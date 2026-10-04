from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    data_dir: Path
    database_file: Path
    backup_dir: Path
    assets_dir: Path

    @classmethod
    def default(cls) -> "AppPaths":
        root = Path(__file__).resolve().parents[1]
        appdata = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        data = appdata / "RanNovel"
        return cls(root, data, data / "rannovel.db", data / "backups", data / "assets")

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.backup_dir, self.assets_dir):
            directory.mkdir(parents=True, exist_ok=True)


def inspect_legacy_library(project_root: Path) -> dict[str, int]:
    """Read only: never move or modify the old program-local database."""
    legacy = Path(project_root) / "data" / "rannovel.db"
    if not legacy.is_file(): return {}
    connection = sqlite3.connect(legacy.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        ignored = {"tags", "sqlite_sequence"}
        return {name: connection.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"' ).fetchone()[0]
                for name in names - ignored}
    finally:
        connection.close()
