from __future__ import annotations

from pathlib import Path


def ensure_path_within(path: Path, root: Path, *, label: str = "path") -> Path:
    """Resolve a path and assert it stays inside root."""
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"{label} escapes the allowed directory.")
    return resolved_path


def safe_child_path(root: Path, name: str, *, label: str = "path") -> Path:
    child_name = Path(name)
    if child_name.is_absolute() or child_name.name != name:
        raise ValueError(f"{label} must be a direct child path.")
    return ensure_path_within(root / child_name, root, label=label)


def resolve_existing_file(
    path: Path,
    *,
    allowed_suffixes: set[str] | None = None,
    label: str = "file",
) -> Path:
    resolved_path = path.expanduser().resolve(strict=True)
    if not resolved_path.is_file():
        raise ValueError(f"{label} is not a file.")
    if allowed_suffixes and resolved_path.suffix.lower() not in allowed_suffixes:
        allowed = ", ".join(sorted(allowed_suffixes))
        raise ValueError(f"{label} must use one of these extensions: {allowed}.")
    return resolved_path
