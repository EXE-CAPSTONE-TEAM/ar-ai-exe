import { Grid, OrbitControls, TransformControls, useGLTF, useTexture } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Fragment, Suspense, useEffect, useMemo, useRef } from "react";
import type { RefObject } from "react";
import * as THREE from "three";

import type { DesignConfig, StickerLayer, TextLayer } from "../../types";
import { ErrorBoundary } from "../Layout/ErrorBoundary";

const TRANSPARENT_PIXEL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";

type ModelViewerProps = {
  modelUrl: string | null;
  config: DesignConfig | null;
  activeLayerId: string | null;
  hiddenLayerIds: string[];
  isSaving: boolean;
  previewErrorMessage: string | null;
  surfaceApplyRequest: number;
  onConfigChange: (config: DesignConfig) => void;
  onActiveLayerChange: (id: string | null) => void;
  onMeshBoundsUpdate: (bounds: { center: [number, number, number]; size: [number, number, number] }) => void;
  onSurfaceApplyResult: (message: string) => void;
  gizmoMode: "translate" | "rotate" | "scale";
};

export function ModelViewer({
  modelUrl,
  config,
  activeLayerId,
  hiddenLayerIds,
  isSaving,
  previewErrorMessage,
  surfaceApplyRequest,
  gizmoMode,
  onConfigChange,
  onActiveLayerChange,
  onMeshBoundsUpdate,
  onSurfaceApplyResult,
}: ModelViewerProps) {
  return (
    <div className="viewer-surface">
      {modelUrl ? (
        <>
          <Canvas camera={{ position: [3, 2, 3], fov: 45 }} shadows>
            <color attach="background" args={["#f8fafc"]} />
            <ambientLight intensity={0.8} />
            <directionalLight position={[3, 4, 5]} intensity={1.3} castShadow />
            <ErrorBoundary fallbackMessage="Failed to load 3D model. The file might be invalid or corrupted.">
              <Suspense fallback={null}>
                <ShoeModel
                  url={modelUrl}
                  config={config}
                  activeLayerId={activeLayerId}
                  hiddenLayerIds={hiddenLayerIds}
                  isSaving={isSaving}
                  surfaceApplyRequest={surfaceApplyRequest}
                  gizmoMode={gizmoMode}
                  onConfigChange={onConfigChange}
                  onActiveLayerChange={onActiveLayerChange}
                  onMeshBoundsUpdate={onMeshBoundsUpdate}
                  onSurfaceApplyResult={onSurfaceApplyResult}
                />
              </Suspense>
            </ErrorBoundary>
            <Grid
              args={[5, 5]}
              cellSize={0.5}
              cellThickness={0.5}
              sectionSize={1}
              sectionThickness={0.8}
              position={[0, -0.02, 0]}
            />
            <OrbitControls makeDefault enablePan enableZoom enableRotate />
          </Canvas>
          {isSaving ? (
            <div className="viewer-saving-overlay" role="status" aria-live="polite">
              <div className="saving-spinner" aria-hidden="true" />
              <span>Đang áp sticker/text vào giày...</span>
            </div>
          ) : null}
          {!isSaving && previewErrorMessage ? (
            <div className="viewer-warning-overlay" role="status" aria-live="polite">
              <strong>Preview chưa áp được vào giày</strong>
              <span>{previewErrorMessage}</span>
            </div>
          ) : null}
        </>
      ) : (
        <div className="viewer-empty">
          <BoxIcon />
          <span>Load a completed scan or imported model.</span>
        </div>
      )}
    </div>
  );
}

type ShoeModelProps = {
  url: string;
  config: DesignConfig | null;
  activeLayerId: string | null;
  hiddenLayerIds: string[];
  isSaving: boolean;
  surfaceApplyRequest: number;
  onConfigChange: (config: DesignConfig) => void;
  onActiveLayerChange: (id: string | null) => void;
  onMeshBoundsUpdate: (bounds: { center: [number, number, number]; size: [number, number, number] }) => void;
  onSurfaceApplyResult: (message: string) => void;
  gizmoMode: "translate" | "rotate" | "scale";
};

