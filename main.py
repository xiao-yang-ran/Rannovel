"""Bootstrap the private Windows runtime without changing system settings."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parent
_dll_handles = []


def configure_runtime() -> None:
    runtime = ROOT / "runtime"
    if Path(sys.executable).resolve().parent != runtime:
        raise RuntimeError("请双击 Start_RanNovel.cmd，使用随项目附带的运行时启动。")
    sys.dont_write_bytecode = True
    site = runtime / "Lib" / "site-packages"
    qt = site / "PySide6"
    directories = (runtime, qt, site / "shiboken6")
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    os.environ["PATH"] = os.pathsep.join(map(str, (*directories, system / "System32", system)))
    for key in ("PYTHONHOME", "PYTHONPATH", "QT_QPA_PLATFORMTHEME", "QT_STYLE_OVERRIDE", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
        os.environ.pop(key, None)
    plugins = qt / "plugins"
    os.environ["QT_PLUGIN_PATH"] = str(plugins)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins / "platforms")
    os.environ["QT_QPA_PLATFORM"] = "windows"
    for directory in directories:
        _dll_handles.append(os.add_dll_directory(str(directory)))
    os.chdir(ROOT)
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.setLibraryPaths([str(plugins)])


def launch() -> int:
    try:
        configure_runtime()
        from app.main import main
        return main()
    except Exception:
        details = traceback.format_exc()
        if sys.stderr is not None:
            sys.stderr.write(details)
        message = "RanNovel 无法启动。请确认已完整解压发布文件夹，并且当前文件夹允许写入。"
        try:
            log = ROOT / "userdata" / "startup-error.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(details, encoding="utf-8")
            message += f"\n\n错误记录：{log}"
        except OSError:
            message += "\n\n" + details
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "RanNovel", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(launch())
