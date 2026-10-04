"""Explicit SQLite schema revisions. Existing unversioned libraries are never overwritten."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import uuid
from contextlib import closing
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from app.models import Base, Faction

SCHEMA_VERSION = 2


def migrate_1_to_2(connection):
    """Add rich card/outline fields to the first unified library schema."""
    Faction.__table__.create(bind=connection, checkfirst=True)
    additions = {
        "volumes": {"summary": "TEXT NOT NULL DEFAULT ''"},
        "chapters": {"summary": "TEXT NOT NULL DEFAULT ''", "core_events": "TEXT NOT NULL DEFAULT ''",
                     "estimated_words": "INTEGER NOT NULL DEFAULT 0"},
        "characters": {"personality": "TEXT NOT NULL DEFAULT ''", "motivation": "TEXT NOT NULL DEFAULT ''",
                       "skills": "TEXT NOT NULL DEFAULT ''", "background": "TEXT NOT NULL DEFAULT ''",
                       "custom_fields": "JSON NOT NULL DEFAULT '{}'",
                       "faction_id": "INTEGER REFERENCES factions(id) ON DELETE RESTRICT"},
        "locations": {"category": "VARCHAR(100) NOT NULL DEFAULT '地点'", "layout": "TEXT NOT NULL DEFAULT ''",
                      "environment_rules": "TEXT NOT NULL DEFAULT ''", "physical_laws": "TEXT NOT NULL DEFAULT ''",
                      "notes": "TEXT NOT NULL DEFAULT ''"},
        "settings": {"category": "VARCHAR(100) NOT NULL DEFAULT '世界总纲'", "overview": "TEXT NOT NULL DEFAULT ''",
                     "structure": "TEXT NOT NULL DEFAULT ''", "rules": "TEXT NOT NULL DEFAULT ''",
                     "advancement": "TEXT NOT NULL DEFAULT ''", "limitations": "TEXT NOT NULL DEFAULT ''",
                     "relationships": "TEXT NOT NULL DEFAULT ''", "notes": "TEXT NOT NULL DEFAULT ''",
                     "custom_fields": "JSON NOT NULL DEFAULT '{}'"},
    }
    for table, columns in additions.items():
        existing = {row[1] for row in connection.exec_driver_sql(f'PRAGMA table_info("{table}")')}
        if not existing: raise RuntimeError(f"迁移失败，缺少数据表：{table}")
        for name, declaration in columns.items():
            if name not in existing:
                connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}')
    for table in ("locations", "settings"):
        connection.exec_driver_sql(f'CREATE INDEX IF NOT EXISTS "ix_{table}_category" ON "{table}" (category)')


class Database:
    def __init__(self, database_file: Path):
        self.database_file = Path(database_file).resolve()
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(URL.create("sqlite", database=str(self.database_file)), connect_args={"check_same_thread": False})
        @event.listens_for(self.engine, "connect")
        def configure(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
        self.session_factory = sessionmaker(self.engine, class_=Session, expire_on_commit=False)

    def initialize(self):
        with self.engine.connect() as connection:
            prior_version = connection.exec_driver_sql("PRAGMA user_version").scalar()
        if prior_version == 1 and self.database_file.is_file():
            safety = self.database_file.with_name(f"rannovel_schema1_safety_{uuid.uuid4().hex}.db")
            with closing(sqlite3.connect(self.database_file)) as source, closing(sqlite3.connect(safety)) as target:
                source.backup(target)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            version = connection.exec_driver_sql("PRAGMA user_version").scalar()
            if version > SCHEMA_VERSION:
                raise RuntimeError("资料库由更新版本的 RanNovel 创建，请升级应用。")
            if version == 0:
                existing = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").all()
                if existing:
                    raise RuntimeError("发现未识别的旧数据库；请先备份并核实内容，程序不会覆盖它。")
                Base.metadata.create_all(connection)
                connection.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
            elif version == 1:
                migrate_1_to_2(connection)
                connection.exec_driver_sql("PRAGMA user_version=2")
        with self.engine.begin() as connection:
            for name, table, columns in (
                ("ix_reference_source", "references", "source_kind, source_id"),
                ("ix_gallery_source", "gallery_images", "source_kind, source_id"),
                ("ix_inspiration_target", "inspirations", "target_kind, target_id"),
                ("ix_event_work_time", "events", "work_id, year, month, id"),
                ("ix_chapter_volume_order", "chapters", "volume_id, sort_order, id"),
            ):
                connection.exec_driver_sql(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns})')
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        from app.services.integrity import validate_schema
        with closing(sqlite3.connect(self.database_file.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            validate_schema(connection)
        return self

    def close(self):
        self.engine.dispose()