function ShoeModel({
  url,
  config,
  activeLayerId,
  hiddenLayerIds,
  isSaving,
  surfaceApplyRequest,
  gizmoMode,
  onConfigChange,
  onActiveLayerChange,
  onMeshBoundsUpdate,
  onSurfaceApplyResult,
}: ShoeModelProps) {
  const gltf = useGLTF(url);
  const hiddenLayerSet = useMemo(() => new Set(hiddenLayerIds), [hiddenLayerIds]);
  const handledSurfaceApplyRequest = useRef(0);

  const modelMetrics = useMemo(() => {
    const bounds = computeSceneLocalBounds(gltf.scene);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const previewScale = maxDim > 0 ? 2.5 / maxDim : 1;
    return { center, size, previewScale };
  }, [gltf.scene]);

  const centeredModelPosition = useMemo(
    () => modelMetrics.center.clone().multiplyScalar(-1),
    [modelMetrics],
  );
  const raycastTargets = useMemo(
    () => createModelRaycastTargets(gltf.scene, modelMetrics.center),
    [gltf.scene, modelMetrics.center],
  );

  useEffect(() => {
    onMeshBoundsUpdate({
      center: vectorToTuple(modelMetrics.center),
      size: vectorToTuple(modelMetrics.size),
    });
  }, [modelMetrics, onMeshBoundsUpdate]);

  useEffect(() => {
    gltf.scene.traverse((node) => {
      if (node instanceof THREE.Mesh) {
        if (isDecalMeshName(node.name)) {
          node.castShadow = true;
          node.receiveShadow = true;
          return;
        }

        if (!node.userData.originalMaterial) {
          if (Array.isArray(node.material)) {
            node.userData.originalMaterial = node.material.map((m: THREE.Material) => m.clone());
          } else if (node.material) {
            node.userData.originalMaterial = node.material.clone();
          }
        }

        if (node.userData.originalMaterial) {
          const applyConfig = (mat: THREE.Material) => {
            const m = mat.clone();
            if (m instanceof THREE.MeshStandardMaterial || m instanceof THREE.MeshPhysicalMaterial) {
              m.color = new THREE.Color(config?.baseColor ?? "#ffffff");
              m.roughness = config?.material.roughness ?? 1;
              m.metalness = config?.material.metallic ?? 0;
            }
            return m;
          };

          if (Array.isArray(node.userData.originalMaterial)) {
            node.material = node.userData.originalMaterial.map(applyConfig);
          } else {
            node.material = applyConfig(node.userData.originalMaterial);
          }
        }

        node.castShadow = true;
        node.receiveShadow = true;
      }
    });
  }, [config?.baseColor, config?.material.metallic, config?.material.roughness, gltf.scene]);

  useEffect(() => {
    if (!surfaceApplyRequest || handledSurfaceApplyRequest.current === surfaceApplyRequest) {
      return;
    }
    handledSurfaceApplyRequest.current = surfaceApplyRequest;

    if (!config || !activeLayerId) {
      onSurfaceApplyResult("Select a sticker or text layer first.");
      return;
    }

    const snappedConfig = snapLayerToSurface(config, activeLayerId, modelMetrics.center, raycastTargets);
    if (!snappedConfig) {
      onSurfaceApplyResult("No shoe surface found near the selected layer.");
      return;
    }

    onConfigChange(snappedConfig);
    onSurfaceApplyResult("Layer applied to shoe surface.");
  }, [
    activeLayerId,
    config,
    modelMetrics.center,
    onConfigChange,
    onSurfaceApplyResult,
    raycastTargets,
    surfaceApplyRequest,
  ]);

  const handlePointerMissed = () => {
    onActiveLayerChange(null);
  };

  const handleTransformEnd = (
    id: string,
    isText: boolean,
    pos: [number, number, number],
    rot: [number, number, number],
    scale: number,
  ) => {
    if (!config) return;

    if (isText) {
      onConfigChange({
        ...config,
        texts: config.texts.map((t) =>
          t.id === id
            ? {
                ...t,
                position: pos,
                rotation: rot,
                normal: normalFromRotation(rot),
                targetMeshName: null,
                scale,
                width: scale * textAspect(t.value),
                height: scale,
                projectionDepth: Math.max(t.projectionDepth ?? 0, scale * 3, 0.05),
              }
            : t,
        ),
      });
    } else {
      onConfigChange({
        ...config,
        stickers: config.stickers.map((s) =>
          s.id === id
            ? {
                ...s,
                position: pos,
                rotation: rot,
                normal: normalFromRotation(rot),
                targetMeshName: null,
                scale,
                width: scale,
                height: scale,
                projectionDepth: Math.max(s.projectionDepth ?? 0, scale * 3, 0.05),
              }
            : s,
        ),
      });
    }
  };

  return (
    <group scale={modelMetrics.previewScale} onPointerMissed={handlePointerMissed}>
      <group position={centeredModelPosition}>
        <primitive object={gltf.scene} />
      </group>

      {config?.stickers
        .filter((sticker) => !hiddenLayerSet.has(sticker.id))
        .map((sticker) => (
          <StickerPlane
            key={sticker.id}
            sticker={sticker}
            modelCenter={modelMetrics.center}
            isActive={sticker.id === activeLayerId}
            isSaving={isSaving}
            gizmoMode={gizmoMode}
            onTransformEnd={(pos, rot, s) => handleTransformEnd(sticker.id, false, pos, rot, s)}
          />
        ))}
      {config?.texts
        .filter((textLayer) => !hiddenLayerSet.has(textLayer.id))
        .map((textLayer) => (
          <TextPlane
            key={textLayer.id}
            layer={textLayer}
            modelCenter={modelMetrics.center}
            isActive={textLayer.id === activeLayerId}
            isSaving={isSaving}
            gizmoMode={gizmoMode}
            onTransformEnd={(pos, rot, s) => handleTransformEnd(textLayer.id, true, pos, rot, s)}
          />
        ))}
    </group>
  );
}

