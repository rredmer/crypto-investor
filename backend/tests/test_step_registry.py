"""Tests for the step registry (analysis/services/step_registry.py)."""


from analysis.services.step_registry import STEP_REGISTRY, get_step_types


class TestStepRegistry:
    def test_registry_has_all_reexports(self):
        expected = {
            "data_refresh", "regime_detection", "news_fetch",
            "data_quality", "order_sync",
        }
        assert expected.issubset(set(STEP_REGISTRY.keys()))

    def test_registry_has_workflow_steps(self):
        expected = {
            "vbt_screen", "sentiment_aggregate", "composite_score",
            "alert_evaluate", "strategy_recommend",
        }
        assert expected.issubset(set(STEP_REGISTRY.keys()))

    def test_registry_has_11_entries(self):
        assert len(STEP_REGISTRY) == 11

    def test_all_executors_callable(self):
        for name, executor in STEP_REGISTRY.items():
            assert callable(executor), f"{name} is not callable"

    def test_get_step_types(self):
        types = get_step_types()
        assert len(types) == 11
        type_names = {t["step_type"] for t in types}
        assert "data_refresh" in type_names
        assert "sentiment_aggregate" in type_names
        for t in types:
            assert "step_type" in t
            assert "description" in t
