import base64
import json
import shutil
import struct
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ModelAsset, ScanSession, ScanStatus
from app.services.command_runner import CommandRunner
from app.services.file_helpers import write_json
from app.services.scan_sessions import ScanSessionService
from app.services.storage import get_storage_service


PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax"
    "wDVkAAAAASUVORK5CYII="
)


class ReconstructionService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.runner = CommandRunner()
        self.scan_service = ScanSessionService(db)
        self.storage = get_storage_service()

    def process(self, scan_session_id: str) -> ModelAsset:
        scan_session = self.db.get(ScanSession, scan_session_id)
        if not scan_session:
            raise ValueError(f"Scan session {scan_session_id} not found.")
        if not scan_session.raw_video_path:
            raise ValueError("Scan session has no uploaded video.")

        existing_asset = self.db.scalar(
            select(ModelAsset).where(ModelAsset.scan_session_id == scan_session_id)
        )
        if existing_asset:
            self.scan_service.set_status(scan_session_id, ScanStatus.COMPLETED)
            return existing_asset

        frame_dir = self.settings.resolved_storage_root / "frames" / scan_session_id
        model_dir = self.settings.resolved_storage_root / "models" / scan_session_id
        frame_dir.mkdir(parents=True, exist_ok=True)
        model_dir.mkdir(parents=True, exist_ok=True)

        self.scan_service.set_status(scan_session_id, ScanStatus.EXTRACTING_FRAMES)
        source_video = self._local_source(scan_session.raw_video_path, suffix=".mp4")
        frame_count = self._extract_frames(source_video, frame_dir, model_dir)

        self.scan_service.set_status(scan_session_id, ScanStatus.RECONSTRUCTING)
        self._write_pipeline_log(model_dir, "Using mock reconstruction output for MVP.")

        self.scan_service.set_status(scan_session_id, ScanStatus.CLEANING_MESH)
        glb_path = model_dir / "shoe_base.glb"
        obj_path = model_dir / "shoe_base.obj"
        mtl_path = model_dir / "shoe_base.mtl"
        texture_path = model_dir / "base_texture.png"
        self._write_mock_assets(glb_path, obj_path, mtl_path, texture_path)

        self.scan_service.set_status(scan_session_id, ScanStatus.UV_UNWRAPPING)
        self._write_pipeline_log(model_dir, "Mock UV unwrap completed.")

        self.scan_service.set_status(scan_session_id, ScanStatus.TEXTURE_BAKING)
        self._write_pipeline_log(model_dir, "Mock texture bake completed.")

        self.scan_service.set_status(scan_session_id, ScanStatus.EXPORTING)
        quality_report_path = model_dir / "quality_report.json"
        self._write_quality_report(quality_report_path, frame_count)

        glb_object = self.storage.put_bytes(
            f"models/{scan_session_id}/shoe_base.glb",
            glb_path.read_bytes(),
            "model/gltf-binary",
        )
        obj_object = self.storage.put_bytes(
            f"models/{scan_session_id}/shoe_base.obj",
            obj_path.read_bytes(),
            "text/plain",
        )
        mtl_object = self.storage.put_bytes(
            f"models/{scan_session_id}/shoe_base.mtl",
            mtl_path.read_bytes(),
            "text/plain",
        )
        texture_object = self.storage.put_bytes(
            f"models/{scan_session_id}/base_texture.png",
            texture_path.read_bytes(),
            "image/png",
        )
        quality_object = self.storage.put_bytes(
            f"models/{scan_session_id}/quality_report.json",
            quality_report_path.read_bytes(),
            "application/json",
        )

        asset = ModelAsset(
            scan_session_id=scan_session_id,
            glb_path=glb_object.key,
            glb_size_bytes=glb_object.size_bytes,
            glb_content_type=glb_object.content_type,
            glb_checksum=glb_object.checksum,
            obj_path=obj_object.key,
            obj_size_bytes=obj_object.size_bytes,
            obj_content_type=obj_object.content_type,
            obj_checksum=obj_object.checksum,
            mtl_path=mtl_object.key,
            mtl_size_bytes=mtl_object.size_bytes,
            mtl_content_type=mtl_object.content_type,
            mtl_checksum=mtl_object.checksum,
            texture_path=texture_object.key,
            texture_size_bytes=texture_object.size_bytes,
            texture_content_type=texture_object.content_type,
            texture_checksum=texture_object.checksum,
            quality_report_path=quality_object.key,
            quality_report_size_bytes=quality_object.size_bytes,
            quality_report_content_type=quality_object.content_type,
            quality_report_checksum=quality_object.checksum,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)

        self.scan_service.set_status(scan_session_id, ScanStatus.COMPLETED)
        return asset

    def _local_source(self, key: str, suffix: str) -> Path:
        local_path = self.storage.local_path(key)
        if local_path and local_path.exists():
            return local_path
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(self.storage.get_bytes(key))
        temp_file.close()
        return Path(temp_file.name)

    def _extract_frames(self, video_path: Path, frame_dir: Path, model_dir: Path) -> int:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            output_pattern = frame_dir / "frame_%04d.jpg"
            result = self.runner.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(video_path),
                    "-vf",
                    "fps=2",
                    str(output_pattern),
                ],
                model_dir / "pipeline.log",
            )
            frame_count = len(list(frame_dir.glob("frame_*.jpg")))
            if result.ok and frame_count > 0:
                return frame_count

        placeholder = frame_dir / "frame_0001.jpg"
        placeholder.write_bytes(PLACEHOLDER_PNG)
        self._write_pipeline_log(model_dir, "FFmpeg unavailable or failed. Wrote placeholder frame.")
        return 1

    def _write_pipeline_log(self, model_dir: Path, message: str) -> None:
        with (model_dir / "pipeline.log").open("a", encoding="utf-8") as log_file:
            log_file.write(f"{message}\n")

    def _write_quality_report(self, path: Path, frame_count: int) -> None:
        write_json(
            path,
            {
                "overallScore": 75,
                "frameCount": frame_count,
                "lighting": "unknown",
                "blur": "unknown",
                "coverage": "unknown",
                "scaleConfidence": "medium",
                "recommendation": "Usable for visual design package.",
            },
        )

    def _write_mock_assets(
        self,
        glb_path: Path,
        obj_path: Path,
        mtl_path: Path,
        texture_path: Path,
    ) -> None:
        glb_path.write_bytes(self._build_mock_glb())
        texture_path.write_bytes(PLACEHOLDER_PNG)
        mtl_path.write_text(
            "newmtl shoe_base\n"
            "Kd 0.95 0.95 0.95\n"
            "Ka 0.1 0.1 0.1\n"
            "Ks 0.2 0.2 0.2\n"
            "map_Kd base_texture.png\n",
            encoding="utf-8",
        )
        obj_path.write_text(
            "mtllib shoe_base.mtl\n"
            "o mock_shoe_base\n"
            "v -1.20 -0.40 0.00\n"
            "v -1.20 0.40 0.00\n"
            "v 1.20 0.34 0.00\n"
            "v 1.20 -0.34 0.00\n"
            "v -1.00 -0.38 0.36\n"
            "v -1.00 0.38 0.36\n"
            "v 0.95 0.30 0.20\n"
            "v 0.95 -0.30 0.20\n"
            "usemtl shoe_base\n"
            "f 1 2 3\n"
            "f 1 3 4\n"
            "f 5 8 7\n"
            "f 5 7 6\n"
            "f 1 5 6\n"
            "f 1 6 2\n"
            "f 2 6 7\n"
            "f 2 7 3\n"
            "f 3 7 8\n"
            "f 3 8 4\n"
            "f 4 8 5\n"
            "f 4 5 1\n",
            encoding="utf-8",
        )

    def _build_mock_glb(self) -> bytes:
        positions = [
            -1.20,
            -0.40,
            0.00,
            -1.20,
            0.40,
            0.00,
            1.20,
            0.34,
            0.00,
            1.20,
            -0.34,
            0.00,
            -1.00,
            -0.38,
            0.36,
            -1.00,
            0.38,
            0.36,
            0.95,
            0.30,
            0.20,
            0.95,
            -0.30,
            0.20,
        ]
        indices = [
            0,
            1,
            2,
            0,
            2,
            3,
            4,
            7,
            6,
            4,
            6,
            5,
            0,
            4,
            5,
            0,
            5,
            1,
            1,
            5,
            6,
            1,
            6,
            2,
            2,
            6,
            7,
            2,
            7,
            3,
            3,
            7,
            4,
            3,
            4,
            0,
        ]
        position_bytes = struct.pack(f"<{len(positions)}f", *positions)
        index_bytes = struct.pack(f"<{len(indices)}H", *indices)
        binary = position_bytes + index_bytes
        gltf = {
            "asset": {"version": "2.0", "generator": "Shoe Visual Customizer mock pipeline"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": "mock_shoe_base"}],
            "meshes": [
                {
                    "primitives": [
                        {
                            "attributes": {"POSITION": 0},
                            "indices": 1,
                            "material": 0,
                        }
                    ]
                }
            ],
            "materials": [
                {
                    "name": "shoe_base",
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [0.95, 0.95, 0.95, 1.0],
                        "metallicFactor": 0.0,
                        "roughnessFactor": 0.6,
                    },
                }
            ],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
                {
                    "buffer": 0,
                    "byteOffset": len(position_bytes),
                    "byteLength": len(index_bytes),
                    "target": 34963,
                },
            ],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 8,
                    "type": "VEC3",
                    "min": [-1.2, -0.4, 0.0],
                    "max": [1.2, 0.4, 0.36],
                },
                {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
            ],
        }
        json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
        binary += b"\x00" * ((4 - len(binary) % 4) % 4)

        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
        return (
            struct.pack("<III", 0x46546C67, 2, total_length)
            + struct.pack("<I4s", len(json_chunk), b"JSON")
            + json_chunk
            + struct.pack("<I4s", len(binary), b"BIN\x00")
            + binary
        )
