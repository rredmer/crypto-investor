"""
Tests for Prometheus-compatible metrics endpoint and collector.
"""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestMetricsEndpoint:
    def test_metrics_returns_200(self, authenticated_client):
        resp = authenticated_client.get("/metrics/")
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")

    def test_metrics_requires_auth(self):
        """Metrics endpoint should require authentication."""
        client = Client()
        resp = client.get("/metrics/")
        assert resp.status_code == 403

    def test_metrics_contains_gauges(self, authenticated_client):
        """After hitting metrics, we should see active_orders gauges."""
        resp = authenticated_client.get("/metrics/")
        body = resp.content.decode()
        assert "active_orders" in body

    def test_metrics_after_request(self, authenticated_client):
        """After a real request, http_requests_total should increment."""
        authenticated_client.get("/api/health/")

        resp = authenticated_client.get("/metrics/")
        body = resp.content.decode()
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body


class TestMetricsCollector:
    def test_gauge(self):
        from core.services.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.gauge("test_gauge", 42.0)
        output = mc.collect()
        assert "test_gauge 42.0" in output

    def test_gauge_with_labels(self):
        from core.services.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.gauge("test_labeled", 1.0, {"env": "test"})
        output = mc.collect()
        assert 'test_labeled{env="test"} 1.0' in output

    def test_counter_inc(self):
        from core.services.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.counter_inc("test_counter", {"method": "GET"})
        mc.counter_inc("test_counter", {"method": "GET"})
        mc.counter_inc("test_counter", {"method": "GET"}, amount=3)
        output = mc.collect()
        assert 'test_counter{method="GET"} 5' in output

    def test_histogram(self):
        from core.services.metrics import MetricsCollector

        mc = MetricsCollector()
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
            mc.histogram_observe("test_hist", v)
        output = mc.collect()
        assert "test_hist_count 5" in output
        assert "test_hist_sum" in output
        assert 'quantile="0.5"' in output
        assert 'quantile="0.99"' in output

    def test_timed_context_manager(self):
        import time

        from core.services.metrics import MetricsCollector, timed

        mc = MetricsCollector()
        with timed("test_timing", {"op": "sleep"}):
            time.sleep(0.01)

        output = mc.collect()
        assert "test_timing" in output
