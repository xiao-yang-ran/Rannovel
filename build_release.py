"""Build a reproducible source release containing no user data or test files."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import zipfile
from pathlib import Path

from app import __version__

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "README.md", "RELEASE_NOTES.md", "requirements.txt", "main.py", "RanNovel.pyw",
    "图标.ico", "create_rannovel_shortcut.ps1", "build_release.py",
    "tools/create_shortcut.ps1",
]


def release_files():
    files = set(REQUIRED)
    for path in (ROOT / "app").rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(part.startswith(("test", "_verify")) for part in relative.parts):
            continue
        files.add(relative.as_posix())
    return sorted(files)


def write_member(archive, name, content):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def main():
    output = ROOT / f"RanNovel_{__version__}_final.zip"
    pending = output.with_suffix(".zip.tmp")
    hashes = {}
    try:
        with zipfile.ZipFile(pending, "w") as archive:
            for relative in release_files():
                source = ROOT / relative
                if source.is_symlink() or not source.is_file():
                    raise FileNotFoundError(source)
                content = source.read_bytes()
                if source.suffix in {".py", ".pyw"}:
                    ast.parse(content.decode("utf-8-sig"), filename=relative, feature_version=(3, 10))
                hashes[relative] = hashlib.sha256(content).hexdigest()
                write_member(archive, relative, content)
            manifest = {"application": "RanNovel", "version": __version__, "sha256": hashes}
            write_member(archive, "release-manifest.json",
                         json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
        os.replace(pending, output)
    finally:
        pending.unlink(missing_ok=True)
    return output


if __name__ == "__main__":
    print(main())
