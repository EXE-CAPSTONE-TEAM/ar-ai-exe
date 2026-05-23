export type User = {
  id: string;
  role: string;
  name: string;
  email: string;
  createdAt: string;
  updatedAt?: string | null;
};

export type ScanSession = {
  id: string;
  userId: string;
  status: string;
  sourceType: "scan" | "import";
  importName: string | null;
  errorMessage: string | null;
  modelAssetId: string | null;
  webDesignUrl: string | null;
  uploadedPasses: string[];
  requiredPasses: string[];
  createdAt: string;
  updatedAt: string;
};

export type ScanStatus = {
  id: string;
  status: string;
  sourceType: "scan" | "import";
  importName: string | null;
  errorMessage: string | null;
  modelAssetId: string | null;
  updatedAt: string;
};

export type ScanMetadata = {
  shoe: {
    sizeSystem: "EU" | "US" | "UK" | "CM";
    size: string;
    side: "left" | "right" | "both";
    type: "sneaker" | "running" | "boot" | "sandal" | "other";
    material: "canvas" | "leather" | "synthetic" | "mesh" | "unknown";
    condition: string;
  };
  measurements: {
    lengthCm: number;
    widthCm: number;
  };
  scanSetup: {
    calibrationReference: string;
    lighting: string;
    background: string;
  };
  customizationGoal: string[];
};

export type ReconstructionToolStatus = {
  name: string;
  required: boolean;
  available: boolean;
  path: string | null;
  configuredValue: string;
  hint: string;
};

export type ReconstructionResourceStatus = {
  name: string;
  ok: boolean;
  available: number | null;
  required: number;
  unit: string;
  message: string;
};

export type ReconstructionReadiness = {
  ready: boolean;
  message: string;
  tools: ReconstructionToolStatus[];
  resources: ReconstructionResourceStatus[];
  settings: Record<string, string | number | boolean>;
  missingTools: string[];
  blockingReasons: string[];
};

export type ModelAsset = {
  id: string;
  scanSessionId: string;
  glbUrl: string;
  objUrl: string;
  mtlUrl: string;
  textureUrl: string;
  metadataUrl: string;
  qualityReportUrl: string;
  objPackageZipUrl: string;
  qualityReport: Record<string, unknown>;
  createdAt: string;
  updatedAt?: string | null;
};

export type ModelImportResponse = {
  scanSession: ScanSession;
  modelAsset: ModelAsset;
};

export type MaterialConfig = {
  roughness: number;
  metallic: number;
};

export type StickerLayer = {
  id: string;
  type: "image";
  imageUrl: string;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
};

export type TextLayer = {
  id: string;
  value: string;
  font: string;
  color: string;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
};

export type DesignConfig = {
  modelAssetId: string;
  baseColor: string;
  material: MaterialConfig;
  stickers: StickerLayer[];
  texts: TextLayer[];
};

export type Design = {
  id: string;
  userId: string;
  modelAssetId: string;
  name: string;
  status: string;
  designConfig: DesignConfig;
  createdAt: string;
  updatedAt: string;
};

export type ExportPackage = {
  id: string;
  designId: string;
  status: string;
  downloadUrl: string;
  files: string[];
  createdAt: string;
  updatedAt?: string | null;
};
