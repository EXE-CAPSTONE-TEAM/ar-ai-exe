from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from app.core.capability_urls import canonical_origin
from app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)

# Bounds how much of the control plane's response we ever buffer; we only
# care about the status code, never the body.
MAX_API_COST_RESPONSE_BYTES = 8 * 1024


class ApiCostReporter:
    """Best-effort client for the control-plane API cost ledger (SRS SF-14 / BR-108).

    Every method here swallows its own errors: a scan must never fail, retry
    storm, or slow down because the cost ledger is unreachable or misconfigured.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client_factory = client_factory or self._create_client

    def report_kiri_call(
        self,
        *,
        operation: str,
        status: str,
        cost_vnd: int,
        user_id: str | None = None,
        reference: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        self._report(
            provider="kiri",
            operation=operation,
            status=status,
            cost_vnd=cost_vnd,
            user_id=user_id,
            reference=reference,
            occurred_at=occurred_at,
        )

    def _report(
        self,
        *,
        provider: str,
        operation: str,
        status: str,
        cost_vnd: int,
        user_id: str | None,
        reference: str | None,
        occurred_at: datetime | None,
    ) -> None:
        base_url = self.settings.control_plane_api_base_url
        if not base_url:
            # No control plane configured (e.g. local dev): skip silently.
            return

        token = self.settings.control_plane_mobile_service_token
        if not token:
            logger.warning(
                "Skipping API cost report for provider=%s operation=%s: "
                "control-plane service token is not configured.",
                provider,
                operation,
            )
            return

        try:
            origin = canonical_origin(
                base_url,
                origin_only=True,
                require_https=self.settings.environment.lower() in {"prod", "production"},
            )
        except ValueError:
            logger.warning(
                "Skipping API cost report for provider=%s operation=%s: "
                "control-plane API base URL is invalid.",
                provider,
                operation,
            )
            return

        payload: dict[str, Any] = {
            "user_id": user_id,
            "provider": provider[:30],
            "operation": operation[:50],
            "status": status,
            "cost_vnd": max(0, cost_vnd),
            "reference": reference[:100] if reference else None,
            "occurred_at": occurred_at.isoformat() if occurred_at else None,
        }

        try:
            with self.client_factory() as client:
                with client.stream(
                    "POST",
                    f"{origin}/api/v1/internal/api-cost/calls",
                    json=payload,
                    headers={"X-Service-Token": token},
                ) as response:
                    status_code = response.status_code
                    self._drain_bounded(response)
        except httpx.HTTPError:
            logger.warning(
                "API cost report failed for provider=%s operation=%s.",
                provider,
                operation,
                exc_info=True,
            )
            return

        if status_code != 201:
            logger.warning(
                "API cost report rejected for provider=%s operation=%s: status=%s.",
                provider,
                operation,
                status_code,
            )

    def _create_client(self) -> httpx.Client:
        timeout_seconds = max(1, self.settings.api_cost_report_timeout_seconds)
        return httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )

    @staticmethod
    def _drain_bounded(response: httpx.Response) -> None:
        read = 0
        for chunk in response.iter_bytes():
            read += len(chunk)
            if read > MAX_API_COST_RESPONSE_BYTES:
                break