function computeSceneLocalBounds(scene: THREE.Object3D): THREE.Box3 {
  scene.updateWorldMatrix(true, true);
  const sceneWorldInverse = scene.matrixWorld.clone().invert();
  const bounds = new THREE.Box3();
  const meshBounds = new THREE.Box3();

  scene.traverse((node) => {
    if (!(node instanceof THREE.Mesh) || !node.geometry.attributes.position) return;
    if (!node.geometry.boundingBox) {
      node.geometry.computeBoundingBox();
    }
    if (!node.geometry.boundingBox) return;

    node.updateWorldMatrix(true, false);
    meshBounds.copy(node.geometry.boundingBox);
    meshBounds.applyMatrix4(sceneWorldInverse.clone().multiply(node.matrixWorld));
    bounds.union(meshBounds);
  });

  if (bounds.isEmpty()) {
    bounds.setFromCenterAndSize(new THREE.Vector3(), new THREE.Vector3(1, 1, 1));
  }
  return bounds;
}

type ModelRaycastTarget = {
  name: string;
  mesh: THREE.Mesh;
};

function createModelRaycastTargets(root: THREE.Object3D, modelCenter: THREE.Vector3): ModelRaycastTarget[] {
  const targets: ModelRaycastTarget[] = [];
  root.updateWorldMatrix(true, true);
  const rootWorldInverse = root.matrixWorld.clone().invert();
  const centerOffset = new THREE.Matrix4().makeTranslation(-modelCenter.x, -modelCenter.y, -modelCenter.z);

  root.traverse((node) => {
    if (!(node instanceof THREE.Mesh) || !node.geometry.attributes.position || isDecalMeshName(node.name)) {
      return;
    }

    node.updateWorldMatrix(true, false);
    const mesh = new THREE.Mesh(node.geometry);
    const relativeMatrix = rootWorldInverse.clone().multiply(node.matrixWorld);
    const stageMatrix = centerOffset.clone().multiply(relativeMatrix);
    mesh.name = node.name || node.geometry.name || "model_mesh";
    mesh.matrixAutoUpdate = false;
    mesh.matrix.copy(stageMatrix);
    mesh.matrixWorld.copy(stageMatrix);
    targets.push({ name: mesh.name, mesh });
  });

  return targets;
}

