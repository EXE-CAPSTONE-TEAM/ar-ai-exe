import { Center, Grid, OrbitControls, Text, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense, useEffect, useMemo } from "react";
import * as THREE from "three";

import type { DesignConfig, StickerLayer, TextLayer } from "../../types";
import { ErrorBoundary } from "../Layout/ErrorBoundary";

type ModelViewerProps = {
  modelUrl: string | null;
  config: DesignConfig | null;
};

export function ModelViewer({ modelUrl, config }: ModelViewerProps) {
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
                <ShoeModel url={modelUrl} config={config} />
                {config?.stickers.map((sticker) => <Sticker key={sticker.id} sticker={sticker} />)}
                {config?.texts.map((textLayer) => <TextDecal key={textLayer.id} layer={textLayer} />)}
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

function ShoeModel({ url, config }: { url: string; config: DesignConfig | null }) {
  const gltf = useGLTF(url);

  const scale = useMemo(() => {
    if (!gltf.scene) return 1;
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    // Target size is roughly 2.5 units to fit nicely in the 5x5 grid
    return maxDim > 0 ? 2.5 / maxDim : 1;
  }, [gltf.scene]);

  useEffect(() => {
    gltf.scene.traverse((node) => {
      if (node instanceof THREE.Mesh) {
        if (!node.userData.originalMaterial) {
          // Clone the original material to preserve maps (diffuse, normal, etc.)
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

  return <primitive object={gltf.scene} scale={scale} />;
}

function Sticker({ sticker }: { sticker: StickerLayer }) {
  return (
    <mesh position={sticker.position} rotation={sticker.rotation} scale={sticker.scale}>
      <planeGeometry args={[1, 0.6]} />
      <meshStandardMaterial color="#ef4444" side={THREE.DoubleSide} />
    </mesh>
  );
}

function TextDecal({ layer }: { layer: TextLayer }) {
  return (
    <Text
      position={layer.position}
      rotation={layer.rotation}
      scale={layer.scale}
      color={layer.color}
      anchorX="center"
      anchorY="middle"
      fontSize={1}
    >
      {layer.value}
    </Text>
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
