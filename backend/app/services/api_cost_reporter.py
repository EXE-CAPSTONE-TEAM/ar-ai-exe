from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any

import httpx

from app.core.capability_urls import canonical_origin
from app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)

# Bounds how much of the control plane's response we ever buffer; we only
# care about the status code, never the body.
MAX_API_COST_RESPONSE_BYTES = 8 * 1024

# report_kiri_call() is invoked from synchronous request paths (e.g. the
# polled GET .../kiri/status endpoint) and from the scan pipeline. The actual
# network call must never block those callers, so it runs on this small,
# bounded pool instead of the caller's thread. Bounded (rather than one
# thread per call) so a slow/unreachable ledger can't pile up unbounded
# threads under heavy polling.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api-cost-reporter")


class ApiCostReporter:
    """Best-effort client for the control-plane API cost ledger (SRS SF-14 / BR-108).

    Every method here swallows its own errors and never blocks its caller: a
    scan must never fail, retry storm, or slow down because the cost ledger
    is unreachable or misconfigured.
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
    ) -> Future[None]:
        """Fire-and-forget: the HTTP call runs on a background thread.

        Returns the `Future` so callers that need to (tests, mainly) can wait
        for completion; ordinary callers can and should ignore it.
        """
        return _EXECUTOR.submit(
            self._report_safely,
            provider="kiri",
            operation=operation,
            status=status,
            cost_vnd=cost_vnd,
            user_id=user_id,
            reference=reference,
            occurred_at=occurred_at,
        )

    def _report_safely(self, **kwargs: Any) -> None:
        try:
            self._report(**kwargs)
        except Exception:
            # Never let an unexpected bug here surface anywhere but the log.
            logger.warning("Unexpected error while reporting API cost.", exc_info=True)

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
