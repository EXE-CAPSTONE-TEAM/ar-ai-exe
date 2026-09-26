from __future__ import annotations

import json

import httpx

from app.core.config import Settings
from app.services.api_cost_reporter import ApiCostReporter


def cost_reporter_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "control_plane_api_base_url": "https://control.test",
        "control_plane_mobile_service_token": "mobile-service-secret",
        "api_cost_report_timeout_seconds": 5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_reports_successful_kiri_call_with_expected_payload() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"id": "cost-1"})

    reporter = ApiCostReporter(
        settings=cost_reporter_settings(),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    reporter.report_kiri_call(
        operation="process",
        status="success",
        cost_vnd=1500,
        user_id="c908600f-d74e-42eb-af8b-36f91d8e59ae",
        reference="serial-1",
    )

    assert len(seen) == 1
    request = seen[0]
    assert request.url.path == "/api/v1/internal/api-cost/calls"
    assert request.headers["X-Service-Token"] == "mobile-service-secret"
    body = json.loads(request.content)
    assert body == {
        "user_id": "c908600f-d74e-42eb-af8b-36f91d8e59ae",
        "provider": "kiri",
        "operation": "process",
        "status": "success",
        "cost_vnd": 1500,
        "reference": "serial-1",
        "occurred_at": None,
    }


def test_reports_failed_kiri_call() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201)

    reporter = ApiCostReporter(
        settings=cost_reporter_settings(),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    reporter.report_kiri_call(
        operation="status",
        status="failed",
        cost_vnd=0,
        user_id=None,
        reference="scan_abc",
    )

    assert len(seen) == 1
    body = json.loads(seen[0].content)
    assert body["status"] == "failed"
    assert body["user_id"] is None
    assert body["reference"] == "scan_abc"


def test_control_plane_500_does_not_raise() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    reporter = ApiCostReporter(
        settings=cost_reporter_settings(),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    reporter.report_kiri_call(operation="download", status="success", cost_vnd=0)


def test_timeout_does_not_raise() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    reporter = ApiCostReporter(
        settings=cost_reporter_settings(),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    reporter.report_kiri_call(operation="download", status="failed", cost_vnd=0)


def test_unset_control_plane_base_url_skips_request() -> None:
    called = False

    def factory() -> httpx.Client:
        nonlocal called
        called = True
        raise AssertionError("client_factory should not be invoked")

    reporter = ApiCostReporter(
        settings=cost_reporter_settings(control_plane_api_base_url=""),
        client_factory=factory,
    )

    reporter.report_kiri_call(operation="process", status="success", cost_vnd=100)

    assert called is False


def test_missing_service_token_skips_request() -> None:
    def factory() -> httpx.Client:
        raise AssertionError("client_factory should not be invoked")

    reporter = ApiCostReporter(
        settings=cost_reporter_settings(control_plane_mobile_service_token=""),
        client_factory=factory,
    )

    reporter.report_kiri_call(operation="process", status="success", cost_vnd=100)
