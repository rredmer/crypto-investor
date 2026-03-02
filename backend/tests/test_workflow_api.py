"""Tests for workflow API endpoints."""


import pytest

from analysis.models import Workflow, WorkflowRun, WorkflowStep, WorkflowStepRun


@pytest.mark.django_db
class TestWorkflowListAPI:
    def test_requires_auth(self, api_client):
        resp = api_client.get("/api/workflows/")
        assert resp.status_code == 403

    def test_list_empty(self, authenticated_client):
        resp = authenticated_client.get("/api/workflows/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_workflows(self, authenticated_client):
        Workflow.objects.create(id="test_wf", name="Test WF")
        resp = authenticated_client.get("/api/workflows/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "test_wf"

    def test_list_filter_asset_class(self, authenticated_client):
        Workflow.objects.create(id="crypto_wf", name="Crypto", asset_class="crypto")
        Workflow.objects.create(id="equity_wf", name="Equity", asset_class="equity")
        resp = authenticated_client.get("/api/workflows/?asset_class=crypto")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "crypto_wf"

    def test_create_workflow(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/workflows/",
            {
                "id": "my_pipeline",
                "name": "My Pipeline",
                "steps": [
                    {"order": 1, "name": "Step 1", "step_type": "data_refresh"},
                    {"order": 2, "name": "Step 2", "step_type": "news_fetch"},
                ],
            },
            format="json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "my_pipeline"
        assert len(data["steps"]) == 2

    def test_create_duplicate_id_fails(self, authenticated_client):
        Workflow.objects.create(id="dup", name="Dup")
        resp = authenticated_client.post(
            "/api/workflows/",
            {
                "id": "dup",
                "name": "Dup Again",
                "steps": [{"order": 1, "name": "S", "step_type": "data_refresh"}],
            },
            format="json",
        )
        assert resp.status_code == 409


@pytest.mark.django_db
class TestWorkflowDetailAPI:
    def test_get_detail(self, authenticated_client):
        wf = Workflow.objects.create(id="detail_wf", name="Detail")
        WorkflowStep.objects.create(workflow=wf, order=1, name="S1", step_type="data_refresh")
        resp = authenticated_client.get("/api/workflows/detail_wf/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "detail_wf"
        assert len(data["steps"]) == 1

    def test_get_not_found(self, authenticated_client):
        resp = authenticated_client.get("/api/workflows/nonexistent/")
        assert resp.status_code == 404

    def test_delete_workflow(self, authenticated_client):
        Workflow.objects.create(id="del_wf", name="Delete Me")
        resp = authenticated_client.delete("/api/workflows/del_wf/")
        assert resp.status_code == 204
        assert not Workflow.objects.filter(id="del_wf").exists()

    def test_delete_template_fails(self, authenticated_client):
        Workflow.objects.create(id="tmpl", name="Template", is_template=True)
        resp = authenticated_client.delete("/api/workflows/tmpl/")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestWorkflowTriggerAPI:
    def test_trigger_requires_auth(self, api_client):
        resp = api_client.post("/api/workflows/test/trigger/")
        assert resp.status_code == 403

    def test_trigger_not_found(self, authenticated_client):
        resp = authenticated_client.post("/api/workflows/nonexistent/trigger/")
        assert resp.status_code == 404

    def test_trigger_empty_workflow(self, authenticated_client):
        Workflow.objects.create(id="empty_wf", name="Empty")
        resp = authenticated_client.post("/api/workflows/empty_wf/trigger/")
        assert resp.status_code == 400

    def test_trigger_success(self, authenticated_client):
        wf = Workflow.objects.create(id="trigger_wf", name="Trigger")
        WorkflowStep.objects.create(workflow=wf, order=1, name="S1", step_type="data_refresh")
        resp = authenticated_client.post("/api/workflows/trigger_wf/trigger/")
        assert resp.status_code == 202
        data = resp.json()
        assert "workflow_run_id" in data
        assert "job_id" in data


@pytest.mark.django_db
class TestWorkflowScheduleAPI:
    def test_enable(self, authenticated_client):
        Workflow.objects.create(id="sched_wf", name="Sched")
        resp = authenticated_client.post("/api/workflows/sched_wf/enable/")
        assert resp.status_code == 200
        wf = Workflow.objects.get(id="sched_wf")
        assert wf.schedule_enabled is True

    def test_disable(self, authenticated_client):
        Workflow.objects.create(id="dis_wf", name="Dis", schedule_enabled=True)
        resp = authenticated_client.post("/api/workflows/dis_wf/disable/")
        assert resp.status_code == 200
        wf = Workflow.objects.get(id="dis_wf")
        assert wf.schedule_enabled is False


@pytest.mark.django_db
class TestWorkflowRunAPI:
    def test_list_runs(self, authenticated_client):
        wf = Workflow.objects.create(id="runs_wf", name="Runs")
        WorkflowRun.objects.create(workflow=wf, trigger="manual")
        resp = authenticated_client.get("/api/workflows/runs_wf/runs/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_run_detail(self, authenticated_client):
        wf = Workflow.objects.create(id="rd_wf", name="RD")
        step = WorkflowStep.objects.create(
            workflow=wf, order=1, name="S1", step_type="data_refresh",
        )
        run = WorkflowRun.objects.create(workflow=wf, total_steps=1)
        WorkflowStepRun.objects.create(workflow_run=run, step=step, order=1)
        resp = authenticated_client.get(f"/api/workflow-runs/{run.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["step_runs"]) == 1

    def test_run_detail_not_found(self, authenticated_client):
        resp = authenticated_client.get("/api/workflow-runs/nonexistent-id/")
        assert resp.status_code == 404

    def test_cancel_run(self, authenticated_client):
        wf = Workflow.objects.create(id="cancel_wf", name="Cancel")
        run = WorkflowRun.objects.create(workflow=wf, status="running")
        resp = authenticated_client.post(f"/api/workflow-runs/{run.id}/cancel/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWorkflowStepTypesAPI:
    def test_list_step_types(self, authenticated_client):
        resp = authenticated_client.get("/api/workflow-steps/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 11
        type_names = {t["step_type"] for t in data}
        assert "data_refresh" in type_names
        assert "sentiment_aggregate" in type_names
