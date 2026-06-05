import pytest
from fastapi import HTTPException, status

from app.services.customization_zones import (
    is_customizable_mesh_name,
    require_customizable_target_name,
    validate_design_config_customization_zones,
)


def test_mesh_whitelist_allows_customizable_names() -> None:
    assert is_customizable_mesh_name("shoe_upper_left")
    assert is_customizable_mesh_name("TonguePanel")
    assert is_customizable_mesh_name("heel_counter_mesh")


def test_mesh_whitelist_blocks_protected_names_and_block_wins() -> None:
    assert not is_customizable_mesh_name("outsole")
    assert not is_customizable_mesh_name("lace_panel")
    assert not is_customizable_mesh_name("logo_upper")
    assert not is_customizable_mesh_name("mesh_001")


def test_require_customizable_target_rejects_missing_or_blocked_target() -> None:
    with pytest.raises(HTTPException) as missing_exc:
        require_customizable_target_name(None, "Layer sticker_001")

    assert missing_exc.value.status_code == status.HTTP_400_BAD_REQUEST

    with pytest.raises(HTTPException) as blocked_exc:
        require_customizable_target_name("outsole", "Layer sticker_001")

    assert blocked_exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_validate_design_config_requires_targets_for_content_layers() -> None:
    config = {
        "stickers": [
            {
                "id": "sticker_001",
                "imageUrl": "data:image/png;base64,abc",
                "targetMeshName": "upper_panel",
            }
        ],
        "texts": [
            {
                "id": "text_001",
                "value": "KUS",
                "targetMeshName": "tongue_panel",
            }
        ],
    }

    validate_design_config_customization_zones(config)


def test_validate_design_config_rejects_unapplied_content_layer() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_design_config_customization_zones(
            {
                "stickers": [
                    {
                        "id": "sticker_001",
                        "imageUrl": "data:image/png;base64,abc",
                        "targetMeshName": None,
                    }
                ]
            }
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
