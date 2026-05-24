import { Center, Grid, OrbitControls, useGLTF, Decal, useTexture } from "@react-three/drei";
import { Canvas, ThreeEvent } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import type { DesignConfig, StickerLayer, TextLayer } from "../../types";
import { ErrorBoundary } from "../Layout/ErrorBoundary";

type ModelViewerProps = {
  modelUrl: string | null;
  config: DesignConfig | null;
  activeLayerId: string | null;
  onConfigChange: (config: DesignConfig) => void;
  onActiveLayerChange: (id: string | null) => void;
  onMeshBoundsUpdate: (bounds: { center: [number, number, number]; size: [number, number, number] }) => void;
  gizmoMode: "translate" | "rotate" | "scale";
};

export function ModelViewer({ modelUrl, config, activeLayerId, gizmoMode, onConfigChange, onActiveLayerChange, onMeshBoundsUpdate }: ModelViewerProps) {
  return (
    <div className="viewer-surface">
      {modelUrl ? (
        <Canvas camera={{ position: [3, 2, 3], fov: 45 }} shadows>
          <color attach="background" args={["#f8fafc"]} />
          <ambientLight intensity={0.8} />
          <directionalLight position={[3, 4, 5]} intensity={1.3} castShadow />
          <ErrorBoundary fallbackMessage="Failed to load 3D model. The file might be invalid or corrupted.">
            <Suspense fallback={null}>
              <Center>
                <ShoeModel
                  url={modelUrl}
                  config={config}
                  activeLayerId={activeLayerId}
                  gizmoMode={gizmoMode}
                  onConfigChange={onConfigChange}
                  onActiveLayerChange={onActiveLayerChange}
                  onMeshBoundsUpdate={onMeshBoundsUpdate}
                />
              </Center>
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
  onConfigChange: (config: DesignConfig) => void;
  onActiveLayerChange: (id: string | null) => void;
  onMeshBoundsUpdate: (bounds: { center: [number, number, number]; size: [number, number, number] }) => void;
  gizmoMode: "translate" | "rotate" | "scale";
};

function ShoeModel({ url, config, activeLayerId, gizmoMode, onConfigChange, onActiveLayerChange, onMeshBoundsUpdate }: ShoeModelProps) {
  const gltf = useGLTF(url);
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const [, setForceRender] = useState({});

  const scale = useMemo(() => {
    if (!gltf.scene) return 1;
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    return maxDim > 0 ? 2.5 / maxDim : 1;
  }, [gltf.scene]);

  useEffect(() => {
    let maxVerts = 0;
    let bestMesh: THREE.Mesh | null = null;
    gltf.scene.traverse((node) => {
      if (node instanceof THREE.Mesh) {
        if (!bestMesh || node.geometry.attributes.position.count > maxVerts) {
          maxVerts = node.geometry.attributes.position.count;
          bestMesh = node;
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
               m.roughness = config?.material.roughness ?? 0.5;
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

    if (bestMesh && bestMesh !== meshRef.current) {
      meshRef.current = bestMesh;
      setForceRender({});
      const mesh = bestMesh as THREE.Mesh;
      mesh.geometry.computeBoundingBox();
      const box = mesh.geometry.boundingBox;
      if (box) {
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        box.getCenter(center);
        box.getSize(size);
        onMeshBoundsUpdate({
          center: [center.x, center.y, center.z],
          size: [size.x, size.y, size.z]
        });
      }
    }
  }, [config?.baseColor, config?.material.metallic, config?.material.roughness, gltf.scene, onMeshBoundsUpdate]);

  const [isDragging, setIsDragging] = useState(false);
  const [isTransforming, setIsTransforming] = useState(false);

  const updateActiveLayer = (point: THREE.Vector3, normal: THREE.Vector3) => {
    if (!config || !groupRef.current || !activeLayerId) return;

    // Convert world point to group local space
    const localPoint = groupRef.current.worldToLocal(point.clone());
    
    // Convert normal to group local space
    const normalMatrix = new THREE.Matrix3().getNormalMatrix(groupRef.current.matrixWorld);
    const localNormal = normal.clone().applyMatrix3(normalMatrix.invert()).normalize();
    
    // Offset slightly above surface to prevent z-fighting
    localPoint.add(localNormal.clone().multiplyScalar(0.01));

    const activeSticker = config.stickers.find((s) => s.id === activeLayerId);
    const activeText = config.texts.find((t) => t.id === activeLayerId);
    const activeLayer = activeSticker || activeText;
    if (!activeLayer) return;

    // Compute rotation: make plane face outward from surface
    const quaternion = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 0, 1), localNormal
    );
    const euler = new THREE.Euler().setFromQuaternion(quaternion);

    const currentZRot = activeLayer.rotation[2] || 0;
    const newPos: [number, number, number] = [localPoint.x, localPoint.y, localPoint.z];
    const newRot: [number, number, number] = [euler.x, euler.y, currentZRot];

    if (activeSticker) {
      onConfigChange({
        ...config,
        stickers: config.stickers.map((s) =>
          s.id === activeLayerId ? { ...s, position: newPos, rotation: newRot } : s
        ),
      });
    } else if (activeText) {
      onConfigChange({
        ...config,
        texts: config.texts.map((t) =>
          t.id === activeLayerId ? { ...t, position: newPos, rotation: newRot } : t
        ),
      });
    }
  };

  const handlePointerDown = (e: ThreeEvent<PointerEvent>) => {
    if (isTransforming) return;
    if (activeLayerId && e.face?.normal) {
      e.stopPropagation();
      setIsDragging(true);
      updateActiveLayer(e.point, e.face.normal);
    }
  };

  const handlePointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (isTransforming) return;
    if (isDragging && activeLayerId && e.face?.normal) {
      e.stopPropagation();
      updateActiveLayer(e.point, e.face.normal);
    }
  };

  const handlePointerUp = () => {
    setIsDragging(false);
  };

  const handlePointerMissed = () => {
    if (isDragging) setIsDragging(false);
    else onActiveLayerChange(null);
  };

  const handleTransformEnd = (id: string, isText: boolean, pos: [number, number, number], rot: [number, number, number], scale: number) => {
    setIsTransforming(false);
    if (!config) return;
    
    if (isText) {
      onConfigChange({
        ...config,
        texts: config.texts.map((t) => t.id === id ? { ...t, position: pos, rotation: rot, scale } : t)
      });
    } else {
      onConfigChange({
        ...config,
        stickers: config.stickers.map((s) => s.id === id ? { ...s, position: pos, rotation: rot, scale } : s)
      });
    }
  };

  return (
    <group
      ref={groupRef}
      scale={scale}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerMissed={handlePointerMissed}
    >
      <primitive object={gltf.scene} />
      
      {config?.stickers.map((sticker) => (
        <StickerPlane 
          key={sticker.id} 
          sticker={sticker} 
          isActive={sticker.id === activeLayerId}
          gizmoMode={gizmoMode}
          onTransformStart={() => setIsTransforming(true)}
          onTransformEnd={(pos, rot, s) => handleTransformEnd(sticker.id, false, pos, rot, s)}
        />
      ))}
      {config?.texts.map((textLayer) => (
        <TextPlane 
          key={textLayer.id} 
          layer={textLayer} 
          isActive={textLayer.id === activeLayerId}
          gizmoMode={gizmoMode}
          onTransformStart={() => setIsTransforming(true)}
          onTransformEnd={(pos, rot, s) => handleTransformEnd(textLayer.id, true, pos, rot, s)}
        />
      ))}
    </group>
  );
}

import { TransformControls, Text as DreiText } from "@react-three/drei";

function StickerPlane({ 
  sticker, 
  isActive, 
  gizmoMode, 
  onTransformStart, 
  onTransformEnd 
}: { 
  sticker: StickerLayer; 
  isActive: boolean; 
  gizmoMode: "translate" | "rotate" | "scale";
  onTransformStart: () => void;
  onTransformEnd: (pos: [number, number, number], rot: [number, number, number], scale: number) => void;
}) {
  const texture = useTexture(sticker.imageUrl);
  texture.colorSpace = THREE.SRGBColorSpace;
  const ref = useRef<THREE.Mesh>(null);
  
  const position = new THREE.Vector3(...sticker.position);
  const rotation = new THREE.Euler(...sticker.rotation);
  const scaleVec = new THREE.Vector3(sticker.scale, sticker.scale, sticker.scale);
  
  const mesh = (
    <mesh ref={ref} position={position} rotation={rotation} scale={scaleVec}>
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
  );

  if (isActive) {
    return (
      <TransformControls 
        mode={gizmoMode}
        onMouseDown={() => onTransformStart()}
        onMouseUp={() => {
          if (ref.current) {
            const p = ref.current.position;
            const r = ref.current.rotation;
            const s = ref.current.scale;
            onTransformEnd([p.x, p.y, p.z], [r.x, r.y, r.z], Math.max(s.x, s.y, s.z));
          }
        }}
      >
        {mesh}
      </TransformControls>
    );
  }

  return mesh;
}

function TextPlane({ 
  layer, 
  isActive, 
  gizmoMode, 
  onTransformStart, 
  onTransformEnd 
}: { 
  layer: TextLayer; 
  isActive: boolean; 
  gizmoMode: "translate" | "rotate" | "scale";
  onTransformStart: () => void;
  onTransformEnd: (pos: [number, number, number], rot: [number, number, number], scale: number) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const position = new THREE.Vector3(...layer.position);
  const rotation = new THREE.Euler(...layer.rotation);
  const scaleVec = new THREE.Vector3(layer.scale, layer.scale, layer.scale);
  
  const mesh = (
    <DreiText 
      ref={ref}
      position={position} 
      rotation={rotation}
      scale={scaleVec}
      color={layer.color}
      fontSize={1}
      anchorX="center"
      anchorY="middle"
    >
      {layer.value}
    </DreiText>
  );

  if (isActive) {
    return (
      <TransformControls 
        mode={gizmoMode}
        onMouseDown={() => onTransformStart()}
        onMouseUp={() => {
          if (ref.current) {
            const p = ref.current.position;
            const r = ref.current.rotation;
            const s = ref.current.scale;
            onTransformEnd([p.x, p.y, p.z], [r.x, r.y, r.z], Math.max(s.x, s.y, s.z));
          }
        }}
      >
        {mesh}
      </TransformControls>
    );
  }

  return mesh;
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
