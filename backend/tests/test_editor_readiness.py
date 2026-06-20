from types import SimpleNamespace

from app.services.editor_readiness import EditorReadinessService


def test_editor_readiness_reports_blender_ready_without_reconstruction_toolchain(monkeypatch) -> None:
    settings = SimpleNamespace(
        blender_bin="blender",
        environment="desktop",
        enable_real_reconstruction=False,
        enable_inline_bake_fallback=True,
    )
    monkeypatch.setattr("app.services.editor_readiness.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.editor_readiness.shutil.which", lambda _value: "C:/Tools/blender/blender.exe")

    readiness = EditorReadinessService().check()

    assert readiness["ready"] is True
    assert readiness["previewRenderer"]["available"] is True
    assert "COLMAP" not in str(readiness)
    assert "OpenMVS" not in str(readiness)


def test_editor_readiness_reports_blender_missing_without_blocking_model_view(monkeypatch) -> None:
    settings = SimpleNamespace(
        blender_bin="C:/Missing/blender.exe",
        environment="desktop",
        enable_real_reconstruction=False,
        enable_inline_bake_fallback=True,
    )
    monkeypatch.setattr("app.services.editor_readiness.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.editor_readiness.shutil.which", lambda _value: None)

    readiness = EditorReadinessService().check()

    assert readiness["ready"] is False
    assert readiness["previewRenderer"]["status"] == "missing"
    assert "open models" in readiness["message"]
    assert "COLMAP" not in str(readiness)
