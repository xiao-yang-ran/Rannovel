"""Use the Chinese Qt translations bundled with PySide6."""

from __future__ import annotations

from pathlib import Path

import PySide6
from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication


def install_chinese_qt_translations(app: QApplication) -> bool:
    QLocale.setDefault(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    translation_file = (
        Path(PySide6.__file__).resolve().parent
        / "translations"
        / "qtbase_zh_CN.qm"
    )
    translator = QTranslator(app)
    if not translator.load(str(translation_file)):
        return False
    app.installTranslator(translator)
    # Keep the Python wrapper alive for the lifetime of the application.
    app._rannovel_qt_translator = translator
    return True
