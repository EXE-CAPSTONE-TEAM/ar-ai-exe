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
};

export function ModelViewer({ modelUrl, config, activeLayerId, onConfigChange, onActiveLayerChange }: ModelViewerProps) {
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
                  onConfigChange={onConfigChange}
                  onActiveLayerChange={onActiveLayerChange}
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
};

function ShoeModel({ url, config, activeLayerId, onConfigChange, onActiveLayerChange }: ShoeModelProps) {
  const gltf = useGLTF(url);
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);

  const scale = useMemo(() => {
    if (!gltf.scene) return 1;
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    return maxDim > 0 ? 2.5 / maxDim : 1;
  }, [gltf.scene]);

  useEffect(() => {
    let maxVerts = 0;
    gltf.scene.traverse((node) => {
      if (node instanceof THREE.Mesh) {
        if (!meshRef.current || node.geometry.attributes.position.count > maxVerts) {
          maxVerts = node.geometry.attributes.position.count;
          meshRef.current = node;
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
  }, [config?.baseColor, config?.material.metallic, config?.material.roughness, gltf.scene]);

  const [isDragging, setIsDragging] = useState(false);

  const updateActiveLayer = (point: THREE.Vector3, normal: THREE.Vector3) => {
    if (!config || !meshRef.current || !activeLayerId) return;

    // The intersection point is in world space. We need it in the mesh's local space.
    const localPoint = meshRef.current.worldToLocal(point.clone());
    
    // The normal is already in local space of the mesh geometry from the Raycaster.
    const n = normal.clone();

    const activeSticker = config.stickers.find((s) => s.id === activeLayerId);
    const activeText = config.texts.find((t) => t.id === activeLayerId);
    const activeLayer = activeSticker || activeText;
    if (!activeLayer) return;

    const dummy = new THREE.Object3D();
    dummy.position.copy(localPoint);
    dummy.lookAt(localPoint.clone().add(n));
    
    // Preserve the user's manual Z rotation if they just slide around
    // If they change normal significantly, we want it to align with normal first.
    // To prevent sudden twisting, we'll just use dummy.rotation and let the user correct Z via slider.
    
    const newPos: [number, number, number] = [localPoint.x, localPoint.y, localPoint.z];
    const newRot: [number, number, number] = [dummy.rotation.x, dummy.rotation.y, dummy.rotation.z];

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
    if (activeLayerId && e.face?.normal) {
      e.stopPropagation();
      setIsDragging(true);
      updateActiveLayer(e.point, e.face.normal);
    }
  };

  const handlePointerMove = (e: ThreeEvent<PointerEvent>) => {
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
      
      {/* Render decals as children of the main mesh via React portal-like behavior or just relying on Decal's mesh prop? 
          Wait, Drei's <Decal> uses the parent mesh if no `mesh` prop is given. 
          But here, the parent is <group>. So we MUST pass the mesh ref. 
      */}
      {meshRef.current && config?.stickers.map((sticker) => (
        <StickerDecal key={sticker.id} sticker={sticker} meshRef={meshRef as React.RefObject<THREE.Mesh>} />
      ))}
      {meshRef.current && config?.texts.map((textLayer) => (
        <TextDecal key={textLayer.id} layer={textLayer} meshRef={meshRef as React.RefObject<THREE.Mesh>} />
      ))}
    </group>
  );
}

function StickerDecal({ sticker, meshRef }: { sticker: StickerLayer; meshRef: React.RefObject<THREE.Mesh> }) {
  const texture = useTexture(sticker.imageUrl);
  
  return (
    <Decal
      mesh={meshRef}
      position={sticker.position}
      rotation={sticker.rotation}
      scale={[sticker.scale, sticker.scale, sticker.scale]} // Z scale defines projection depth
    >
      <meshStandardMaterial
        map={texture}
        transparent
        polygonOffset
        polygonOffsetFactor={-1} // Prevents z-fighting
      />
    </Decal>
  );
}

import { RenderTexture, Text as DreiText } from "@react-three/drei";

function TextDecal({ layer, meshRef }: { layer: TextLayer; meshRef: React.RefObject<THREE.Mesh> }) {
  return (
    <Decal
      mesh={meshRef}
      position={layer.position}
      rotation={layer.rotation}
      scale={[layer.scale * 2, layer.scale * 1.2, layer.scale]}
    >
      <meshStandardMaterial transparent polygonOffset polygonOffsetFactor={-1}>
        <RenderTexture attach="map" anisotropy={16}>
          <color attach="background" args={["transparent"]} />
          <Center>
            <DreiText fontSize={1} color={layer.color}>
              {layer.value}
            </DreiText>
          </Center>
        </RenderTexture>
      </meshStandardMaterial>
    </Decal>
  );
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
