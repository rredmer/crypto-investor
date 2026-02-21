"""Tests for observability stack — request ID middleware, JSON logging, exception handler."""

import json  # noqa: I001
import logging

import pytest
from django.test import Client


# ── safe_int ──────────────────────────────────────────────────


class TestSafeInt:
    def test_none_returns_default(self):
        from core.utils import safe_int

        assert safe_int(None, 50) == 50

    def test_valid_int_string(self):
        from core.utils import safe_int

        assert safe_int("25", 50) == 25

    def test_clamps_to_min(self):
        from core.utils import safe_int

        assert safe_int("0", 50, min_val=1) == 1

    def test_clamps_to_max(self):
        from core.utils import safe_int

        assert safe_int("9999", 50, max_val=200) == 200

    def test_invalid_string_returns_default(self):
        from core.utils import safe_int

        assert safe_int("abc", 50) == 50

    def test_empty_string_returns_default(self):
        from core.utils import safe_int

        assert safe_int("", 50) == 50


# ── RequestIDMiddleware ───────────────────────────────────────


@pytest.mark.django_db
class TestRequestIDMiddleware:
    def test_generates_request_id_header(self, authenticated_client):
        resp = authenticated_client.get("/api/health/")
        assert "X-Request-ID" in resp
        assert len(resp["X-Request-ID"]) == 12

    def test_respects_incoming_request_id(self, authenticated_client):
        resp = authenticated_client.get("/api/health/", HTTP_X_REQUEST_ID="custom-rid-123")
        assert resp["X-Request-ID"] == "custom-rid-123"

    def test_different_requests_get_different_ids(self, authenticated_client):
        r1 = authenticated_client.get("/api/health/")
        r2 = authenticated_client.get("/api/health/")
        assert r1["X-Request-ID"] != r2["X-Request-ID"]

    def test_unauthenticated_still_gets_request_id(self):
        client = Client()
        resp = client.get("/api/health/")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp


# ── JSONFormatter ─────────────────────────────────────────────


class TestJSONFormatter:
    def test_outputs_valid_json(self):
        from core.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["msg"] == "hello world"

    def test_includes_timestamp(self):
        from core.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="ts test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "ts" in parsed
        assert parsed["ts"].endswith("Z")

    def test_includes_request_id_from_contextvar(self):
        from core.logging import JSONFormatter, request_id_var

        token = request_id_var.set("test-rid-abc")
        try:
            formatter = JSONFormatter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="with rid",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["request_id"] == "test-rid-abc"
        finally:
            request_id_var.reset(token)

    def test_includes_extra_fields(self):
        from core.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="extra",
            args=(),
            exc_info=None,
        )
        record.method = "GET"
        record.path = "/api/test/"
        record.status = 200
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["method"] == "GET"
        assert parsed["path"] == "/api/test/"
        assert parsed["status"] == 200

    def test_includes_exception_info(self):
        from core.logging import JSONFormatter

        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="error",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError: boom" in parsed["exception"]


# ── Custom Exception Handler ──────────────────────────────────


class TestExceptionHandler:
    def test_normalize_detail_dict(self):
        from core.exception_handler import _normalize

        result = _normalize({"detail": "Not found."}, 404)
        assert result == {"error": "Not found.", "status_code": 404}

    def test_normalize_field_errors(self):
        from core.exception_handler import _normalize

        result = _normalize({"symbol": ["This field is required."]}, 400)
        assert result["error"] == "Validation failed"
        assert result["fields"]["symbol"] == ["This field is required."]
        assert result["status_code"] == 400

    def test_normalize_preserves_existing_error_key(self):
        from core.exception_handler import _normalize

        result = _normalize({"error": "Custom error", "extra": "data"}, 400)
        assert result["error"] == "Custom error"
        assert result["status_code"] == 400

    def test_normalize_string_data(self):
        from core.exception_handler import _normalize

        result = _normalize("raw error string", 500)
        assert result["error"] == "raw error string"
        assert result["status_code"] == 500

    def test_handler_normalizes_drf_404(self, authenticated_client):
        """A real 404 should return structured JSON with error key."""
        resp = authenticated_client.get("/api/portfolios/99999/")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data

    def test_handler_normalizes_validation_error(self, authenticated_client):
        """A DRF validation error should return structured fields."""
        resp = authenticated_client.post(
            "/api/trading/orders/",
            {"symbol": "invalid", "side": "invalid", "amount": -1},
            format="json",
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert data["status_code"] == 400


# ── OpenAPI Schema ────────────────────────────────────────────


@pytest.mark.django_db
class TestOpenAPISchema:
    def test_schema_endpoint_returns_json(self, authenticated_client):
        resp = authenticated_client.get("/api/schema/")
        assert resp.status_code == 200

    def test_docs_endpoint_accessible(self, authenticated_client):
        resp = authenticated_client.get("/api/docs/")
        assert resp.status_code == 200

    def test_redoc_endpoint_accessible(self, authenticated_client):
        resp = authenticated_client.get("/api/redoc/")
        assert resp.status_code == 200
