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
  errorMessage: string | null;
  modelAssetId: string | null;
  webDesignUrl: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ScanStatus = {
  id: string;
  status: string;
  errorMessage: string | null;
  modelAssetId: string | null;
  updatedAt: string;
};

export type ModelAsset = {
  id: string;
  scanSessionId: string;
  glbUrl: string;
  objUrl: string;
  mtlUrl: string;
  textureUrl: string;
  qualityReportUrl: string;
  qualityReport: Record<string, unknown>;
  createdAt: string;
  updatedAt?: string | null;
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
