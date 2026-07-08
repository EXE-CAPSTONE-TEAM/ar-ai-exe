from app.db.database import SessionLocal
from app.services.kiri_pipeline import KiriPipelineService


def start_kiri_processing(scan_session_id: str) -> None:
    db = SessionLocal()
    try:
        KiriPipelineService(db).start_processing(scan_session_id)
    finally:
        db.close()


def bake_kiri_project(scan_session_id: str) -> None:
    db = SessionLocal()
    try:
        KiriPipelineService(db).bake_saved_project(scan_session_id)
    finally:
        db.close()
