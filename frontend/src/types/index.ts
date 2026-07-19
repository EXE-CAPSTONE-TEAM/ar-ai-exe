export type User = {
  id: string;
  role: string;
  name: string;
  email: string;
  createdAt: string;
  updatedAt?: string | null;
};

export type ProjectStatus = "draft" | "processing" | "ready" | "failed" | "archived";
export type AssetStatus = "uploaded" | "processing" | "ready" | "failed";
export type DesignStatus = "draft" | "published" | "archived" | "exported";
export type PreviewStatus = "none" | "pending" | "processing" | "ready" | "failed";
export type JobStatus = "queued" | "processing" | "completed" | "failed";

export type Project = {
  id: string;
  name: string;
  status: ProjectStatus;
  thumbnailUrl?: string | null;
  sourceType: "scan" | "uploaded_glb" | "uploaded_obj" | "template";
  createdAt: string;
  updatedAt: string;
};

export type CloudProject = {
  id: string;
  name: string;
  status: ProjectStatus;
  thumbnailUrl?: string | null;
  updatedAt: string;
};

export type ScanSession = {
  id: string;
  userId: string;
  projectId?: string | null;
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
  projectId?: string | null;
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

export type EditorReadiness = {
  ready: boolean;
  message: string;
  previewRenderer: {
    status: "installed" | "missing" | "failed" | string;
    available: boolean;
    path: string | null;
    message: string;
  };
  settings: Record<string, string | boolean>;
};

export type DesktopRuntime = {
  apiBaseUrl: string;
  backendStatus: "starting" | "ready" | "failed" | string;
  blenderStatus: "missing" | "downloading" | "installed" | "failed" | string;
  demoProjectStatus: "missing" | "ready" | "repairing" | "failed" | string;
  diagnosticSummary: string;
  backendPort: number;
  storagePath: string;
  blenderPath: string;
  logsPath: string;
  appVersion: string;
  lastError?: string | null;
};

export type InstallProgress = {
  name: string;
  status: "missing" | "downloading" | "installed" | "failed" | string;
  message: string;
  percent: number;
  path?: string | null;
};

export type ModelAsset = {
  id: string;
  scanSessionId: string;
  projectId?: string | null;
  status?: AssetStatus;
  sourceType?: "scan" | "uploaded_glb" | "uploaded_obj" | "template";
  glbUrl: string;
  canonicalGlbUrl?: string | null;
  objUrl: string;
  mtlUrl: string;
  textureUrl: string;
  textureUrls?: string[];
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

export type DesignAssetSource = "upload" | "canvas" | "text-render";

export type DesignAsset = {
  id: string;
  sourceType: DesignAssetSource;
  fileName: string;
  contentType: string;
  sizeBytes: number;
  checksum: string;
  downloadUrl: string;
  createdAt: string;
};

export type MaterialConfig = {
  roughness: number;
  metallic: number;
};

export type StickerLayer = {
  id: string;
  type: "image";
  source?: "preset" | "upload" | "canvas";
  imageUrl?: string;
  assetId?: string;
  previewUrl?: string;
  position: [number, number, number];
  rotation: [number, number, number];
  normal?: [number, number, number];
  targetMeshName?: string | null;
  scale: number;
  width?: number;
  height?: number;
  offset?: number;
  projectionDepth?: number;
  subdivisions?: number;
  opacity?: number;
  roughness?: number;
  metallic?: number;
  renderOrder?: number;
};

export type TextLayer = {
  id: string;
  value: string;
  font: string;
  color: string;
  renderAssetId?: string;
  position: [number, number, number];
  rotation: [number, number, number];
  normal?: [number, number, number];
  scale: number;
  width?: number;
  height?: number;
  offset?: number;
  projectionDepth?: number;
  subdivisions?: number;
  targetMeshName?: string | null;
  opacity?: number;
  roughness?: number;
  metallic?: number;
  renderOrder?: number;
};

export type DesignConfig = {
  modelAssetId: string;
  baseColor: string;
  material: MaterialConfig;
  stickers: StickerLayer[];
  texts: TextLayer[];
  camera?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type Design = {
  id: string;
  userId: string;
  projectId?: string | null;
  modelAssetId: string;
  name: string;
  status: DesignStatus | string;
  revision: number;
  designConfig: DesignConfig;
  previewGlbUrl: string | null;
  previewStatus: PreviewStatus;
  previewErrorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ExportPackage = {
  id: string;
  designId: string;
  status: string;
  downloadUrl: string;
  zipUrl?: string | null;
  files: string[];
  createdAt: string;
  updatedAt?: string | null;
};

export type EditorPermissions = {
  canEdit: boolean;
  canBake: boolean;
  canExport: boolean;
};

export type EditorContext = {
  project: Project;
  modelAsset: ModelAsset | null;
  latestDesign: Design | null;
  permissions: EditorPermissions;
};

export type Job = {
  id: string;
  type: "bake";
  status: JobStatus;
  progress: number;
  errorMessage: string | null;
  designId?: string | null;
  projectId?: string | null;
  createdAt: string;
  updatedAt: string;
};
