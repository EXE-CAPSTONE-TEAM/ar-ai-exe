import json
import math
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ModelAsset, ScanSession, ScanStatus
from app.services.blender_service import BlenderService
from app.services.colmap_service import ColmapService
from app.services.command_runner import CommandRunner
from app.services.file_helpers import write_json
from app.services.model_assets import ModelAssetFiles, ModelAssetService
from app.services.openmvs_service import OpenMVSService
from app.services.reconstruction_toolchain import ReconstructionToolchainService
from app.services.scan_sessions import ScanSessionService
from app.services.storage import get_storage_service
from app.services.mesh_sculpt_service import MeshSculptService, SculptResult


@dataclass(frozen=True)
class FrameStats:
    path: Path
    brightness: float
    sharpness: float
    perceptual_hash: int


@dataclass(frozen=True)
class FrameSelection:
    selected: list[Path]
    extracted_count: int
    rejected_by_reason: dict[str, int]
    average_brightness: float
    average_sharpness: float


class ReconstructionService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.runner = CommandRunner()
        self.scan_service = ScanSessionService(db)
        self.storage = get_storage_service()
        self.colmap = ColmapService()
        self.openmvs = OpenMVSService()
        self.blender = BlenderService()
        self.toolchain = ReconstructionToolchainService(self.settings)

    def process(self, scan_session_id: str) -> ModelAsset:
        scan_session = self.db.get(ScanSession, scan_session_id)
        if not scan_session:
            raise ValueError(f"Scan session {scan_session_id} not found.")
        if not self.scan_service.is_ready_for_processing(scan_session):
            raise ValueError("Scan session requires both side_orbit and top_orbit videos.")

        existing_asset = self.db.scalar(
            select(ModelAsset).where(ModelAsset.scan_session_id == scan_session_id)
        )
        if existing_asset:
            self.scan_service.set_status(scan_session_id, ScanStatus.COMPLETED)
            return existing_asset

        frame_root = self.settings.resolved_storage_root / "frames" / scan_session_id
        model_dir = self.settings.resolved_storage_root / "models" / scan_session_id
        work_dir = model_dir / "work"
        selected_dir = work_dir / "selected-images"
        if model_dir.exists():
            shutil.rmtree(model_dir)
        frame_root.mkdir(parents=True, exist_ok=True)
        selected_dir.mkdir(parents=True, exist_ok=True)
        model_dir.mkdir(parents=True, exist_ok=True)
        log_path = model_dir / "pipeline.log"

        self._preflight_toolchain()

        video_sources = self._video_sources(scan_session)
        self.scan_service.set_status(scan_session_id, ScanStatus.EXTRACTING_FRAMES)
        extracted: dict[str, list[Path]] = {}
        for pass_type, source_path in video_sources.items():
            pass_dir = frame_root / pass_type
            pass_dir.mkdir(parents=True, exist_ok=True)
            extracted[pass_type] = self._extract_frames(pass_type, source_path, pass_dir, log_path)

        self.scan_service.set_status(scan_session_id, ScanStatus.FILTERING_FRAMES)
        selections: dict[str, FrameSelection] = {}
        for pass_type, frame_paths in extracted.items():
            selections[pass_type] = self._filter_frames(pass_type, frame_paths, selected_dir)
        if not any(selection.selected for selection in selections.values()):
            raise RuntimeError("No usable frames remained after filtering.")

        self.scan_service.set_status(scan_session_id, ScanStatus.PREPARING_RECONSTRUCTION)
        metadata_path = model_dir / "metadata.json"
        self._write_metadata(metadata_path, scan_session, selections)

        self.scan_service.set_status(scan_session_id, ScanStatus.RECONSTRUCTING)
        textured_obj_path = self._run_photogrammetry(selected_dir, work_dir, log_path)

        sculpt_result = None
        if self.settings.sculpt_enable:
            self.scan_service.set_status(scan_session_id, ScanStatus.SCULPTING_MESH)
            sculpt_service = MeshSculptService(self.settings)
            sculpt_result = sculpt_service.sculpt_and_bake(
                input_mesh=textured_obj_path,
                output_dir=model_dir,
                log_path=log_path,
            )
            final_mesh_path = sculpt_result.low_poly_obj
        else:
            final_mesh_path = textured_obj_path

        self.scan_service.set_status(scan_session_id, ScanStatus.CLEANING_MESH)
        self._write_blender_script(model_dir / "export_shoe_assets.py")
        self._run_blender_export(final_mesh_path, model_dir, log_path)
        self._copy_obj_package(final_mesh_path, model_dir)

        self.scan_service.set_status(scan_session_id, ScanStatus.EXPORTING)
        quality_report_path = model_dir / "quality_report.json"
        self._write_quality_report(quality_report_path, selections, sculpt_result)
        obj_package_path = model_dir / "shoe_obj_package.zip"
        self._zip_obj_package(model_dir, obj_package_path)

        asset = self._store_asset(
            scan_session_id, model_dir, metadata_path, quality_report_path, obj_package_path
        )
        self.scan_service.set_status(scan_session_id, ScanStatus.COMPLETED)
        return asset

    def _preflight_toolchain(self) -> None:
        self.toolchain.assert_ready()

    def _video_sources(self, scan_session: ScanSession) -> dict[str, Path]:
        side_key = scan_session.side_video_path or scan_session.raw_video_path
        top_key = scan_session.top_video_path
        if not side_key or not top_key:
            raise ValueError("Both side_orbit and top_orbit videos are required.")
        return {
            "side_orbit": self._local_source(side_key, suffix=".mp4"),
            "top_orbit": self._local_source(top_key, suffix=".mp4"),
        }

    def _local_source(self, key: str, suffix: str) -> Path:
        local_path = self.storage.local_path(key)
        if local_path and local_path.exists():
            return local_path
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(self.storage.get_bytes(key))
        temp_file.close()
        return Path(temp_file.name)

    def _extract_frames(
        self,
        pass_type: str,
        video_path: Path,
        frame_dir: Path,
        log_path: Path,
    ) -> list[Path]:
        for existing in frame_dir.glob("*.jpg"):
            existing.unlink()
        output_pattern = frame_dir / f"{pass_type}_%04d.jpg"
        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps={self.settings.reconstruction_frame_fps}",
            "-q:v",
            "2",
            str(output_pattern),
        ]
        self._run_command(command, log_path)
        frame_paths = sorted(frame_dir.glob(f"{pass_type}_*.jpg"))
        if not frame_paths:
            raise RuntimeError(f"FFmpeg extracted no frames for {pass_type}.")
        return frame_paths

    def _filter_frames(
        self,
        pass_type: str,
        frame_paths: list[Path],
        selected_dir: Path,
    ) -> FrameSelection:
        selected: list[Path] = []
        rejected = {
            "invalid": 0,
            "dark": 0,
            "blurry": 0,
            "duplicate": 0,
            "over_limit": 0,
        }
        last_hashes: list[int] = []
        brightness_values: list[float] = []
        sharpness_values: list[float] = []

        for frame_path in frame_paths:
            stats = self._analyze_frame(frame_path)
            if not stats:
                rejected["invalid"] += 1
                continue
            brightness_values.append(stats.brightness)
            sharpness_values.append(stats.sharpness)
            if stats.brightness < self.settings.reconstruction_min_brightness:
                rejected["dark"] += 1
                continue
            if stats.sharpness < self.settings.reconstruction_min_sharpness:
                rejected["blurry"] += 1
                continue
            if any(
                self._hamming_distance(stats.perceptual_hash, item)
                <= self.settings.reconstruction_duplicate_hamming_threshold
                for item in last_hashes[-8:]
            ):
                rejected["duplicate"] += 1
                continue
            if len(selected) >= self.settings.reconstruction_max_frames_per_pass:
                rejected["over_limit"] += 1
                continue

            target = selected_dir / f"{pass_type}_{len(selected) + 1:04d}.jpg"
            shutil.copyfile(frame_path, target)
            selected.append(target)
            last_hashes.append(stats.perceptual_hash)

        if not selected:
            raise RuntimeError(f"No usable frames selected for {pass_type}.")
        return FrameSelection(
            selected=selected,
            extracted_count=len(frame_paths),
            rejected_by_reason=rejected,
            average_brightness=self._average(brightness_values),
            average_sharpness=self._average(sharpness_values),
        )

    def _analyze_frame(self, frame_path: Path) -> FrameStats | None:
        command = [
            self.settings.ffmpeg_bin,
            "-v",
            "error",
            "-i",
            str(frame_path),
            "-vf",
            "scale=64:64,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        try:
            result = subprocess.run(command, capture_output=True, check=False, timeout=30)
        except subprocess.TimeoutExpired:
            return None
        pixels = result.stdout
        if result.returncode != 0 or len(pixels) != 64 * 64:
            return None

        values = list(pixels)
        brightness = self._average(values)
        sharpness = self._laplacian_score(values, 64, 64)
        perceptual_hash = self._average_hash(values, 64, 64)
        return FrameStats(
            path=frame_path,
            brightness=brightness,
            sharpness=sharpness,
            perceptual_hash=perceptual_hash,
        )

    def _run_photogrammetry(self, image_dir: Path, work_dir: Path, log_path: Path) -> Path:
        database_path = work_dir / "colmap.db"
        sparse_dir = work_dir / "sparse"
        sparse_dir.mkdir(parents=True, exist_ok=True)
        self._run_command(
            self.colmap.feature_extraction_command(image_dir, database_path), log_path
        )
        self._run_command(self.colmap.matching_command(database_path), log_path)
        self._run_command(
            self.colmap.mapper_command(image_dir, database_path, sparse_dir), log_path
        )

        sparse_model = sparse_dir / "0"
        if not sparse_model.exists():
            raise RuntimeError("COLMAP did not produce sparse model folder sparse/0.")

        scene_path = work_dir / "scene.mvs"
        dense_scene_path = work_dir / "dense.mvs"
        mesh_scene_path = work_dir / "mesh.mvs"
        refined_scene_path = work_dir / "mesh_refined.mvs"
        textured_scene_path = work_dir / "textured.mvs"
        self._run_command(
            self.openmvs.interface_colmap_command(sparse_model, image_dir, scene_path),
            log_path,
            cwd=work_dir,
        )
        self._run_command(
            self.openmvs.densify_command(scene_path, dense_scene_path), log_path, cwd=work_dir
        )
        self._run_command(
            self.openmvs.reconstruct_mesh_command(dense_scene_path, mesh_scene_path),
            log_path,
            cwd=work_dir,
        )
        self._run_command(
            self.openmvs.refine_mesh_command(mesh_scene_path, refined_scene_path),
            log_path,
            cwd=work_dir,
        )
        self._run_command(
            self.openmvs.texture_mesh_command(refined_scene_path, textured_scene_path),
            log_path,
            cwd=work_dir,
        )

        candidates = sorted(work_dir.glob("*.obj")) + sorted(work_dir.glob("**/*.obj"))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise RuntimeError("OpenMVS did not produce an OBJ mesh.")

    def _write_blender_script(self, script_path: Path) -> None:
        script_path.write_text(
            """
import mathutils
import pathlib
import sys

import bpy


def import_obj(path):
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        bpy.ops.import_scene.obj(filepath=str(path))


def export_glb(path):
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")


def normalize_scene():
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects imported.")
    min_corner = mathutils.Vector((float("inf"), float("inf"), float("inf")))
    max_corner = mathutils.Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in meshes:
        for corner in obj.bound_box:
            world = obj.matrix_world @ mathutils.Vector(corner)
            min_corner.x = min(min_corner.x, world.x)
            min_corner.y = min(min_corner.y, world.y)
            min_corner.z = min(min_corner.z, world.z)
            max_corner.x = max(max_corner.x, world.x)
            max_corner.y = max(max_corner.y, world.y)
            max_corner.z = max(max_corner.z, world.z)
    center = (min_corner + max_corner) / 2
    extent = max(max_corner.x - min_corner.x, max_corner.y - min_corner.y, max_corner.z - min_corner.z)
    scale = 2.4 / extent if extent > 0 else 1
    for obj in meshes:
        obj.location -= center
        obj.scale *= scale


input_obj = pathlib.Path(sys.argv[-2])
output_dir = pathlib.Path(sys.argv[-1])
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
import_obj(input_obj)
normalize_scene()
export_glb(output_dir / "shoe_preview.glb")
""".strip(),
            encoding="utf-8",
        )

    def _run_blender_export(self, textured_obj_path: Path, model_dir: Path, log_path: Path) -> None:
        script_path = model_dir / "export_shoe_assets.py"
        command = self.blender.cleanup_export_command(script_path, textured_obj_path, model_dir)
        self._run_command(command, log_path, cwd=model_dir)
        if not (model_dir / "shoe_preview.glb").exists():
            raise RuntimeError("Blender did not export shoe_preview.glb.")

    def _copy_obj_package(self, source_obj: Path, model_dir: Path) -> None:
        source_mtl, source_texture = self._find_material_and_texture(source_obj)
        obj_text = source_obj.read_text(encoding="utf-8", errors="ignore")
        obj_lines = [
            "mtllib shoe.mtl" if line.startswith("mtllib ") else line
            for line in obj_text.splitlines()
        ]
        (model_dir / "shoe.obj").write_text("\n".join(obj_lines) + "\n", encoding="utf-8")

        mtl_text = source_mtl.read_text(encoding="utf-8", errors="ignore")
        mtl_lines = []
        for line in mtl_text.splitlines():
            if line.strip().startswith("map_Kd "):
                mtl_lines.append("map_Kd shoe_texture.png")
            elif "normal_map.png" in line:
                mtl_lines.append(line.replace("normal_map.png", "shoe_normal_map.png"))
            else:
                mtl_lines.append(line)
        (model_dir / "shoe.mtl").write_text("\n".join(mtl_lines) + "\n", encoding="utf-8")
        shutil.copyfile(source_texture, model_dir / "shoe_texture.png")

        normal_map_src = model_dir / "normal_map.png"
        if normal_map_src.exists():
            shutil.copyfile(normal_map_src, model_dir / "shoe_normal_map.png")

    def _find_material_and_texture(self, source_obj: Path) -> tuple[Path, Path]:
        source_dir = source_obj.parent
        mtl_name: str | None = None
        for line in source_obj.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("mtllib "):
                mtl_name = line.split(maxsplit=1)[1].strip()
                break
        mtl_path = source_dir / mtl_name if mtl_name else None
        if not mtl_path or not mtl_path.exists():
            candidates = sorted(source_dir.glob("*.mtl"))
            if not candidates:
                raise RuntimeError("OpenMVS OBJ output did not include an MTL file.")
            mtl_path = candidates[0]

        texture_name: str | None = None
        for line in mtl_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("map_Kd "):
                texture_name = line.split(maxsplit=1)[1].strip()
                break
        texture_path = source_dir / texture_name if texture_name else None
        if not texture_path or not texture_path.exists():
            candidates = [
                path
                for pattern in ("*.png", "*.jpg", "*.jpeg")
                for path in sorted(source_dir.glob(pattern))
            ]
            if not candidates:
                raise RuntimeError("OpenMVS OBJ output did not include a texture image.")
            texture_path = candidates[0]
        return mtl_path, texture_path

    def _write_metadata(
        self,
        metadata_path: Path,
        scan_session: ScanSession,
        selections: dict[str, FrameSelection],
    ) -> None:
        source_metadata = {}
        if scan_session.metadata_path:
            try:
                source_metadata = json.loads(
                    self.storage.get_bytes(scan_session.metadata_path).decode("utf-8")
                )
            except Exception:
                source_metadata = {}
        write_json(
            metadata_path,
            {
                "scanId": scan_session.id,
                "domain": "shoe",
                "requiredPasses": list(self.scan_service.required_passes),
                "uploadedPasses": self.scan_service.uploaded_passes(scan_session),
                "sourceMetadata": source_metadata,
                "selectedFrames": {
                    pass_type: [path.name for path in selection.selected]
                    for pass_type, selection in selections.items()
                },
            },
        )

    def _write_quality_report(
        self,
        path: Path,
        selections: dict[str, FrameSelection],
        sculpt_result: SculptResult | None = None,
    ) -> None:
        frames_extracted = {
            pass_type: selection.extracted_count for pass_type, selection in selections.items()
        }
        frames_selected = {
            pass_type: len(selection.selected) for pass_type, selection in selections.items()
        }
        rejected: dict[str, int] = {}
        for selection in selections.values():
            for reason, count in selection.rejected_by_reason.items():
                rejected[reason] = rejected.get(reason, 0) + count

        brightness = self._average(
            [selection.average_brightness for selection in selections.values()]
        )
        sharpness = self._average(
            [selection.average_sharpness for selection in selections.values()]
        )
        lighting_score = self._clamp((brightness / 160) * 100)
        blur_score = self._clamp((sharpness / 450) * 100)
        selected_total = sum(frames_selected.values())
        target_total = max(1, self.settings.reconstruction_max_frames_per_pass * len(selections))
        coverage_score = self._clamp((selected_total / target_total) * 100)
        overall = round(
            self._clamp((lighting_score * 0.25) + (blur_score * 0.35) + (coverage_score * 0.40))
        )
        confidence = "high" if overall >= 80 else "medium" if overall >= 55 else "low"
        warnings = []
        if lighting_score < 50:
            warnings.append("Lighting may be too dim for high-quality texture projection.")
        if blur_score < 50:
            warnings.append("Selected frames include motion blur or low detail.")
        if coverage_score < 35:
            warnings.append("Frame coverage is low; reconstruction may miss shoe areas.")

        report = {
            "overallScore": overall,
            "status": "completed",
            "inputVideos": list(selections.keys()),
            "framesExtracted": frames_extracted,
            "framesSelected": frames_selected,
            "rejectedFramesByReason": rejected,
            "lightingScore": round(lighting_score, 1),
            "blurScore": round(blur_score, 1),
            "coverageScore": round(coverage_score, 1),
            "textureConfidence": confidence,
            "geometryConfidence": confidence,
            "scaleConfidence": "medium",
            "warnings": warnings,
            "recommendation": "Use for visual shoe similarity review; not for industrial measurement.",
        }
        if sculpt_result:
            report["sculptMetrics"] = {
                "highPolyFaceCount": sculpt_result.high_poly_face_count,
                "lowPolyFaceCount": sculpt_result.low_poly_face_count,
                "reductionRatio": sculpt_result.reduction_ratio,
                "normalMapResolution": self.settings.sculpt_normal_map_size,
                "textureResolution": self.settings.sculpt_texture_size,
            }

        write_json(path, report)

    def _zip_obj_package(self, model_dir: Path, zip_path: Path) -> None:
        files = [
            "shoe.obj",
            "shoe.mtl",
            "shoe_texture.png",
            "metadata.json",
            "quality_report.json",
        ]
        if (model_dir / "shoe_normal_map.png").exists():
            files.append("shoe_normal_map.png")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in files:
                archive.write(model_dir / name, name)

    def _store_asset(
        self,
        scan_session_id: str,
        model_dir: Path,
        metadata_path: Path,
        quality_report_path: Path,
        obj_package_path: Path,
    ) -> ModelAsset:
        normal_map_path = model_dir / "shoe_normal_map.png"
        return ModelAssetService(self.db).create_from_files(
            scan_session_id,
            ModelAssetFiles(
                glb=model_dir / "shoe_preview.glb",
                obj=model_dir / "shoe.obj",
                mtl=model_dir / "shoe.mtl",
                texture=model_dir / "shoe_texture.png",
                metadata=metadata_path,
                quality_report=quality_report_path,
                obj_package_zip=obj_package_path,
                normal_map=normal_map_path if normal_map_path.exists() else None,
            ),
        )

    def _run_command(self, command: list[str], log_path: Path, cwd: Path | None = None) -> None:
        result = self.runner.run(
            command,
            log_path=log_path,
            cwd=cwd,
            timeout=self.settings.reconstruction_command_timeout_seconds,
            env=self._pipeline_env(),
        )
        if not result.ok:
            message = result.stderr.strip() or result.stdout.strip() or "command failed"
            raise RuntimeError(
                f"Reconstruction command failed: {' '.join(command)}\n{message[-1200:]}"
            )

    def _pipeline_env(self) -> dict[str, str]:
        max_threads = str(max(1, self.settings.reconstruction_max_threads))
        return {
            "OMP_NUM_THREADS": max_threads,
            "OPENBLAS_NUM_THREADS": max_threads,
            "MKL_NUM_THREADS": max_threads,
            "NUMEXPR_NUM_THREADS": max_threads,
            "VECLIB_MAXIMUM_THREADS": max_threads,
        }

    def _laplacian_score(self, pixels: list[int], width: int, height: int) -> float:
        scores: list[int] = []
        for y in range(1, height - 1):
            row = y * width
            for x in range(1, width - 1):
                index = row + x
                center = pixels[index]
                laplacian = (
                    (4 * center)
                    - pixels[index - 1]
                    - pixels[index + 1]
                    - pixels[index - width]
                    - pixels[index + width]
                )
                scores.append(abs(laplacian))
        return self._average(scores)

    def _average_hash(self, pixels: list[int], width: int, height: int) -> int:
        block_width = width // 8
        block_height = height // 8
        blocks: list[float] = []
        for block_y in range(8):
            for block_x in range(8):
                values = []
                for y in range(block_y * block_height, (block_y + 1) * block_height):
                    offset = y * width
                    for x in range(block_x * block_width, (block_x + 1) * block_width):
                        values.append(pixels[offset + x])
                blocks.append(self._average(values))
        threshold = self._average(blocks)
        result = 0
        for index, value in enumerate(blocks):
            if value >= threshold:
                result |= 1 << index
        return result

    def _hamming_distance(self, left: int, right: int) -> int:
        return (left ^ right).bit_count()

    def _average(self, values: list[float] | list[int]) -> float:
        if not values:
            return 0.0
        return float(sum(values) / len(values))

    def _clamp(self, value: float, low: float = 0.0, high: float = 100.0) -> float:
        if math.isnan(value):
            return low
        return min(high, max(low, value))
