from __future__ import annotations

import json
import struct
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.capability_urls import canonical_origin
from app.core.config import Settings, get_settings
from app.schemas.control_plane_mobile import (
    ControlPlaneGrantClaimResponse,
    ControlPlaneOutputConfirmResponse,
    ControlPlaneOutputUploadResponse,
)


MAX_CONTROL_PLANE_RESPONSE_BYTES = 64 * 1024
MEBIBYTE = 1024 * 1024


class ControlPlaneMobileError(RuntimeError):
    """Safe base error for the mobile control-plane boundary."""


class ControlPlaneGrantRejected(ControlPlaneMobileError):
    pass


class ControlPlaneCompletionRejected(ControlPlaneMobileError):
    pass


class ControlPlaneConfigurationError(ControlPlaneMobileError):
    pass


class ControlPlaneUnavailable(ControlPlaneMobileError):
    pass


class ControlPlaneContractError(ControlPlaneMobileError):
    pass


@dataclass(frozen=True, slots=True)
class ControlPlanePublishResult:
    project_id: str
    model_asset_id: str
    status: str
    web_project_url: str


class ControlPlaneMobileClient:
    """Use service auth and one-object capabilities; never share storage credentials."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client_factory = client_factory or self._create_client

    def claim_compute_grant(
        self,
        compute_grant: str,
    ) -> ControlPlaneGrantClaimResponse:
        payload = self._post_json(
            "/compute-grants/claim",
            {"compute_grant": compute_grant},
        )
        try:
            return ControlPlaneGrantClaimResponse.model_validate(payload)
        except ValidationError as exc:
            raise ControlPlaneContractError("Control-plane grant response is invalid.") from exc

    def publish_glb(
        self,
        *,
        completion_token: str,
        expected_project_id: str,
        project_name: str,
        web_project_url: str,
        file_size_bytes: int,
        chunks: Iterable[bytes],
    ) -> ControlPlanePublishResult:
        max_bytes = max(1, self.settings.control_plane_max_output_size_mb) * MEBIBYTE
        if file_size_bytes < 12 or file_size_bytes > max_bytes:
            raise ControlPlaneContractError(
                "Generated GLB is empty, truncated, or exceeds the publish limit."
            )

        upload_payload = self._post_json(
            "/scans/output-upload",
            {"completion_token": completion_token},
        )
        try:
            upload = ControlPlaneOutputUploadResponse.model_validate(upload_payload)
        except ValidationError as exc:
            raise ControlPlaneContractError(
                "Control-plane upload capability response is invalid."
            ) from exc

        if str(upload.project_id) != expected_project_id:
            raise ControlPlaneContractError(
                "Control-plane upload capability targets a different project."
            )

        if not upload.already_completed:
            if not upload.upload_url:
                raise ControlPlaneContractError("Control-plane upload capability is missing.")
            self._put_glb(
                upload.upload_url,
                chunks=chunks,
                file_size_bytes=file_size_bytes,
            )

            confirm_payload = self._post_json(
                "/scans/output-confirm",
                {
                    "completion_token": completion_token,
                    "asset_id": str(upload.asset_id),
                    "file_size_bytes": file_size_bytes,
                    "project_name": project_name,
                },
            )
            try:
                confirmed = ControlPlaneOutputConfirmResponse.model_validate(confirm_payload)
            except ValidationError as exc:
                raise ControlPlaneContractError(
                    "Control-plane publish confirmation is invalid."
                ) from exc

            if (
                confirmed.project_id != upload.project_id
                or confirmed.model_asset_id != upload.asset_id
            ):
                raise ControlPlaneContractError(
                    "Control-plane publish confirmation does not match the capability."
                )
            return ControlPlanePublishResult(
                project_id=str(confirmed.project_id),
                model_asset_id=str(confirmed.model_asset_id),
                status=confirmed.status,
                web_project_url=confirmed.web_project_url,
            )

        return ControlPlanePublishResult(
            project_id=str(upload.project_id),
            model_asset_id=str(upload.asset_id),
            status="ready",
            web_project_url=web_project_url,
        )

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = self.settings.control_plane_mobile_service_token
        if not token:
            raise ControlPlaneConfigurationError(
                "Control-plane mobile service authentication is not configured."
            )
        url = f"{self._control_plane_origin()}/api/v1/internal/mobile{path}"

        try:
            with self.client_factory() as client:
                with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={"X-Service-Token": token},
                ) as response:
                    status_code = response.status_code
                    body = self._read_bounded_body(response)
        except ControlPlaneMobileError:
            raise
        except httpx.HTTPError as exc:
            raise ControlPlaneUnavailable("Control-plane mobile request failed.") from exc

        response_payload = self._decode_object(body)
        if 200 <= status_code < 300:
            return response_payload
        self._raise_control_plane_error(status_code, response_payload)
        raise AssertionError("Control-plane error classification must raise.")

    def _put_glb(
        self,
        upload_url: str,
        *,
        chunks: Iterable[bytes],
        file_size_bytes: int,
    ) -> None:
        self._require_allowed_upload_url(upload_url)
        headers = {
            "Content-Type": "model/gltf-binary",
            "Content-Length": str(file_size_bytes),
        }
        try:
            with self.client_factory() as client:
                with client.stream(
                    "PUT",
                    upload_url,
                    headers=headers,
                    content=_validated_glb_stream(chunks, file_size_bytes),
                ) as response:
                    status_code = response.status_code
                    self._read_bounded_body(response)
        except ControlPlaneMobileError:
            raise
        except httpx.HTTPError as exc:
            raise ControlPlaneUnavailable("Uploading the generated GLB failed.") from exc

        if not 200 <= status_code < 300:
            raise ControlPlaneUnavailable("The storage capability rejected the generated GLB.")

    def _control_plane_origin(self) -> str:
        value = self.settings.control_plane_api_base_url
        production = self.settings.environment.lower() in {"prod", "production"}
        try:
            return canonical_origin(
                value,
                origin_only=True,
                require_https=production,
            )
        except ValueError as exc:
            raise ControlPlaneConfigurationError(
                "Control-plane API origin is not configured safely."
            ) from exc

    def _require_allowed_upload_url(self, upload_url: str) -> None:
        production = self.settings.environment.lower() in {"prod", "production"}
        try:
            allowed_origins = {
                canonical_origin(
                    origin,
                    origin_only=True,
                    require_https=production,
                )
                for origin in self.settings.control_plane_allowed_storage_origins
            }
            upload_origin = canonical_origin(
                upload_url,
                origin_only=False,
                require_https=production,
            )
        except ValueError as exc:
            raise ControlPlaneConfigurationError(
                "Control-plane storage capability URL or allowlist is invalid."
            ) from exc
        if not allowed_origins or upload_origin not in allowed_origins:
            raise ControlPlaneConfigurationError(
                "Control-plane storage capability origin is not allowlisted."
            )

    def _create_client(self) -> httpx.Client:
        timeout_seconds = max(
            1,
            self.settings.control_plane_mobile_request_timeout_seconds,
        )
        return httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )

    @staticmethod
    def _read_bounded_body(response: httpx.Response) -> bytes:
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > MAX_CONTROL_PLANE_RESPONSE_BYTES:
                raise ControlPlaneContractError("Control-plane response exceeds the safety limit.")
        return bytes(body)

    @staticmethod
    def _decode_object(body: bytes) -> dict[str, Any]:
        try:
            value = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ControlPlaneContractError("Control-plane returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise ControlPlaneContractError("Control-plane returned an invalid response.")
        return value

    @staticmethod
    def _raise_control_plane_error(
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        error_code = payload.get("code")
        if error_code == "MOBILE_SCAN_GRANT_INVALID":
            raise ControlPlaneGrantRejected("Compute grant is invalid or expired.")
        if error_code == "MOBILE_SCAN_COMPLETION_INVALID":
            raise ControlPlaneCompletionRejected(
                "Scan completion capability is invalid or expired."
            )
        if (
            status_code >= 500
            or status_code in {408, 409, 425, 429}
            or error_code == "MOBILE_SCAN_PUBLISH_CONFLICT"
        ):
            raise ControlPlaneUnavailable(
                "Control-plane mobile operation is temporarily unavailable."
            )
        if status_code in {401, 403}:
            raise ControlPlaneConfigurationError(
                "Control-plane service authentication was rejected."
            )
        raise ControlPlaneContractError("Control-plane rejected the mobile operation.")


def _validated_glb_stream(
    chunks: Iterable[bytes],
    expected_size: int,
) -> Iterator[bytes]:
    source = iter(chunks)
    prefix = bytearray()
    pending: list[bytes] = []
    total = 0

    while len(prefix) < 12:
        try:
            raw_chunk = next(source)
        except StopIteration:
            break
        chunk = bytes(raw_chunk)
        if not chunk:
            continue
        pending.append(chunk)
        total += len(chunk)
        prefix.extend(chunk[: 12 - len(prefix)])

    if len(prefix) < 12:
        raise ControlPlaneContractError("Generated GLB is truncated.")
    magic, version, declared_length = struct.unpack("<4sII", prefix)
    if magic != b"glTF" or version != 2 or declared_length != expected_size:
        raise ControlPlaneContractError("Generated GLB header is invalid.")
    if total > expected_size:
        raise ControlPlaneContractError("Generated GLB size does not match metadata.")

    yield from pending
    for raw_chunk in source:
        chunk = bytes(raw_chunk)
        if not chunk:
            continue
        total += len(chunk)
        if total > expected_size:
            raise ControlPlaneContractError("Generated GLB size does not match metadata.")
        yield chunk
    if total != expected_size:
        raise ControlPlaneContractError("Generated GLB size does not match metadata.")
