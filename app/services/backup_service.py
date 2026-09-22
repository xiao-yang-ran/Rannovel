"""Whole-library ZIP backup and validated restore."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from pathlib import Path

from app.database import SCHEMA_VERSION


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(source: Path, target: Path):
    with closing(sqlite3.connect(source)) as input_db, closing(sqlite3.connect(target)) as output_db:
        input_db.backup(output_db)


def create_backup(database_file: Path, backup_dir: Path, assets_dir: Path | None = None) -> Path:
    database_file, backup_dir = Path(database_file), Path(backup_dir)
    if not database_file.is_file(): raise FileNotFoundError(f"数据库文件不存在：{database_file}")
    assets_dir = Path(assets_dir) if assets_dir else database_file.parent / "assets"
    backup_dir.mkdir(parents=True, exist_ok=True)
    output = backup_dir / f"rannovel_{uuid.uuid4().hex}.zip"
    with tempfile.TemporaryDirectory(dir=backup_dir) as temporary:
        snapshot = Path(temporary) / "rannovel.db"
        _snapshot(database_file, snapshot)
        with closing(sqlite3.connect(snapshot)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",): raise ValueError("数据库未通过完整性检查。")
            names = [row[0] for row in connection.execute("SELECT filename FROM assets")]
        hashes = {}
        for name in names:
            if Path(name).name != name: raise ValueError("资源文件名无效。")
            path = assets_dir / name
            if not path.is_file(): raise FileNotFoundError(f"资源文件丢失：{path}")
            hashes[name] = _sha256_file(path)
        manifest = {"application": "RanNovel", "format_version": 2, "schema_version": SCHEMA_VERSION,
                    "database_sha256": _sha256_file(snapshot), "assets": hashes}
        try:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, "rannovel.db")
                for name in names: archive.write(assets_dir / name, f"assets/{name}")
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        except Exception:
            output.unlink(missing_ok=True)
            raise
    return output


def _extract_validated(archive_file: Path, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    db = directory / "rannovel.db"
    assets = directory / "assets"
    assets.mkdir()
    try:
        with zipfile.ZipFile(archive_file) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("application") != "RanNovel" or manifest.get("format_version") != 2 or manifest.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("备份格式或数据库版本不兼容。")
            hashes = manifest.get("assets")
            if not isinstance(hashes, dict) or set(archive.namelist()) != {"manifest.json", "rannovel.db"} | {f"assets/{name}" for name in hashes}:
                raise ValueError("备份目录不完整或含有额外文件。")
            for name in hashes:
                if Path(name).name != name or name in {"", ".", ".."}: raise ValueError("备份资源路径无效。")
            for member, destination, expected in [("rannovel.db", db, manifest["database_sha256"])] + [(f"assets/{name}", assets / name, digest) for name, digest in hashes.items()]:
                with archive.open(member) as input_file, destination.open("wb") as output_file:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                        output_file.write(chunk); digest.update(chunk)
                if digest.hexdigest() != expected: raise ValueError(f"备份校验失败：{member}")
        with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",): raise ValueError("备份数据库损坏。")
            if connection.execute("PRAGMA foreign_key_check").fetchone(): raise ValueError("备份中的关联关系损坏。")
            if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION: raise ValueError("数据库版本不匹配。")
            db_assets = {row[0]: row[1] for row in connection.execute("SELECT filename, sha256 FROM assets")}
            if db_assets != hashes: raise ValueError("数据库与资源清单不匹配。")
            required = {"works", "chapters", "characters", "inspirations", "references", "assets"}
            actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required <= actual: raise ValueError("备份缺少必需数据表。")
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, sqlite3.DatabaseError) as error:
        raise ValueError("ZIP 备份无效或损坏。") from error
    return db, assets


def restore_backup(archive_file: Path, database, backup_dir: Path, assets_dir: Path | None = None) -> Path:
    archive_file, backup_dir = Path(archive_file), Path(backup_dir)
    assets_dir = Path(assets_dir) if assets_dir else database.database_file.parent / "assets"
    backup_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=backup_dir) as temporary:
        incoming_db, incoming_assets = _extract_validated(archive_file, Path(temporary))
        safety = create_backup(database.database_file, backup_dir, assets_dir)
        old_assets = backup_dir / f"assets_before_restore_{uuid.uuid4().hex}"
        database.close()
        moved = False
        try:
            if assets_dir.exists():
                os.replace(assets_dir, old_assets); moved = True
            os.replace(incoming_assets, assets_dir)
            _snapshot(incoming_db, database.database_file)
            database.initialize()
            return safety
        except Exception as error:
            database.close()
            try:
                rollback_db, _ = _extract_validated(safety, Path(temporary) / "rollback")
                _snapshot(rollback_db, database.database_file)
                if assets_dir.exists(): os.replace(assets_dir, backup_dir / f"failed_restore_assets_{uuid.uuid4().hex}")
                if moved: os.replace(old_assets, assets_dir)
                database.initialize()
            except Exception as rollback_error:
                raise RuntimeError(f"恢复与回退均失败；安全备份：{safety}") from rollback_error
            raise RuntimeError(f"恢复失败，已回退；安全备份：{safety}") from error