function isDecalMeshName(name: string): boolean {
  return name.startsWith("decal_") || name.startsWith("svg_decal_") || name.startsWith("text_decal_");
}

function snapLayerToSurface(
  config: DesignConfig,
  activeLayerId: string,
  modelCenter: THREE.Vector3,
  raycastTargets: ModelRaycastTarget[],
): DesignConfig | null {
  const sticker = config.stickers.find((item) => item.id === activeLayerId);
  const textLayer = config.texts.find((item) => item.id === activeLayerId);
  const layer = sticker ?? textLayer;
  if (!layer || raycastTargets.length === 0) {
    return null;
  }

  const stagePosition = new THREE.Vector3(...layer.position).sub(modelCenter);
  const rotation = new THREE.Euler(...layer.rotation);
  const outwardNormal = new THREE.Vector3(0, 0, 1).applyEuler(rotation).normalize();
  const decalSize = layerMaxSize(layer);
  const hit = projectStagePointToSurface(
    stagePosition,
    outwardNormal,
    snapProjectionDepth(layer, decalSize),
    raycastTargets,
  );
  if (!hit) {
    return null;
  }

  const offset = surfaceOffset(layer, decalSize);
  const snappedStagePosition = hit.point.clone().addScaledVector(hit.normal, offset);
  const snappedPosition = snappedStagePosition.clone().add(modelCenter);
  const snappedRotation = rotationAlignedToNormal(rotation, hit.normal);
  const patch = {
    position: vectorToTuple(snappedPosition),
    rotation: snappedRotation,
    normal: vectorToTuple(hit.normal),
    targetMeshName: hit.targetName,
    offset,
    projectionDepth: Math.max(decalSize * 1.25, 0.05),
  };

  if (sticker) {
    return {
      ...config,
      stickers: config.stickers.map((item) => (item.id === activeLayerId ? { ...item, ...patch } : item)),
    };
  }

  return {
    ...config,
    texts: config.texts.map((item) => (item.id === activeLayerId ? { ...item, ...patch } : item)),
  };
}

function projectStagePointToSurface(
  stagePoint: THREE.Vector3,
  outwardNormal: THREE.Vector3,
  depth: number,
  raycastTargets: ModelRaycastTarget[],
): { point: THREE.Vector3; normal: THREE.Vector3; targetName: string } | null {
  const raycaster = new THREE.Raycaster();
  const targetMeshes = raycastTargets.map((target) => target.mesh);
  const candidates: Array<{ intersection: THREE.Intersection; priority: number; distanceSq: number }> = [];

  const collect = (origin: THREE.Vector3, direction: THREE.Vector3, priority: number) => {
    raycaster.near = 0;
    raycaster.far = depth * 2;
    raycaster.set(origin, direction);
    for (const intersection of raycaster.intersectObjects(targetMeshes, false)) {
      candidates.push({
        intersection,
        priority,
        distanceSq: intersection.point.distanceToSquared(stagePoint),
      });
    }
  };

  collect(stagePoint.clone().addScaledVector(outwardNormal, depth), outwardNormal.clone().negate(), 0);
  collect(stagePoint.clone().addScaledVector(outwardNormal, -depth), outwardNormal, 1);
  if (candidates.length === 0) {
    return null;
  }

  candidates.sort((a, b) => a.priority - b.priority || a.distanceSq - b.distanceSq);
  const intersection = candidates[0].intersection;
  const surfaceNormal = intersectionNormal(intersection, outwardNormal);
  const targetName =
    raycastTargets.find((target) => target.mesh === intersection.object)?.name ||
    intersection.object.name ||
    "";

  return { point: intersection.point.clone(), normal: surfaceNormal, targetName };
}

