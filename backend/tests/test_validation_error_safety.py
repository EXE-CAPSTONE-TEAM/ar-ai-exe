"""Regression: validation errors must serialize even when `input` is non-JSON."""
import json

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.testclient import TestClient

from app.core.errors import validation_exception_handler
from fastapi.exceptions import RequestValidationError


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.post("/upload")
    async def upload(metadata: str = Form(...), model: UploadFile = File(...)):
        return {"ok": True}

    return app


def test_validation_error_response_is_json_serializable():
    """Sending metadata as a file should produce a 422 with a safe `input` value."""
    client = TestClient(_make_app())
    _ = client.post(
        "/upload",
        data={"metadata": "not-valid-json"},
        files={"model": ("shoe.glb", b"\x00\x00", "model/gltf-binary")},
    )
    # The above won't reproduce the original crash (the form is well-formed).
    # Reproduce the crash by calling the handler directly with a fake error.
    fake_error = RequestValidationError(
        [
            {
                "type": "string_type",
                "loc": ("body", "metadata"),
                "msg": "Input should be a valid string",
                "input": object(),  # not JSON serializable
            }
        ]
    )
    from fastapi import Request

    # Build a minimal ASGI scope for the handler call.
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 0),
        "asgi": {"version": "3.0", "spec_version": "2.0"},
    }
    request = Request(scope)
    import asyncio
    response_obj = asyncio.run(validation_exception_handler(request, fake_error))
    body = response_obj.body
    raw = body.decode("utf-8")
    # Must be valid JSON
    parsed = json.loads(raw)
    assert "UploadFile" not in raw
    assert parsed["error"]["code"] == "INVALID_REQUEST"


def test_model_validator_errors_return_422_not_500():
    """A model_validator ValueError lands in `ctx`; it must serialise (regression: POST /bake 500)."""
    from pydantic import BaseModel, model_validator

    class Contract(BaseModel):
        path: str

        @model_validator(mode="after")
        def check(self):
            raise ValueError("output capability does not match the canonical job path")

    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.post("/bake")
    async def bake(body: Contract):
        return {"ok": True}

    response = TestClient(app).post("/bake", json={"path": "x"})
    assert response.status_code == 422
    assert "canonical job path" in json.dumps(response.json())
