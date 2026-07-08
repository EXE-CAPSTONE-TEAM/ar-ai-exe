from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def test_migration_backfills_project_owned_model_version(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_AUTO_CREATE_TABLES", "false")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[1] / "alembic"),
    )
    command.upgrade(config, "20260612_0007")

    engine = create_engine(database_url)
    now = datetime(2026, 7, 2)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (id, role, name, email, created_at, updated_at)
                VALUES ('user_001', 'demo_user', 'Owner', 'owner@example.com', :now, :now)
                """
            ),
            {"now": now},
        )
        connection.execute(
            text(
                """
                INSERT INTO projects
                    (id, user_id, name, status, source_type, created_at, updated_at)
                VALUES
                    ('proj_001', 'user_001', 'Shoe', 'ready', 'scan', :now, :now)
                """
            ),
            {"now": now},
        )
        connection.execute(
            text(
                """
                INSERT INTO scan_sessions
                    (id, user_id, project_id, status, source_type, created_at, updated_at)
                VALUES
                    ('scan_001', 'user_001', 'proj_001', 'completed', 'scan', :now, :now)
                """
            ),
            {"now": now},
        )
        connection.execute(
            text(
                """
                INSERT INTO model_assets
                    (id, scan_session_id, glb_path, obj_path, mtl_path, texture_path,
                     status, source_type, quality_report_path, created_at)
                VALUES
                    ('model_001', 'scan_001', 'models/scan_001/shoe_preview.glb',
                     'models/scan_001/shoe.obj', 'models/scan_001/shoe.mtl',
                     'models/scan_001/shoe_texture.png', 'ready', 'scan',
                     'models/scan_001/quality_report.json', :now)
                """
            ),
            {"now": now},
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        version = connection.execute(
            text(
                """
                SELECT project_id, asset_type, logical_key, version_number, status
                FROM asset_versions
                """
            )
        ).mappings().one()
        legacy_id = connection.execute(
            text("SELECT legacy_id FROM asset_version_legacy_links")
        ).scalar_one()
        file_types = set(
            connection.execute(
                text("SELECT file_type FROM asset_version_files")
            ).scalars()
        )
        _assert_refactored_schema(connection)

    assert version == {
        "project_id": "proj_001",
        "asset_type": "model",
        "logical_key": "primary",
        "version_number": 1,
        "status": "ready",
    }
    assert legacy_id == "model_001"
    assert file_types == {"glb", "obj", "mtl", "texture", "quality-report"}

    command.downgrade(config, "20260702_0008")
    command.upgrade(config, "head")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM projects")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM scan_sessions")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM model_assets")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM designs")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM asset_versions")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM asset_version_files")).scalar_one() == 5
        assert connection.execute(text("SELECT COUNT(*) FROM asset_version_legacy_links")).scalar_one() == 1
        _assert_refactored_schema(connection)

    get_settings.cache_clear()


def _assert_refactored_schema(connection) -> None:
    inspector = inspect(connection)
    design_columns = {column["name"]: column for column in inspector.get_columns("designs")}
    assert "base_asset_version_id" in design_columns
    assert design_columns["model_asset_id"]["nullable"] is True

    assert _foreign_key_delete_action(connection, "designs", "model_asset_id") == "SET NULL"
    assert _foreign_key_delete_action(connection, "designs", "base_asset_version_id") == "SET NULL"
    assert _foreign_key_delete_action(connection, "asset_versions", "project_id") == "RESTRICT"
    assert _foreign_key_delete_action(connection, "asset_versions", "parent_asset_version_id") == "SET NULL"
    assert _foreign_key_delete_action(connection, "asset_version_files", "asset_version_id") == "CASCADE"
    assert _foreign_key_delete_action(connection, "asset_version_legacy_links", "asset_version_id") == "CASCADE"

    unique_indexes = _unique_indexes(connection, "asset_version_legacy_links")
    assert ("legacy_type", "legacy_id") in unique_indexes
    assert ("asset_version_id", "legacy_type") in unique_indexes


def _foreign_key_delete_action(connection, table_name: str, column_name: str) -> str:
    rows = connection.exec_driver_sql(f"PRAGMA foreign_key_list({table_name})").fetchall()
    for row in rows:
        if row[3] == column_name:
            return row[6]
    raise AssertionError(f"Foreign key for {table_name}.{column_name} not found")


def _unique_indexes(connection, table_name: str) -> set[tuple[str, ...]]:
    unique_indexes: set[tuple[str, ...]] = set()
    for index_row in connection.exec_driver_sql(f"PRAGMA index_list({table_name})").fetchall():
        if not index_row[2]:
            continue
        index_name = index_row[1]
        columns = tuple(
            row[2]
            for row in connection.exec_driver_sql(f"PRAGMA index_info({index_name})").fetchall()
        )
        unique_indexes.add(columns)
    return unique_indexes
