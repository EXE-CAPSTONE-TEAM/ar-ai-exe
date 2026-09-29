from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.control_plane_mobile import (
    _EXCHANGE_RATE_LIMIT,
    _enforce_exchange_rate_limit,
    _exchange_rate_history,
    get_client_ip,
)
from app.core.config import Settings
from app.services.decal_baker import DecalBakeService


def test_settings_rejects_insecure_jwt_secret_in_production():
    with pytest.raises(ValueError, match="Insecure default jwt_secret_key"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="local-dev-jwt-secret-change-me-32bytes-min",
            enable_demo_auth=False,
        )


def test_settings_rejects_short_jwt_secret_in_production():
    with pytest.raises(ValueError, match="must be at least 32 characters"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="too-short-secret",
            enable_demo_auth=False,
        )


def test_settings_rejects_demo_auth_in_production():
    with pytest.raises(ValueError, match="enable_demo_auth must be False"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="a" * 32,
            enable_demo_auth=True,
        )


def test_settings_forces_secure_cookie_in_production():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="a" * 32,
        enable_demo_auth=False,
        auth_cookie_secure=False,
    )
    assert settings.auth_cookie_secure is True


def test_settings_allows_dev_defaults_in_local():
    settings = Settings(
        _env_file=None,
        environment="local",
        jwt_secret_key="local-dev-jwt-secret-change-me-32bytes-min",
        enable_demo_auth=True,
    )
    assert settings.environment == "local"
    assert settings.enable_demo_auth is True


def test_safe_color_validation():
    baker = DecalBakeService()
    # Invalid colors fall back to #ffffff
    assert baker._safe_color("red") == "#ffffff"
    assert baker._safe_color('red" onload="alert(1)"') == "#ffffff"
    assert baker._safe_color("#12345") == "#ffffff"  # 5 digits rejected
    assert baker._safe_color("#1234567") == "#ffffff"  # 7 digits rejected
    assert baker._safe_color("javascript:alert(1)") == "#ffffff"

    # Valid hex colors accepted
    assert baker._safe_color("#fff") == "#fff"
    assert baker._safe_color("#FFF") == "#FFF"
    assert baker._safe_color("#ffffff") == "#ffffff"
    assert baker._safe_color("#FF00AA") == "#FF00AA"
    assert baker._safe_color("#11223344") == "#11223344"  # 8 digits with alpha


def test_write_text_svg_escapes_xss_payload(tmp_path: Path):
    baker = DecalBakeService()
    payload = "</text><script>alert('xss')</script><text>"
    svg_path = baker._write_text_svg(payload, "Arial", "#ffffff", tmp_path, "test_svg")

    content = svg_path.read_text(encoding="utf-8")
    assert "<script>" not in content
    assert "</script>" not in content
    assert "&lt;/text&gt;&lt;script&gt;alert('xss')&lt;/script&gt;&lt;text&gt;" in content


def test_exchange_rate_limiter_blocks_11th_request():
    _exchange_rate_history.clear()
    client_ip = "192.0.2.100"

    # Up to _EXCHANGE_RATE_LIMIT requests succeed
    for _ in range(_EXCHANGE_RATE_LIMIT):
        _enforce_exchange_rate_limit(client_ip)

    # 11th request raises 429
    with pytest.raises(HTTPException) as exc_info:
        _enforce_exchange_rate_limit(client_ip)
    assert exc_info.value.status_code == 429
    assert "Too many compute grant exchange requests" in exc_info.value.detail


def test_get_client_ip_trusted_proxy_forwarded_for():
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"x-forwarded-for": "203.0.113.195, 10.0.0.1"}

    assert get_client_ip(request, trusted_proxies=["127.0.0.1"]) == "203.0.113.195"


def test_get_client_ip_untrusted_peer_ignores_spoofed_header():
    request = MagicMock()
    request.client.host = "198.51.100.5"
    request.headers = {"x-forwarded-for": "1.1.1.1"}

    # When peer is not in trusted_proxies, X-Forwarded-For is ignored
    assert get_client_ip(request, trusted_proxies=["127.0.0.1"]) == "198.51.100.5"


def test_exchange_rate_limiter_evicts_stale_records():
    _exchange_rate_history.clear()
    # Add an old key with timestamps outside the 60s window
    old_time = time.monotonic() - 120.0
    _exchange_rate_history["stale_client"] = [old_time]

    # Populate 101 entries to trigger eviction check (>100 entries)
    for i in range(105):
        _exchange_rate_history[f"dummy_ip_{i}"] = [old_time]

    # When a new request is made, stale keys are evicted
    _enforce_exchange_rate_limit("active_client")

    assert "stale_client" not in _exchange_rate_history
    assert "active_client" in _exchange_rate_history