function intersectionNormal(intersection: THREE.Intersection, outwardNormal: THREE.Vector3): THREE.Vector3 {
  const normal = intersection.face
    ? intersection.face.normal
        .clone()
        .applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(intersection.object.matrixWorld))
    : outwardNormal.clone();

  if (normal.lengthSq() === 0) {
    normal.copy(outwardNormal);
  }
  normal.normalize();
  if (normal.dot(outwardNormal) < 0) {
    normal.negate();
  }
  return normal;
}

function rotationAlignedToNormal(currentRotation: THREE.Euler, normal: THREE.Vector3): [number, number, number] {
  const currentQuaternion = new THREE.Quaternion().setFromEuler(currentRotation);
  let tangentX = new THREE.Vector3(1, 0, 0).applyQuaternion(currentQuaternion).projectOnPlane(normal);
  if (tangentX.lengthSq() < 0.000001) {
    const fallback = Math.abs(normal.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    tangentX = fallback.projectOnPlane(normal);
  }
  tangentX.normalize();
  const tangentY = new THREE.Vector3().crossVectors(normal, tangentX).normalize();
  const matrix = new THREE.Matrix4().makeBasis(tangentX, tangentY, normal);
  const rotation = new THREE.Euler().setFromRotationMatrix(matrix, "XYZ");
  return [rotation.x, rotation.y, rotation.z];
}

function normalFromRotation(rotation: [number, number, number]): [number, number, number] {
  return vectorToTuple(new THREE.Vector3(0, 0, 1).applyEuler(new THREE.Euler(...rotation)).normalize());
}

function layerMaxSize(layer: StickerLayer | TextLayer): number {
  return Math.max(layer.width ?? layer.scale, layer.height ?? layer.scale, layer.scale, 0.0001);
}

function snapProjectionDepth(layer: StickerLayer | TextLayer, decalSize: number): number {
  const configuredDepth = layer.projectionDepth ?? decalSize * 1.25;
  const minimumDepth = Math.max(decalSize * 0.5, 0.05);
  const maximumDepth = Math.max(decalSize * 2.5, 0.1);
  return clamp(configuredDepth, minimumDepth, maximumDepth);
}

function surfaceOffset(layer: StickerLayer | TextLayer, decalSize: number): number {
  return clamp(Math.max(layer.offset ?? 0.004, decalSize * 0.005, 0.002), 0, 0.1);
}

function vectorToTuple(vector: THREE.Vector3): [number, number, number] {
  return [vector.x, vector.y, vector.z];
}

function StickerPlane({
  sticker,
  modelCenter,
  isActive,
  isSaving,
  gizmoMode,
  onTransformEnd,
}: {
  sticker: StickerLayer;
  modelCenter: THREE.Vector3;
  isActive: boolean;
  isSaving: boolean;
  gizmoMode: "translate" | "rotate" | "scale";
  onTransformEnd: (pos: [number, number, number], rot: [number, number, number], scale: number) => void;
}) {
  const texture = useTexture(stickerTextureUrl(sticker));
  const ref = useRef<THREE.Mesh>(null);
  texture.colorSpace = THREE.SRGBColorSpace;

  const position = useMemo(() => new THREE.Vector3(...sticker.position).sub(modelCenter), [modelCenter, sticker.position]);
  const rotation = useMemo(() => new THREE.Euler(...sticker.rotation), [sticker.rotation]);
  const scale = Math.max(sticker.scale, 0.0001);

  return (
    <Fragment>
      <mesh
        ref={ref}
        name={`layer_preview_${sticker.id}`}
        position={position}
        rotation={rotation}
        scale={[scale, scale, scale]}
      >
        <planeGeometry args={[1, 1]} />
        <meshStandardMaterial
          map={texture}
          transparent
          side={THREE.DoubleSide}
          depthWrite={false}
          polygonOffset
          polygonOffsetFactor={-4}
        />
      </mesh>
      {isActive && !isSaving ? (
        <TransformControls
          object={ref as RefObject<THREE.Object3D>}
          mode={gizmoMode}
          size={gizmoSize(sticker.scale)}
          onMouseUp={() => {
            if (ref.current) {
              const p = ref.current.position;
              const r = ref.current.rotation;
              const s = ref.current.scale;
              const savedPosition = p.clone().add(modelCenter);
              onTransformEnd(vectorToTuple(savedPosition), [r.x, r.y, r.z], Math.max(s.x, s.y, s.z));
            }
          }}
        />
      ) : null}
    </Fragment>
  );
}

function stickerTextureUrl(sticker: StickerLayer): string {
  return sticker.previewUrl ?? sticker.imageUrl ?? TRANSPARENT_PIXEL;
}

function TextPlane({
  layer,
  modelCenter,
  isActive,
  isSaving,
  gizmoMode,
  onTransformEnd,
}: {
  layer: TextLayer;
  modelCenter: THREE.Vector3;
  isActive: boolean;
  isSaving: boolean;
  gizmoMode: "translate" | "rotate" | "scale";
  onTransformEnd: (pos: [number, number, number], rot: [number, number, number], scale: number) => void;
}) {
  const textureUrl = useMemo(() => textSvgDataUri(layer), [layer]);
  const texture = useTexture(textureUrl);
  const ref = useRef<THREE.Mesh>(null);
  texture.colorSpace = THREE.SRGBColorSpace;

  const position = useMemo(() => new THREE.Vector3(...layer.position).sub(modelCenter), [layer.position, modelCenter]);
  const rotation = useMemo(() => new THREE.Euler(...layer.rotation), [layer.rotation]);
  const scale = Math.max(layer.scale, 0.0001);
  const aspect = textAspect(layer.value);

  return (
    <Fragment>
      <mesh
        ref={ref}
        name={`layer_preview_${layer.id}`}
        position={position}
        rotation={rotation}
        scale={[scale, scale, scale]}
      >
        <planeGeometry args={[aspect, 1]} />
        <meshBasicMaterial
          map={texture}
          transparent
          side={THREE.DoubleSide}
          depthWrite={false}
          polygonOffset
          polygonOffsetFactor={-4}
        />
      </mesh>
      {isActive && !isSaving ? (
        <TransformControls
          object={ref as RefObject<THREE.Object3D>}
          mode={gizmoMode}
          size={gizmoSize(layer.scale)}
          onMouseUp={() => {
            if (ref.current) {
              const p = ref.current.position;
              const r = ref.current.rotation;
              const s = ref.current.scale;
              const savedPosition = p.clone().add(modelCenter);
              onTransformEnd(vectorToTuple(savedPosition), [r.x, r.y, r.z], Math.max(s.x, s.y, s.z));
            }
          }}
        />
      ) : null}
    </Fragment>
  );
}

function textSvgDataUri(layer: TextLayer): string {
  const value = escapeXml(layer.value || " ");
  const color = safeColor(layer.color);
  const font = escapeAttribute(layer.font || "Arial");
  const aspect = textAspect(layer.value);
  const width = Math.round(512 * aspect);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="512" viewBox="0 0 ${width} 512"><rect width="100%" height="100%" fill="none"/><text x="50%" y="50%" fill="${color}" font-family="${font}" font-size="300" font-weight="700" text-anchor="middle" dominant-baseline="central">${value}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function textAspect(value: string): number {
  return Math.max(value.trim().length * 0.62, 1);
}

function gizmoSize(scale: number): number {
  return clamp(scale * 2.25, 0.35, 0.75);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function safeColor(value: string): string {
  return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : "#ffffff";
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttribute(value: string): string {
  return escapeXml(value).replace(/"/g, "&quot;");
}

function BoxIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="48" height="48">
      <path
        fill="currentColor"
        d="M12 2 3 6.5v11L12 22l9-4.5v-11L12 2Zm0 2.24 5.7 2.85L12 9.94 6.3 7.09 12 4.24ZM5 8.62l6 3v7.76l-6-3V8.62Zm8 10.76v-7.76l6-3v7.76l-6 3Z"
      />
    </svg>
  );
}
