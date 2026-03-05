"""
Job runner — dispatches sync functions to a thread pool, tracks progress in-memory,
and persists job state to DB via Django ORM.
"""

import logging
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from django.conf import settings

logger = logging.getLogger("job_runner")


def recover_stale_jobs() -> int:
    """Mark all running/pending BackgroundJobs as failed on startup.

    Returns the number of recovered jobs.
    """
    from analysis.models import BackgroundJob

    now = datetime.now(timezone.utc)
    count = BackgroundJob.objects.filter(
        status__in=["running", "pending"],
    ).update(
        status="failed",
        error="Interrupted by server restart",
        completed_at=now,
    )
    if count:
        logger.info("Recovered %d stale BackgroundJob(s) on startup", count)
    return count


def recover_stale_workflow_runs() -> int:
    """Mark all running/pending WorkflowRuns as failed on startup.

    Returns the number of recovered runs.
    """
    from analysis.models import WorkflowRun

    now = datetime.now(timezone.utc)
    count = WorkflowRun.objects.filter(
        status__in=["running", "pending"],
    ).update(
        status="failed",
        error="Interrupted by server restart",
        completed_at=now,
    )
    if count:
        logger.info("Recovered %d stale WorkflowRun(s) on startup", count)
    return count

# In-memory progress store for live polling
_job_progress: dict[str, dict[str, Any]] = {}

# Singleton runner instance
_runner_instance = None


def get_job_runner() -> "JobRunner":
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = JobRunner(max_workers=settings.MAX_JOB_WORKERS)
    return _runner_instance


class JobRunner:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")

    def submit(
        self,
        job_type: str,
        run_fn: Callable[..., Any],
        params: dict | None = None,
    ) -> str:
        """Create a DB job record and dispatch run_fn to the thread pool."""
        import django

        django.setup()
        from analysis.models import BackgroundJob

        job_id = str(uuid.uuid4())
        BackgroundJob.objects.create(
            id=job_id,
            job_type=job_type,
            status="pending",
            params=params,
        )
        _job_progress[job_id] = {"progress": 0.0, "progress_message": "Queued"}
        self._executor.submit(self._run_job, job_id, run_fn, params or {})
        return job_id

    def _run_job(self, job_id: str, run_fn: Callable, params: dict) -> None:
        import django

        django.setup()
        from analysis.models import BackgroundJob

        try:
            job_obj = BackgroundJob.objects.get(id=job_id)
            BackgroundJob.objects.filter(id=job_id).update(
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            _job_progress[job_id] = {"progress": 0.0, "progress_message": "Running"}

            # Broadcast job start
            try:
                from core.services.ws_broadcast import broadcast_scheduler_event

                broadcast_scheduler_event(
                    task_id="",
                    task_name=job_obj.job_type,
                    task_type=job_obj.job_type,
                    status="running",
                    job_id=job_id,
                    message=f"Job {job_id[:8]} started",
                )
            except Exception:
                pass

            _last_persisted_pct = [0]  # mutable container for closure

            def progress_callback(progress: float, message: str = "") -> None:
                clamped = min(progress, 1.0)
                _job_progress[job_id] = {
                    "progress": clamped,
                    "progress_message": message,
                }
                # Persist to DB every 10% increment
                pct_10 = int(clamped * 10)
                if pct_10 > _last_persisted_pct[0]:
                    _last_persisted_pct[0] = pct_10
                    BackgroundJob.objects.filter(id=job_id).update(
                        progress=clamped,
                        progress_message=message[:200],
                    )

            result = run_fn(params, progress_callback)

            _job_progress[job_id] = {"progress": 1.0, "progress_message": "Complete"}
            job = BackgroundJob.objects.get(id=job_id)
            job.status = "completed"
            job.progress = 1.0
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            job.save()

            # Broadcast job completion
            try:
                from core.services.ws_broadcast import broadcast_scheduler_event

                broadcast_scheduler_event(
                    task_id="",
                    task_name=job.job_type,
                    task_type=job.job_type,
                    status="completed",
                    job_id=job_id,
                    message=f"Job {job_id[:8]} completed",
                )
            except Exception:
                pass

            # Persist structured result for backtest jobs
            if job.job_type == "backtest" and isinstance(result, dict) and "error" not in result:
                from analysis.models import BacktestResult

                BacktestResult.objects.create(
                    job=job,
                    framework=result.get("framework", params.get("framework", "")),
                    strategy_name=result.get("strategy", params.get("strategy", "")),
                    symbol=result.get("symbol", params.get("symbol", "")),
                    timeframe=result.get("timeframe", params.get("timeframe", "")),
                    timerange=params.get("timerange", ""),
                    metrics=result.get("metrics"),
                    trades=result.get("trades"),
                    config=params,
                )
        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            _job_progress[job_id] = {"progress": 0.0, "progress_message": f"Failed: {e}"}
            BackgroundJob.objects.filter(id=job_id).update(
                status="failed",
                error=str(e),
                completed_at=datetime.now(timezone.utc),
            )
            # Broadcast job failure
            try:
                from core.services.ws_broadcast import broadcast_scheduler_event

                broadcast_scheduler_event(
                    task_id="",
                    task_name=params.get("job_type", "unknown"),
                    task_type=params.get("job_type", "unknown"),
                    status="failed",
                    job_id=job_id,
                    message=f"Job {job_id[:8]} failed: {e}",
                )
            except Exception:
                pass

    @staticmethod
    def get_live_progress(job_id: str) -> dict[str, Any] | None:
        return _job_progress.get(job_id)

    @staticmethod
    def cancel_job(job_id: str) -> bool:
        from analysis.models import BackgroundJob

        updated = BackgroundJob.objects.filter(
            id=job_id,
            status__in=["pending", "running"],
        ).update(status="cancelled", completed_at=datetime.now(timezone.utc))
        return updated > 0
