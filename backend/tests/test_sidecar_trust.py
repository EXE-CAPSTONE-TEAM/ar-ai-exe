"""Sidecar trust boundary (KusShoes spec §E.4, §E.5, §F — Ticket-05)."""
import asyncio
import hashlib
import hmac
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import worker
from app.core.config import Settings
from app.main import app
from app.services.desktop_download import DesktopDownloadService, safe_filename

TOKEN = "launch-token-" + "a" * 51
NONCE = "0123456789abcdef" * 4
STORAGE = "https://acct.r2.cloudflarestorage.com"


def _settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "control_plane_service_token": TOKEN,
        "worker_allowed_storage_origins": [STORAGE],
        "worker_max_output_size_mb": 1,
    }
    values.update(overrides)
    return Settings(**values)


# --- handshake ------------------------------------------------------------------------------


def test_handshake_proves_the_token_without_revealing_it(monkeypatch) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(control_plane_service_token=TOKEN))

    response = asyncio.run(worker.handshake(NONCE))

    expected = hmac.new(TOKEN.encode(), NONCE.encode(), hashlib.sha256).hexdigest()
    assert response.proof == expected
    assert TOKEN not in response.model_dump_json()


def test_handshake_proof_differs_per_nonce_and_per_token(monkeypatch) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(control_plane_service_token=TOKEN))
    first = asyncio.run(worker.handshake(NONCE)).proof
    second = asyncio.run(worker.handshake("f" * 64)).proof
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(control_plane_service_token=TOKEN + "x"))
    other_token = asyncio.run(worker.handshake(NONCE)).proof

    assert len({first, second, other_token}) == 3


@pytest.mark.parametrize(("token", "nonce", "status"), [("", NONCE, 503), (TOKEN, "short", 422), (TOKEN, "Z" * 64, 422)])
def test_handshake_rejects_unconfigured_token_or_bad_nonce(monkeypatch, token, nonce, status) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(control_plane_service_token=token))
    with pytest.raises(HTTPException) as error:
        asyncio.run(worker.handshake(nonce))
    assert error.value.status_code == status


# --- CORS -----------------------------------------------------------------------------------


@pytest.mark.parametrize("origin", ["http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"])
def test_packaged_tauri_origins_pass_cors(origin) -> None:
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == origin


def test_foreign_origin_does_not_pass_cors() -> None:
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


# --- downloads ------------------------------------------------------------------------------


def _service(tmp_path: Path, handler, **overrides) -> DesktopDownloadService:
    transport = httpx.MockTransport(handler)
    return DesktopDownloadService(
        settings=_settings(**overrides),
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        downloads_dir=tmp_path,
    )


def test_download_streams_into_the_downloads_folder_without_overwriting(tmp_path) -> None:
    body = b"glTF" + b"\0" * 60
    service = _service(tmp_path, lambda request: httpx.Response(200, content=body))
    url = f"{STORAGE}/kusshoes/exports/p/j/final_shoe.glb?X-Amz-Signature=x"

    first, size = asyncio.run(service.download(url=url, filename="kusshoes-shoe.glb"))
    second, _ = asyncio.run(service.download(url=url, filename="kusshoes-shoe.glb"))

    assert first == tmp_path / "kusshoes-shoe.glb"
    assert second == tmp_path / "kusshoes-shoe (1).glb"
    assert size == len(body) and first.read_bytes() == body
    assert not list(tmp_path.glob(".kusshoes-*.part"))  # temp files never left behind


def test_download_filename_cannot_escape_the_folder(tmp_path) -> None:
    service = _service(tmp_path, lambda request: httpx.Response(200, content=b"PK\x03\x04data"))
    path, _ = asyncio.run(
        service.download(url=f"{STORAGE}/kusshoes/x.zip", filename="..\\..\\Windows/evil.zip")
    )
    assert path.parent == tmp_path
    assert path.name == "evil.zip"


@pytest.mark.parametrize("filename", ["shoe.exe", "shoe", "..", "shoe.glb.bat"])
def test_download_rejects_unexpected_file_types(filename) -> None:
    with pytest.raises(HTTPException) as error:
        safe_filename(filename)
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/kusshoes/x.glb",
        "http://acct.r2.cloudflarestorage.com/kusshoes/x.glb",  # scheme is part of the origin
        "https://user:pass@acct.r2.cloudflarestorage.com/kusshoes/x.glb",
    ],
)
def test_download_rejects_non_allowlisted_storage(tmp_path, url) -> None:
    calls: list[httpx.Request] = []
    service = _service(tmp_path, lambda request: calls.append(request) or httpx.Response(200, content=b"x"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.download(url=url, filename="shoe.glb"))
    assert error.value.status_code == 422
    assert calls == []  # nothing was fetched


def test_download_over_the_size_limit_leaves_no_file(tmp_path) -> None:
    too_big = b"\0" * (1024 * 1024 + 1)  # worker_max_output_size_mb=1 in _settings
    service = _service(tmp_path, lambda request: httpx.Response(200, content=too_big))
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.download(url=f"{STORAGE}/kusshoes/x.glb", filename="shoe.glb"))
    assert error.value.status_code == 502
    assert list(tmp_path.iterdir()) == []


def test_download_endpoint_requires_the_launch_token() -> None:
    client = TestClient(app)
    response = client.post("/downloads", json={"url": f"{STORAGE}/k/x.glb", "filename": "x.glb"})
    assert response.status_code in {401, 503}
