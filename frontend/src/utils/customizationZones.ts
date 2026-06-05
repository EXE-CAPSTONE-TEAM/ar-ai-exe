const CUSTOMIZABLE_ALLOW_TERMS = [
  "upper",
  "vamp",
  "quarter",
  "toe",
  "toe_box",
  "heel",
  "counter",
  "tongue",
  "side",
  "panel",
  "body",
];

const CUSTOMIZABLE_BLOCK_TERMS = [
  "sole",
  "outsole",
  "midsole",
  "lace",
  "laces",
  "eyelet",
  "hardware",
  "zipper",
  "logo",
  "decal",
  "text_decal",
  "svg_decal",
  "ground",
];

export function isCustomizableMeshName(...names: Array<string | null | undefined>): boolean {
  const normalizedNames = names.map(normalizeMeshName).filter(Boolean);
  if (normalizedNames.length === 0) {
    return false;
  }
  if (normalizedNames.some((name) => matchesAnyTerm(name, CUSTOMIZABLE_BLOCK_TERMS))) {
    return false;
  }
  return normalizedNames.some((name) => matchesAnyTerm(name, CUSTOMIZABLE_ALLOW_TERMS));
}

export function resolveCustomizableMeshName(
  objectName: string | null | undefined,
  geometryName: string | null | undefined,
): string | null {
  if (!isCustomizableMeshName(objectName, geometryName)) {
    return null;
  }
  if (objectName && matchesAnyTerm(normalizeMeshName(objectName), CUSTOMIZABLE_ALLOW_TERMS)) {
    return objectName;
  }
  return geometryName || objectName || null;
}

function normalizeMeshName(value: string | null | undefined): string {
  return (value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

function matchesAnyTerm(name: string, terms: string[]): boolean {
  return terms.some((term) => name.includes(term));
}
