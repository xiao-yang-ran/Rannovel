"""Single RanNovel application entry point."""
from __future__ import annotations
import sys
from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from app.config import AppPaths, inspect_legacy_library
from app.database import Database
from app.services.repository import LibraryRepository
from app.ui.locale import install_chinese_qt_translations
from app.ui.main_window import MainWindow
from app.ui.style import APP_STYLE


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RanNovel"); app.setOrganizationName("RanNovel")
    install_chinese_qt_translations(app)
    app.setStyle("Fusion"); app.setStyleSheet(APP_STYLE)
    paths = AppPaths.default()
    icon = paths.project_root / "resources" / "RanNovel.ico"
    if icon.is_file(): app.setWindowIcon(QIcon(str(icon)))
    database = None
    lock = None
    try:
        paths.ensure_directories()
        lock = QLockFile(str(paths.data_dir / "rannovel.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise RuntimeError("RanNovel 已在运行，或资料目录无法加锁。请先关闭已有窗口。")
        counts = inspect_legacy_library(paths.project_root)
        if any(counts.values()):
            raise RuntimeError("程序目录中的旧资料库含有创作数据。请先备份并人工处理；程序不会自动覆盖或忽略它。")
        database = Database(paths.database_file)
        database.initialize()
        window = MainWindow(LibraryRepository(database, paths), paths)
        window.show()
        return app.exec()
    except Exception as error:
        QMessageBox.critical(None, "RanNovel 无法启动", str(error))
        return 1
    finally:
        if database is not None:
            database.close()
        if lock is not None:
            lock.unlock()
