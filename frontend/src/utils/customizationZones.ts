const NON_TARGET_MESH_TERMS = [
  "decal",
  "text_decal",
  "svg_decal",
];

export function isCustomizableMeshName(...names: Array<string | null | undefined>): boolean {
  const normalizedNames = names.map(normalizeMeshName).filter(Boolean);
  if (normalizedNames.length === 0) {
    return false;
  }
  return !normalizedNames.some((name) => matchesAnyTerm(name, NON_TARGET_MESH_TERMS));
}

export function resolveCustomizableMeshName(
  objectName: string | null | undefined,
  geometryName: string | null | undefined,
): string | null {
  if (!isCustomizableMeshName(objectName, geometryName)) {
    return null;
  }
  return objectName || geometryName || null;
}

function normalizeMeshName(value: string | null | undefined): string {
  return (value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

function matchesAnyTerm(name: string, terms: string[]): boolean {
  return terms.some((term) => name.includes(term));
}
