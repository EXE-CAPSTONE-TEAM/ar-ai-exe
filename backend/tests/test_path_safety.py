from pathlib import Path

import pytest

from app.core.path_safety import ensure_path_within, safe_child_path


def test_safe_child_path_rejects_nested_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="direct child"):
        safe_child_path(tmp_path, "../outside.txt")


def test_ensure_path_within_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"

    with pytest.raises(ValueError, match="escapes"):
        ensure_path_within(outside, root)
