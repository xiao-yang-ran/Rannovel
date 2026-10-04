"""Validate both SQLite constraints and polymorphic library associations."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.domain import ASSET_NAME, GALLERY_KINDS, KINDS, SHA256, TARGET_PERMISSIONS, asset_names
from app.models import Base


def validate_schema(connection) -> None:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in Base.metadata.sorted_tables:
        if table.name not in tables:
            raise ValueError(f"资料库缺少数据表：{table.name}")
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table.name}")')}
        if not set(table.columns.keys()) <= columns:
            raise ValueError(f"资料库字段不完整：{table.name}")


def used_asset_names(connection) -> set[str]:
    names = {row[0] for row in connection.execute(
        "SELECT a.filename FROM assets a JOIN gallery_images g ON g.asset_id = a.id"
    )}
    for table in ("works", "chapters"):
        for (body,) in connection.execute(f"SELECT body_html FROM {table}"):
            names.update(asset_names(body))
    return names


def validate_library(database_file: Path, schema_version: int) -> dict[str, str]:
    uri = Path(database_file).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("资料库未通过 SQLite 完整性检查。")
        validate_schema(connection)
        if connection.execute("PRAGMA user_version").fetchone()[0] != schema_version:
            raise ValueError("数据库版本不匹配。")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("资料库中的外键关联已损坏。")
        works = dict(connection.execute("SELECT id, kind FROM works"))
        if any(kind not in KINDS for kind in works.values()):
            raise ValueError("作品类型无效。")
        volumes = dict(connection.execute("SELECT id, work_id FROM volumes"))
        chapter_volumes = dict(connection.execute("SELECT id, volume_id FROM chapters"))
        if not set(chapter_volumes.values()) <= volumes.keys():
            raise ValueError("章节引用的分卷不存在。")
        chapters = {item_id: volumes[volume_id] for item_id, volume_id in chapter_volumes.items()}
        sources = {"character": {row[0]: None for row in connection.execute("SELECT id FROM characters")}}
        for kind, table in (("location", "locations"), ("event", "events"), ("setting", "settings")):
            sources[kind] = dict(connection.execute(f"SELECT id, work_id FROM {table}"))
        for owners in (volumes, sources["location"], sources["event"], sources["setting"]):
            if any(works.get(work_id) != "novel" for work_id in owners.values()):
                raise ValueError("分卷或长篇资料的作品归属无效。")

        def target_work(kind, target_id):
            if kind == "chapter" and target_id in chapters:
                return chapters[target_id]
            if kind in ("essay", "fragment") and works.get(target_id) == kind:
                return target_id
            raise ValueError(f"正文关联目标不存在：{kind} #{target_id}")

        for row in connection.execute('SELECT target_kind, target_id, source_kind, source_id FROM "references"'):
            target_kind, target_id, source_kind, source_id = row
            work_id = target_work(target_kind, target_id)
            if source_kind not in sources or source_kind not in TARGET_PERMISSIONS[target_kind]:
                raise ValueError("正文关联的资料类型不允许。")
            if source_id not in sources[source_kind]:
                raise ValueError(f"关联资料不存在：{source_kind} #{source_id}")
            if source_kind != "character" and sources[source_kind][source_id] != work_id:
                raise ValueError("正文引用了其他作品的资料。")
        faction_ids = {row[0] for row in connection.execute("SELECT id FROM factions")}
        for (faction_id,) in connection.execute("SELECT faction_id FROM characters WHERE faction_id IS NOT NULL"):
            if faction_id not in faction_ids:
                raise ValueError("人物所属阵营不存在。")
        for source_id, target_id in connection.execute("SELECT source_id, target_id FROM character_relations"):
            if source_id == target_id or source_id not in sources["character"] or target_id not in sources["character"]:
                raise ValueError("人物关系的端点无效。")
        for event_id, character_id in connection.execute("SELECT event_id, character_id FROM event_characters"):
            if event_id not in sources["event"] or character_id not in sources["character"]:
                raise ValueError("事件人物关联无效。")
        ideas = set()
        for item_id, pool, owner, kind, target in connection.execute(
            "SELECT id, pool, owner_work_id, target_kind, target_id FROM inspirations"
        ):
            ideas.add(item_id)
            if pool not in ("essay", "novel"):
                raise ValueError("灵感来源池无效。")
            if owner is not None and (owner not in works or pool != ("essay" if works[owner] == "essay" else "novel")):
                raise ValueError("灵感来源池与所属作品不匹配。")
            if (kind is None) != (target is None):
                raise ValueError("灵感正文关联不完整。")
            if kind is not None and (owner is None or target_work(kind, target) != owner):
                raise ValueError("灵感关联了其他作品的正文。")
        sources["inspiration"] = dict.fromkeys(ideas)
        asset_ids = {row[0] for row in connection.execute("SELECT id FROM assets")}
        for kind, source_id, asset_id in connection.execute("SELECT source_kind, source_id, asset_id FROM gallery_images"):
            if kind not in GALLERY_KINDS or source_id not in sources[kind] or asset_id not in asset_ids:
                raise ValueError("图库关联条目不存在或类型无效。")
        for table in ("characters", "settings"):
            for (raw,) in connection.execute(f"SELECT custom_fields FROM {table}"):
                try:
                    valid = isinstance(json.loads(raw), dict)
                except (TypeError, json.JSONDecodeError):
                    valid = False
                if not valid:
                    raise ValueError(f"补充信息格式无效：{table}")
        assets = dict(connection.execute("SELECT filename, sha256 FROM assets"))
        if any(not isinstance(name, str) or not ASSET_NAME.fullmatch(name)
               or not isinstance(digest, str) or not SHA256.fullmatch(digest)
               for name, digest in assets.items()):
            raise ValueError("图片资源名称或哈希无效。")
        if not used_asset_names(connection) <= assets.keys():
            raise ValueError("正文引用的图片未登记在资源库中。")
        return assets
