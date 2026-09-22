"""Build a source-only release; never package personal data."""
from __future__ import annotations
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ["README.md", "requirements.txt", "main.py", "RanNovel.pyw", "图标.ico",
         "create_rannovel_shortcut.ps1", "build_release.py"]
FILES += [str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "app").rglob("*.py")]
FILES += [str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "tools").glob("*.ps1")]


def main():
    output = ROOT / "RanNovel_1.0_final.zip"
    temporary = output.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in FILES:
                source = ROOT / relative
                if not source.is_file(): raise FileNotFoundError(source)
                archive.write(source, relative)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output

if __name__ == "__main__": print(main())
