from app.services.customization_zones import (
    is_customizable_mesh_name,
    require_customizable_target_name,
    validate_design_config_customization_zones,
)


def test_mesh_target_detection_allows_arbitrary_model_mesh_names() -> None:
    assert is_customizable_mesh_name("shoe_upper_left")
    assert is_customizable_mesh_name("TonguePanel")
    assert is_customizable_mesh_name("heel_counter_mesh")
    assert is_customizable_mesh_name("mesh_001")
    assert is_customizable_mesh_name("outsole")
    assert is_customizable_mesh_name("logo_upper")


def test_mesh_target_detection_ignores_generated_decal_meshes() -> None:
    assert not is_customizable_mesh_name("decal_sticker_001")
    assert not is_customizable_mesh_name("svg_decal_logo")
    assert not is_customizable_mesh_name("text_decal_name")


def test_require_customizable_target_normalizes_missing_or_arbitrary_target() -> None:
    assert require_customizable_target_name(None, "Layer sticker_001") == ""
    assert require_customizable_target_name("outsole", "Layer sticker_001") == "outsole"


def test_validate_design_config_accepts_content_layers_with_arbitrary_targets() -> None:
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


def test_validate_design_config_accepts_unapplied_content_layer() -> None:
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
