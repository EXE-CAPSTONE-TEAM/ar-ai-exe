import pytest

from app.services.storage import normalize_key


@pytest.mark.parametrize("key", ["../secret", "assets/../../secret", "assets/../secret"])
def test_normalize_key_rejects_parent_traversal(key: str) -> None:
    with pytest.raises(ValueError):
        normalize_key(key)


def test_normalize_key_uses_portable_relative_key() -> None:
    assert normalize_key("/projects\\proj_001\\model.glb") == "projects/proj_001/model.glb"
