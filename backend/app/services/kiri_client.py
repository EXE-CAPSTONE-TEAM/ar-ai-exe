from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings


class KiriError(RuntimeError):
    pass


class KiriApiClient:
    def __init__(self, client: httpx.Client | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client

    def upload_video(self, video_path: Path) -> str:
        if not self.settings.kiri_api_token:
            raise KiriError("KIRI_API_TOKEN is not configured.")
        with video_path.open("rb") as video_file:
            response = self._request(
                "POST",
                "/v1/open/photo/video",
                files={"videoFile": (video_path.name, video_file, "video/mp4")},
                data={
                    "modelQuality": "0",
                    "textureQuality": "1",
                    "fileFormat": "glb",
                    "isBbox": "false",
                },
            )
        payload = self._payload(response)
        serialize = (payload.get("data") or {}).get("serialize")
        if not serialize:
            raise KiriError("Kiri upload response did not include a serialize id.")
        return str(serialize)

    def get_status(self, serialize: str) -> str:
        response = self._request("GET", "/v1/open/model/getStatus", params={"serialize": serialize})
        payload = self._payload(response)
        provider_status = (payload.get("data") or {}).get("status")
        if not provider_status:
            raise KiriError("Kiri status response did not include a status.")
        return str(provider_status).strip().lower()

    def get_model_zip_url(self, serialize: str) -> str:
        response = self._request(
            "POST",
            "/v1/open/model/getModelZip",
            json={"serialize": serialize},
        )
        payload = self._payload(response)
        model_url = (payload.get("data") or {}).get("modelUrl")
        if not model_url:
            raise KiriError("Kiri download response did not include a model URL.")
        self._validate_download_url(str(model_url))
        return str(model_url)

    def download_model_zip(self, model_url: str) -> bytes:
        self._validate_download_url(model_url)
        max_bytes = self.settings.kiri_max_download_size_mb * 1024 * 1024
        client = self.client or httpx.Client(timeout=self.settings.kiri_request_timeout_seconds)
        close_client = self.client is None
        try:
            with client.stream("GET", model_url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise KiriError(
                            f"Kiri model ZIP exceeds {self.settings.kiri_max_download_size_mb} MB."
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
        except httpx.HTTPError as exc:
            raise KiriError(f"Kiri model download failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.settings.kiri_api_base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.settings.kiri_api_token}"
        client = self.client or httpx.Client(timeout=self.settings.kiri_request_timeout_seconds)
        close_client = self.client is None
        try:
            response = client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise KiriError(f"Kiri API request failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    @staticmethod
    def _payload(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise KiriError("Kiri API returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise KiriError("Kiri API returned an invalid response.")
        if payload.get("code") not in (None, 0, "0"):
            message = payload.get("msg") or payload.get("message") or "Kiri API request failed."
            raise KiriError(str(message))
        return payload

    def _validate_download_url(self, raw_url: str) -> None:
        parsed = urlparse(raw_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            raise KiriError("Kiri model URL must use HTTPS.")
        allowed = [value.strip().lower().lstrip(".") for value in self.settings.kiri_download_allowed_hosts]
        if not any(host == value or host.endswith(f".{value}") for value in allowed if value):
            raise KiriError("Kiri model URL host is not allowlisted.")
