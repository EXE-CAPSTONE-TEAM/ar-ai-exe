from __future__ import annotations

import re
from typing import Any

NON_TARGET_MESH_TERMS = (
    "decal",
    "text_decal",
    "svg_decal",
)


def is_customizable_mesh_name(*names: str | None) -> bool:
    normalized_names = [normalized for name in names if (normalized := normalize_mesh_name(name))]
    if not normalized_names:
        return False
    return not any(matches_any_term(name, NON_TARGET_MESH_TERMS) for name in normalized_names)


def require_customizable_target_name(value: Any, layer_label: str) -> str:
    del layer_label
    if not isinstance(value, str) or not value.strip():
        return ""
    return value.strip()


def validate_design_config_customization_zones(config: dict[str, Any]) -> None:
    del config


def layer_needs_customizable_target(collection_name: str, layer: dict[str, Any]) -> bool:
    if collection_name == "stickers":
        return bool(layer.get("assetId") or layer.get("asset_id") or layer.get("imageUrl"))
    value = layer.get("value")
    return bool(layer.get("renderAssetId") or layer.get("render_asset_id") or str(value or "").strip())


def normalize_mesh_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower())


def matches_any_term(name: str, terms: tuple[str, ...]) -> bool:
    return any(term in name for term in terms)
