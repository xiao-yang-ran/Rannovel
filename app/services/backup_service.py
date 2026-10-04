"""Consistent, bounded whole-library backups and rollback-safe restores."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.database import SCHEMA_VERSION
from app.domain import ASSET_NAME, SHA256
from app.services.integrity import used_asset_names, validate_library

MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_ENTRY_BYTES = 4 * 1024 ** 3
MAX_ARCHIVE_BYTES = 20 * 1024 ** 3
MAX_MEMBERS = 100002
CHUNK_SIZE = 1024 * 1024


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(source: Path, target: Path):
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + "?mode=ro", uri=True)) as input_db:
        with closing(sqlite3.connect(target)) as output_db:
            input_db.backup(output_db)


def _archive_name(prefix="rannovel"):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}.zip"


def _write_checked(archive, source, member, expected):
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_file, archive.open(member, "w", force_zip64=True) as output_file:
        for chunk in iter(lambda: input_file.read(CHUNK_SIZE), b""):
            size += len(chunk)
            if size > MAX_ENTRY_BYTES:
                raise ValueError(f"备份文件超过单项大小限制：{member}")
            digest.update(chunk)
            output_file.write(chunk)
    if digest.hexdigest() != expected:
        raise ValueError(f"图片或数据库内容已改变，备份未生成：{member}。请恢复原文件后重试。")
    return size


def create_backup(database_file: Path, backup_dir: Path, assets_dir: Path | None = None) -> Path:
    database_file, backup_dir = Path(database_file), Path(backup_dir)
    if not database_file.is_file():
        raise FileNotFoundError(f"数据库文件不存在：{database_file}")
    assets_dir = Path(assets_dir) if assets_dir else database_file.parent / "assets"
    backup_dir.mkdir(parents=True, exist_ok=True)
    output = backup_dir / _archive_name()
    pending = output.with_suffix(".zip.tmp")
    try:
        with tempfile.TemporaryDirectory(dir=backup_dir) as temporary:
            snapshot = Path(temporary) / "rannovel.db"
            _snapshot(database_file, snapshot)
            hashes = validate_library(snapshot, SCHEMA_VERSION)
            # Removed images retained only for an editor's undo history do not belong in a backup.
            with closing(sqlite3.connect(snapshot)) as connection:
                used = used_asset_names(connection)
                unused = hashes.keys() - used
                connection.executemany("DELETE FROM assets WHERE filename=?", ((name,) for name in unused))
                connection.commit()
            hashes = {name: digest for name, digest in hashes.items() if name in used}
            if len(hashes) + 2 > MAX_MEMBERS:
                raise ValueError("图片数量超过备份格式限制。")
            manifest = {"application": "RanNovel", "format_version": 2, "schema_version": SCHEMA_VERSION,
                        "database_sha256": _sha256_file(snapshot), "assets": hashes}
            manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise ValueError("备份资源清单过大。")
            total = len(manifest_bytes)
            with zipfile.ZipFile(pending, "w", zipfile.ZIP_DEFLATED) as archive:
                total += _write_checked(archive, snapshot, "rannovel.db", manifest["database_sha256"])
                for name, digest in hashes.items():
                    path = assets_dir / name
                    if path.is_symlink() or not path.is_file():
                        raise FileNotFoundError(f"资源文件丢失或不是普通文件：{path}")
                    total += _write_checked(archive, path, f"assets/{name}", digest)
                    if total > MAX_ARCHIVE_BYTES:
                        raise ValueError("资料库超过 20 GiB 的备份大小限制。")
                archive.writestr("manifest.json", manifest_bytes)
        os.replace(pending, output)
    finally:
        pending.unlink(missing_ok=True)
    return output


def _extract_validated(archive_file: Path, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    db, assets = directory / "rannovel.db", directory / "assets"
    assets.mkdir()
    try:
        with zipfile.ZipFile(archive_file) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(members) > MAX_MEMBERS or len(names) != len(set(names)):
                raise ValueError("备份包含重复文件或文件数量超限。")
            if any(member.file_size > MAX_ENTRY_BYTES for member in members):
                raise ValueError("备份中的单个文件过大。")
            if sum(member.file_size for member in members) > MAX_ARCHIVE_BYTES:
                raise ValueError("备份解压大小超过 20 GiB。")
            if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
                raise ValueError("备份资源清单过大。")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("application") != "RanNovel" or manifest.get("format_version") != 2 or manifest.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("备份格式或数据库版本不兼容。")
            hashes = manifest.get("assets")
            if not isinstance(hashes, dict):
                raise ValueError("备份资源清单格式无效。")
            for name, digest in hashes.items():
                if not ASSET_NAME.fullmatch(name) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
                    raise ValueError("备份资源路径或哈希无效。")
            db_digest = manifest.get("database_sha256")
            if not isinstance(db_digest, str) or not SHA256.fullmatch(db_digest):
                raise ValueError("备份数据库哈希无效。")
            if set(names) != {"manifest.json", "rannovel.db"} | {f"assets/{name}" for name in hashes}:
                raise ValueError("备份目录不完整或含有额外文件。")
            for member, destination, expected in [("rannovel.db", db, db_digest)] + [
                (f"assets/{name}", assets / name, digest) for name, digest in hashes.items()
            ]:
                digest = hashlib.sha256()
                size = 0
                with archive.open(member) as input_file, destination.open("xb") as output_file:
                    for chunk in iter(lambda: input_file.read(CHUNK_SIZE), b""):
                        size += len(chunk)
                        if size > MAX_ENTRY_BYTES:
                            raise ValueError(f"备份文件解压大小超限：{member}")
                        output_file.write(chunk)
                        digest.update(chunk)
                if digest.hexdigest() != expected:
                    raise ValueError(f"备份校验失败：{member}")
        if validate_library(db, SCHEMA_VERSION) != hashes:
            raise ValueError("数据库与资源清单不匹配。")
    except (zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError, sqlite3.DatabaseError) as error:
        raise ValueError("ZIP 备份无效或损坏。") from error
    return db, assets


def _recovery_archive(snapshot, backup_dir, assets_dir, reason):
    """Preserve damaged current data without pretending it is a valid restore ZIP."""
    output = backup_dir / _archive_name("recovery_before_restore")
    pending = output.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(pending, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "rannovel.db")
            if assets_dir.is_dir():
                for path in sorted(assets_dir.iterdir()):
                    if path.is_file() and not path.is_symlink():
                        archive.write(path, f"assets/{path.name}")
            archive.writestr("RECOVERY_README.txt",
                "这是恢复前的原始资料留存，当前资料未通过正常备份检查。\n"
                "该 ZIP 用于人工取回数据，不可直接用“从 ZIP 恢复”导入。\n"
                f"检查失败原因：{reason}\n")
        os.replace(pending, output)
    finally:
        pending.unlink(missing_ok=True)
    return output


def restore_backup(archive_file: Path, database, backup_dir: Path, assets_dir: Path | None = None) -> Path:
    archive_file, backup_dir = Path(archive_file), Path(backup_dir)
    assets_dir = Path(assets_dir) if assets_dir else database.database_file.parent / "assets"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Keep directory renames on the same filesystem even when backups live on another drive.
    with tempfile.TemporaryDirectory(prefix="rannovel_restore_", dir=assets_dir.parent) as temporary:
        stage = Path(temporary)
        incoming_db, incoming_assets = _extract_validated(archive_file, stage)
        database.close()
        original_db = stage / "before_restore.db"
        _snapshot(database.database_file, original_db)
        try:
            safety = create_backup(original_db, backup_dir, assets_dir)
        except (ValueError, FileNotFoundError) as error:
            safety = _recovery_archive(original_db, backup_dir, assets_dir, error)
        old_assets = stage / "before_restore_assets"
        moved_old = installed_new = False
        try:
            if assets_dir.exists():
                os.replace(assets_dir, old_assets)
                moved_old = True
            os.replace(incoming_assets, assets_dir)
            installed_new = True
            _snapshot(incoming_db, database.database_file)
            database.initialize()
            return safety
        except Exception as error:
            database.close()
            try:
                _snapshot(original_db, database.database_file)
                if installed_new:
                    os.replace(assets_dir, stage / "failed_restore_assets")
                if moved_old:
                    os.replace(old_assets, assets_dir)
                database.initialize()
            except Exception as rollback_error:
                # Never let TemporaryDirectory erase the last surviving original images.
                if old_assets.exists():
                    preserved = assets_dir.parent / f"recovery_assets_{uuid.uuid4().hex}"
                    os.replace(old_assets, preserved)
                raise RuntimeError(f"恢复与回退均失败；原始资料留存在安全备份：{safety}") from rollback_error
            raise RuntimeError(f"恢复失败，已回退；安全备份：{safety}") from error
