"""Distributed telemetry and W3C TraceContext injector for hermetic testing.

Implements W3C TraceContext specification (traceparent) and correlates
test driver executions, worker requests, and headless Blender subprocesses.
Generates structured incident diagnostics upon test or bake failures.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "OK"  # "OK" or "ERROR"
    attributes: dict[str, Any] = field(default_factory=dict)
    error_details: Optional[dict[str, Any]] = None

    def finish(self, status: str = "OK", error: Optional[Exception] = None) -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0
        self.status = status
        if error is not None:
            self.error_details = {
                "type": type(error).__name__,
                "message": str(error),
                "stack": traceback.format_exc(),
            }

    def to_w3c_header(self) -> str:
        """Format as W3C traceparent header: 00-{trace_id}-{span_id}-01."""
        return f"00-{self.trace_id}-{self.span_id}-01"


class TelemetryEngine:
    """Manages trace contexts, span lifecycles, and failure incident extraction."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        if output_dir is None:
            output_dir = Path(__file__).resolve().parents[2] / ".harness" / "telemetry"
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.active_spans: list[TraceSpan] = []

    def create_root_span(self, name: str, attributes: Optional[dict[str, Any]] = None) -> TraceSpan:
        """Create a new root trace span with a cryptographically random 128-bit trace ID."""
        trace_id = secrets.token_hex(16)
        span_id = secrets.token_hex(8)
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            name=name,
            attributes=attributes or {},
        )
        return span

    @contextmanager
    def trace_scope(
        self,
        name: str,
        parent: Optional[TraceSpan] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Iterator[TraceSpan]:
        """Context manager creating a correlated span and recording execution metrics."""
        if parent:
            span = TraceSpan(
                trace_id=parent.trace_id,
                span_id=secrets.token_hex(8),
                parent_span_id=parent.span_id,
                name=name,
                attributes=attributes or {},
            )
        else:
            span = self.create_root_span(name, attributes)

        # Inject into environment so subprocesses inherit trace correlation
        os.environ["HARNESS_TRACE_ID"] = span.trace_id
        os.environ["HARNESS_SPAN_ID"] = span.span_id
        os.environ["TRACEPARENT"] = span.to_w3c_header()

        self.active_spans.append(span)
        try:
            yield span
            span.finish("OK")
        except Exception as exc:
            span.finish("ERROR", exc)
            self._record_incident(span)
            raise
        finally:
            if span in self.active_spans:
                self.active_spans.remove(span)

    def _record_incident(self, span: TraceSpan) -> Path:
        """Dump a structured incident record upon test or worker failure."""
        incident_path = self.output_dir / f"incident_{span.trace_id}.json"
        record = {
            "version": "1.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "name": span.name,
            "duration_ms": span.duration_ms,
            "status": span.status,
            "attributes": span.attributes,
            "error": span.error_details,
            "environment": {
                "python": sys.version,
                "platform": sys.platform,
                "blender_bin": os.environ.get("BLENDER_BIN", "not_set"),
            },
        }
        incident_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return incident_path
