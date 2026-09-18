"""Unit tests for W3C TraceContext and distributed telemetry engine."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.telemetry.context import TelemetryEngine, TraceSpan


def test_trace_span_generates_valid_w3c_header() -> None:
    span = TraceSpan(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        parent_span_id=None,
        name="test_operation",
    )
    header = span.to_w3c_header()
    assert header == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def test_telemetry_scope_injects_environment_and_records_metrics(tmp_path: Path) -> None:
    engine = TelemetryEngine(output_dir=tmp_path)

    with engine.trace_scope("sample_task", attributes={"service": "worker"}) as span:
        assert os.environ.get("HARNESS_TRACE_ID") == span.trace_id
        assert os.environ.get("TRACEPARENT") == span.to_w3c_header()
        assert len(span.trace_id) == 32
        assert len(span.span_id) == 16

    assert span.status == "OK"
    assert span.duration_ms >= 0.0


def test_telemetry_dumps_incident_record_on_failure(tmp_path: Path) -> None:
    engine = TelemetryEngine(output_dir=tmp_path)

    with pytest.raises(ValueError, match="Synthetic test failure"):
        with engine.trace_scope("failing_bake_job", attributes={"job_id": "job-123"}):
            raise ValueError("Synthetic test failure")

    # An incident file must have been written
    incident_files = list(tmp_path.glob("incident_*.json"))
    assert len(incident_files) == 1

    incident_data = json.loads(incident_files[0].read_text(encoding="utf-8"))
    assert incident_data["status"] == "ERROR"
    assert incident_data["name"] == "failing_bake_job"
    assert incident_data["error"]["type"] == "ValueError"
    assert incident_data["error"]["message"] == "Synthetic test failure"
    assert incident_data["attributes"]["job_id"] == "job-123"
    assert "blender_bin" in incident_data["environment"]
