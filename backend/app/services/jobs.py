from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.database import SessionLocal
from app.models import Design, DesignPreviewStatus, Job, JobStatus, JobType, User
from app.schemas.job import JobResponse
from app.services.designs import DesignService


INLINE_BAKE_FALLBACK_ENVIRONMENTS = {"local", "dev", "development", "demo", "desktop", "test"}
INLINE_BAKE_FAILURE_MESSAGE = "Preview bake failed. The draft was saved and can be retried."


class JobService:
    def __init__(self, db: Session):
        self.db = db

    def enqueue_bake(self, design: Design, user: User) -> Job:
        if design.user_id != user.id:
            raise ApiError(404, "DESIGN_NOT_FOUND", "Design not found.")
        job = Job(
            user_id=user.id,
            project_id=design.project_id,
            design_id=design.id,
            type=JobType.BAKE,
            status=JobStatus.QUEUED,
            progress=0,
        )
        design.preview_status = DesignPreviewStatus.PENDING
        design.preview_error_message = None
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        try:
            rq_job_id = enqueue_job(job.id)
        except Exception as exc:
            if _should_run_inline_bake_fallback():
                return self._run_inline_bake_fallback(job, design)

            job.status = JobStatus.FAILED
            job.error_message = "Preview processing is temporarily unavailable."
            job.updated_at = datetime.utcnow()
            design.preview_status = DesignPreviewStatus.FAILED
            design.preview_error_message = "Preview processing is temporarily unavailable."
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Preview processing is temporarily unavailable.",
            ) from exc

        job.rq_job_id = rq_job_id
        self.db.commit()
        self.db.refresh(job)
        return job

    def _run_inline_bake_fallback(self, job: Job, design: Design) -> Job:
        job.status = JobStatus.PROCESSING
        job.progress = 5
        job.error_message = None
        job.updated_at = datetime.utcnow()
        design.preview_status = DesignPreviewStatus.PROCESSING
        design.preview_error_message = None
        self.db.commit()

        try:
            run_job(job.id)
        except Exception:
            self.db.rollback()
            refreshed_job = self.db.get(Job, job.id)
            refreshed_design = self.db.get(Design, design.id)
            if refreshed_job:
                _fail_job(refreshed_job, INLINE_BAKE_FAILURE_MESSAGE)
            if refreshed_design:
                refreshed_design.preview_status = DesignPreviewStatus.FAILED
                refreshed_design.preview_error_message = INLINE_BAKE_FAILURE_MESSAGE
                refreshed_design.preview_updated_at = datetime.utcnow()
            self.db.commit()

        self.db.expire_all()
        refreshed_job = self.db.get(Job, job.id)
        if not refreshed_job:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Preview processing could not be completed.",
            )
        return refreshed_job

    def get_for_user(self, job_id: str, user: User) -> Job:
        job = self.db.get(Job, job_id)
        if not job or job.user_id != user.id:
            raise ApiError(404, "JOB_NOT_FOUND", "Job not found.")
        return job

    def response(self, job: Job) -> JobResponse:
        return JobResponse(
            id=job.id,
            type=job.type,
            status=job.status,
            progress=job.progress,
            errorMessage=job.error_message,
            designId=job.design_id,
            projectId=job.project_id,
            createdAt=job.created_at,
            updatedAt=job.updated_at,
        )


def enqueue_job(job_id: str) -> str:
    from redis import Redis
    from rq import Queue

    settings = get_settings()
    queue = Queue(settings.rq_queue_name, connection=Redis.from_url(settings.redis_url))
    rq_job = queue.enqueue(
        "app.workers.job_worker.run_job",
        job_id,
        job_timeout=settings.rq_job_timeout_seconds,
    )
    return rq_job.id


def _should_run_inline_bake_fallback() -> bool:
    settings = get_settings()
    environment = settings.environment.strip().lower()
    return settings.enable_inline_bake_fallback or environment in INLINE_BAKE_FALLBACK_ENVIRONMENTS


def run_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        job.status = JobStatus.PROCESSING
        job.progress = 10
        job.error_message = None
        job.updated_at = datetime.utcnow()
        db.commit()

        if job.type == JobType.BAKE and job.design_id:
            _run_bake_job(db, job)
        else:
            _fail_job(job, "Unsupported job type.")
            db.commit()
    finally:
        db.close()


def _run_bake_job(db: Session, job: Job) -> None:
    design = db.get(Design, job.design_id)
    if not design:
        _fail_job(job, "Design not found.")
        db.commit()
        return

    DesignService(db).refresh_preview(design)
    db.refresh(design)
    if design.preview_status == DesignPreviewStatus.FAILED:
        _fail_job(job, design.preview_error_message or "Preview bake failed.")
    else:
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.error_message = None
        job.updated_at = datetime.utcnow()
    db.commit()


def _fail_job(job: Job, message: str) -> None:
    job.status = JobStatus.FAILED
    job.progress = 100
    job.error_message = message
    job.updated_at = datetime.utcnow()
