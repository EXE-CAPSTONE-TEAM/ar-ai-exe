from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status


CUSTOMIZABLE_ALLOW_TERMS = (
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
)

CUSTOMIZABLE_BLOCK_TERMS = (
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
)


def is_customizable_mesh_name(*names: str | None) -> bool:
    normalized_names = [normalized for name in names if (normalized := normalize_mesh_name(name))]
    if not normalized_names:
        return False
    if any(matches_any_term(name, CUSTOMIZABLE_BLOCK_TERMS) for name in normalized_names):
        return False
    return any(matches_any_term(name, CUSTOMIZABLE_ALLOW_TERMS) for name in normalized_names)


def require_customizable_target_name(value: Any, layer_label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{layer_label} must be applied to an allowed customization area before saving.",
        )

    target_name = value.strip()
    if not is_customizable_mesh_name(target_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{layer_label} targets a non-customizable shoe area.",
        )
    return target_name


def validate_design_config_customization_zones(config: dict[str, Any]) -> None:
    for collection_name in ("stickers", "texts"):
        layers = config.get(collection_name, [])
        if not isinstance(layers, list):
            continue

        for index, layer in enumerate(layers, start=1):
            if not isinstance(layer, dict) or not layer_needs_customizable_target(collection_name, layer):
                continue
            layer_id = str(layer.get("id") or f"{collection_name}_{index:03d}")
            require_customizable_target_name(layer.get("targetMeshName"), f"Layer {layer_id}")


def layer_needs_customizable_target(collection_name: str, layer: dict[str, Any]) -> bool:
    if collection_name == "stickers":
        return bool(layer.get("assetId") or layer.get("asset_id") or layer.get("imageUrl"))
    value = layer.get("value")
    return bool(layer.get("renderAssetId") or layer.get("render_asset_id") or str(value or "").strip())


def normalize_mesh_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower())


def matches_any_term(name: str, terms: tuple[str, ...]) -> bool:
    return any(term in name for term in terms)
