"""Crop box: editor (glTF, Y-up, three.js Euler XYZ) -> Blender (Z-up) cutter transform."""
import math

import pytest

from app.services.crop_math import blender_to_gltf, cutter_matrix, gltf_bounds, transform_point

# A shoe-like bounding box in glTF space: 0.30 long (x), 0.12 tall (y, up), 0.10 wide (z).
GLTF_CENTER = (0.0, 0.06, 0.0)
GLTF_SIZE = (0.30, 0.12, 0.10)
UNIT_CORNERS = [(x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]


def _crop(center=(0, 0, 0), size=(1, 1, 1), rotation=(0, 0, 0)):
    keys = ("x", "y", "z")
    return {
        "center": dict(zip(keys, center, strict=True)),
        "size": dict(zip(keys, size, strict=True)),
        "rotation": dict(zip(keys, rotation, strict=True)),
        "coordinateSpace": "normalized",
    }


def _cutter_corners_in_gltf(crop):
    matrix = cutter_matrix(crop, GLTF_CENTER, GLTF_SIZE)
    return [blender_to_gltf(transform_point(matrix, corner)) for corner in UNIT_CORNERS]


def _extent(points, axis):
    values = [p[axis] for p in points]
    return min(values), max(values)


def test_full_box_covers_exactly_the_model_bounds():
    corners = _cutter_corners_in_gltf(_crop())
    for axis in range(3):
        low, high = _extent(corners, axis)
        assert low == pytest.approx(GLTF_CENTER[axis] - GLTF_SIZE[axis] / 2)
        assert high == pytest.approx(GLTF_CENTER[axis] + GLTF_SIZE[axis] / 2)


def test_upper_half_in_the_editor_is_the_upper_half_in_blender():
    """The editor's Y (up) must land on Blender's Z (up), not on Blender's Y."""
    matrix = cutter_matrix(_crop(center=(0, 0.25, 0), size=(1, 0.5, 1)), GLTF_CENTER, GLTF_SIZE)
    blender_corners = [transform_point(matrix, corner) for corner in UNIT_CORNERS]
    z_low, z_high = _extent(blender_corners, 2)
    y_low, y_high = _extent(blender_corners, 1)
    assert z_low == pytest.approx(GLTF_CENTER[1])  # starts at mid height...
    assert z_high == pytest.approx(GLTF_CENTER[1] + GLTF_SIZE[1] / 2)  # ...up to the top
    assert y_high - y_low == pytest.approx(GLTF_SIZE[2])  # Blender Y spans the full glTF width


def test_rotation_about_the_editor_vertical_is_about_blender_z():
    matrix = cutter_matrix(_crop(rotation=(0, 90, 0)), (0, 0, 0), (1, 1, 1))
    # A point on the glTF +X face rotated 90 deg about glTF Y (up) goes to glTF -Z.
    rotated = blender_to_gltf(transform_point(matrix, (0.5, 0, 0)))
    assert rotated == pytest.approx((0, 0, -0.5), abs=1e-9)
    # In Blender coordinates that is +Y, and the height (Blender Z) is unchanged.
    assert transform_point(matrix, (0.5, 0, 0)) == pytest.approx((0, 0.5, 0), abs=1e-9)


def test_multi_axis_rotation_uses_three_js_xyz_order():
    """three.js "XYZ" is Rx·Ry·Rz; applying Rz first (Blender's order) gives a different point."""
    matrix = cutter_matrix(_crop(rotation=(90, 90, 0)), (0, 0, 0), (1, 1, 1))
    got = blender_to_gltf(transform_point(matrix, (1, 0, 0)))
    # Rx(90)·Ry(90) applied to +X: Ry(90) sends +X to -Z, then Rx(90) sends -Z to +Y.
    assert got == pytest.approx((0, 1, 0), abs=1e-9)
    # Blender's own "XYZ" (Rz·Ry·Rx) would send +X: Rx -> +X, Ry(90) -> -Z, Rz(0) -> -Z.
    blender_euler_result = (0.0, 0.0, -1.0)
    assert not all(math.isclose(g, b, abs_tol=1e-9) for g, b in zip(got, blender_euler_result, strict=True))


def test_bounds_round_trip_from_blender_corners():
    blender_corners = [
        (x, -z, y)
        for x in (GLTF_CENTER[0] - 0.15, GLTF_CENTER[0] + 0.15)
        for y in (0.0, 0.12)
        for z in (-0.05, 0.05)
    ]
    center, size = gltf_bounds(blender_corners)
    assert center == pytest.approx(GLTF_CENTER)
    assert size == pytest.approx(GLTF_SIZE)


def test_degenerate_size_is_floored_not_zero():
    matrix = cutter_matrix(_crop(size=(1, 0, 1)), GLTF_CENTER, GLTF_SIZE)
    corners = [transform_point(matrix, corner) for corner in UNIT_CORNERS]
    low, high = _extent(corners, 2)
    assert high - low > 0
