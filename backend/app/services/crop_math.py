"""Crop-box maths shared by the Blender crop script and its tests (pure Python, no bpy/mathutils).

Contract (KusShoes spec §E.2, Ticket-09): the desktop editor edits the crop box in the glTF / three.js
model space, which is **Y-up**. ``center`` and ``size`` are fractions of the model's axis-aligned
bounding box in that space (centre in [-0.5, 0.5], size in (0.01, 1]); ``rotation`` is in degrees
with three.js' default Euler order ``"XYZ"``, whose matrix is ``Rx · Ry · Rz``.

Blender imports glTF into a **Z-up** world by rotating +90° about X, i.e. glTF ``(x, y, z)`` becomes
Blender ``(x, -z, y)``. Blender's own ``rotation_euler`` "XYZ" means ``Rz · Ry · Rx`` — a different
product — so the cutter transform is built here as an explicit matrix instead of Euler angles.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

Matrix = list[list[float]]
Vector3 = tuple[float, float, float]

# glTF (Y-up) -> Blender (Z-up): rotation of +90 degrees about X, exactly what the glTF importer applies.
GLTF_TO_BLENDER: Matrix = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, -1.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]
# Floor on a cutter dimension so a degenerate box never produces a zero-volume Boolean operand.
MIN_CUTTER_SIZE = 1e-6


def matmul(a: Matrix, b: Matrix) -> Matrix:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transform_point(m: Matrix, point: Sequence[float]) -> Vector3:
    x, y, z = point
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


def blender_to_gltf(point: Sequence[float]) -> Vector3:
    """Inverse of GLTF_TO_BLENDER: Blender (x, y, z) -> glTF (x, z, -y)."""
    x, y, z = point
    return (x, z, -y)


def _rotation(axis: str, degrees: float) -> Matrix:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    if axis == "x":
        return [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]]
    if axis == "y":
        return [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]
    return [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def gltf_bounds(blender_world_corners: Iterable[Sequence[float]]) -> tuple[Vector3, Vector3]:
    """Axis-aligned bounds (centre, size) in glTF space from Blender world-space bbox corners."""
    points = [blender_to_gltf(corner) for corner in blender_world_corners]
    if not points:
        raise ValueError("no geometry to bound")
    lows = tuple(min(p[i] for p in points) for i in range(3))
    highs = tuple(max(p[i] for p in points) for i in range(3))
    center = tuple((lows[i] + highs[i]) * 0.5 for i in range(3))
    size = tuple(highs[i] - lows[i] for i in range(3))
    return center, size  # type: ignore[return-value]


def cutter_matrix(crop: dict, bounds_center: Vector3, bounds_size: Vector3) -> Matrix:
    """Blender world matrix for a unit cube (size 1, centred at origin) that becomes the crop box."""
    center, size = crop["center"], crop["size"]
    rotation = crop.get("rotation") or {"x": 0.0, "y": 0.0, "z": 0.0}
    axes = ("x", "y", "z")
    location = [bounds_center[i] + float(center[a]) * bounds_size[i] for i, a in enumerate(axes)]
    scale = [max(bounds_size[i] * float(size[a]), MIN_CUTTER_SIZE) for i, a in enumerate(axes)]

    translate: Matrix = [
        [1, 0, 0, location[0]],
        [0, 1, 0, location[1]],
        [0, 0, 1, location[2]],
        [0, 0, 0, 1],
    ]
    # three.js Euler order "XYZ" -> Rx · Ry · Rz
    rotate = matmul(
        matmul(_rotation("x", float(rotation["x"])), _rotation("y", float(rotation["y"]))),
        _rotation("z", float(rotation["z"])),
    )
    stretch: Matrix = [[scale[0], 0, 0, 0], [0, scale[1], 0, 0], [0, 0, scale[2], 0], [0, 0, 0, 1]]
    return matmul(GLTF_TO_BLENDER, matmul(translate, matmul(rotate, stretch)))
