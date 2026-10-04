"""RanNovel main window interface."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget
from app.ui.dialogs import pick_record, run_job
from app.services.backup_service import create_backup, restore_backup
from app.services.repository import KINDS
from app.ui.decor import HeroPanel
from app.ui.common import NAV, ask_text, show_error
from app.ui.writing import WritingPage
from app.ui.entities import EntityPage
from app.ui.inspirations import InspirationPage, UsedInspirationDialog
from app.ui.graph import RelationGraph


class MainWindow(QMainWindow):
    def __init__(self, repo, paths):
        super().__init__(); self.repo, self.paths = repo, paths
        self.setWindowTitle("RanNovel · 一间写故事的书房"); self.resize(1400, 900)
        self.current_work_id = None; self.page_cache = {}
        self.last_nav_index = 0
        central = QWidget(); root = QHBoxLayout(central); self.setCentralWidget(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(225)
        side_layout = QVBoxLayout(sidebar)
        brand = QLabel("RanNovel"); brand.setObjectName("brand"); side_layout.addWidget(brand)
        subtitle = QLabel("一间写故事的书房"); subtitle.setObjectName("subtitle"); side_layout.addWidget(subtitle)
        side_layout.addSpacing(24)
        label = QLabel("创 作 空 间"); label.setObjectName("navSection"); side_layout.addWidget(label)
        self.navigation = QListWidget(); self.navigation.setObjectName("navigation")
        for _, label in NAV: self.navigation.addItem(label)
        side_layout.addWidget(self.navigation, 1)
        notice = QLabel("● 离线创作 · 数据仅在本机"); notice.setObjectName("localNotice"); side_layout.addWidget(notice)
        root.addWidget(sidebar)
        content = QWidget(); content.setObjectName("contentSurface")
        content_layout = QVBoxLayout(content)
        self.hero = HeroPanel(); content_layout.addWidget(self.hero)
        self.pages = QStackedWidget(); content_layout.addWidget(self.pages, 1)
        root.addWidget(content, 1)
        self.navigation.currentRowChanged.connect(self.change_page)
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction("已使用灵感…", self.show_used_inspirations)
        file_menu.addSeparator()
        file_menu.addAction("立即备份…", self.backup)
        file_menu.addAction("从 ZIP 恢复…", self.restore)
        file_menu.addSeparator(); file_menu.addAction("退出", self.close)
        self.work_menu = self.menuBar().addMenu("作品")
        self.rebuild_work_menu()
        works = repo.list_works()
        if works: self.current_work_id = works[0].id
        self.navigation.setCurrentRow(0)
        self.statusBar().showMessage("完全离线 · 数据保存在程序文件夹内的 userdata")
    def rebuild_work_menu(self):
        self.work_menu.clear()
        self.work_menu.addAction("新建作品…", self.new_work)
        self.work_menu.addAction("打开作品…", self.open_work)
        self.work_menu.addAction("归档当前作品", self.archive_current)
        self.work_menu.addAction("查看归档作品…", self.open_archived)
        self.work_menu.addAction("恢复当前作品到常用列表", self.restore_current)
        self.work_menu.addSeparator()
        for work in self.repo.list_works():
            self.work_menu.addAction(f"{KINDS[work.kind]} · {work.title}", lambda checked=False, i=work.id: self.switch_work(i))
    def new_work(self):
        if not self.flush_editor(): return
        title = ask_text(self, "新建作品", "作品名称")
        if not title: return
        kinds = ["长篇", "随笔", "片段"]
        label, ok = QInputDialog.getItem(self, "写作模式", "选择模式", kinds, 0, False)
        if ok:
            try:
                work_id = self.repo.create_work(title, list(KINDS)[kinds.index(label)])
                if not self.switch_work(work_id): self.rebuild_work_menu()
            except Exception as error: show_error(self, error)
    def open_work(self): self.choose_work(False)
    def show_used_inspirations(self):
        UsedInspirationDialog(self.repo, self).exec()
        page = self.page_cache.get(("inspiration", None))
        if page: page.refresh()
    def open_archived(self): self.choose_work(True)
    def choose_work(self, archived):
        works = self.repo.list_works(archived)
        def load(query, limit, offset):
            rows = [work for work in works if query.strip().casefold() in work.title.casefold()]
            return [(work.id, f"#{work.id} {KINDS[work.kind]} · {work.title}") for work in rows[offset:offset+limit]]
        work_id = pick_record(self, "归档作品" if archived else "打开作品", load)
        if work_id is not None:
            self.switch_work(work_id)

    def archive_current(self):
        if self.current_work_id and self.flush_editor():
            try:
                old_id = self.current_work_id
                self.repo.archive_work(old_id, True)
                self._discard_work_pages(old_id)
                self.current_work_id = None
                self.rebuild_work_menu()
                self.show_current()
            except Exception as error:
                show_error(self, error)

    def restore_current(self):
        if self.current_work_id:
            try:
                self.repo.archive_work(self.current_work_id, False)
                self.rebuild_work_menu()
            except Exception as error:
                show_error(self, error)

    def flush_editor(self):
        for page in self.page_cache.values():
            if isinstance(page, WritingPage) and not page.save_now(): return False
        return True
    def _discard_work_pages(self, work_id):
        for key, page in list(self.page_cache.items()):
            if key[1] == work_id:
                if isinstance(page, WritingPage):
                    page.dispose()
                self.pages.removeWidget(page)
                page.deleteLater()
                del self.page_cache[key]
        try:
            self.repo.collect_unused_assets()
        except Exception as error:
            QMessageBox.warning(self, "图片清理", f"正文已保存，未使用图片暂未清理：{error}")

    def switch_work(self, work_id):
        if not self.flush_editor(): return False
        old_id = self.current_work_id
        if old_id is not None and old_id != work_id:
            self._discard_work_pages(old_id)
        self.current_work_id = work_id; self.show_current(); self.rebuild_work_menu()
        work = self.repo.get_work(work_id)
        self.statusBar().showMessage(f"正在编辑：{work.title}" + (" · 已归档" if work.archived else ""))
        return True
    def change_page(self, index):
        if index < 0:
            return
        if not self.flush_editor():
            self.navigation.blockSignals(True)
            self.navigation.setCurrentRow(self.last_nav_index)
            self.navigation.blockSignals(False)
            return
        self.last_nav_index = index
        self.hero.title.setText(NAV[index][1])
        self.hero.subline.setText("在这里继续写下你的故事。")
        self.show_current()

    def show_current(self):
        index = self.navigation.currentRow()
        if index < 0: return
        kind = NAV[index][0]
        work = self.repo.get_work(self.current_work_id) if self.current_work_id else None
        created = False
        if kind in {"write", "event", "setting", "location"} and not work:
            key = ("empty", None)
            if key not in self.page_cache:
                label = QLabel("从左上角“作品”新建或打开作品。")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.page_cache[key] = label; self.pages.addWidget(label)
        elif kind in {"event", "setting", "location"} and work.kind != "novel":
            key = ("novel_only", None)
            if key not in self.page_cache:
                label = QLabel("此资料按长篇独立保存；请选择长篇作品。")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.page_cache[key] = label; self.pages.addWidget(label)
        else:
            key = (kind, self.current_work_id if kind in {"write", "event", "setting", "location"} else None)
            created = key not in self.page_cache
            if created:
                page = (WritingPage(self.repo, work.id) if kind == "write" else
                        InspirationPage(self.repo, lambda: self.current_work_id) if kind == "inspiration" else
                        RelationGraph(self.repo) if kind == "graph" else
                        EntityPage(self.repo, kind, work.id if kind != "character" else None))
                self.page_cache[key] = page; self.pages.addWidget(page)
        page = self.page_cache[key]
        if not created and not isinstance(page, WritingPage) and hasattr(page, "refresh"): page.refresh()
        if isinstance(page, WritingPage) and page.refs:
            page.refs.refresh()
        self.pages.setCurrentWidget(page)
    def backup(self):
        if not self.flush_editor():
            return
        folder = QFileDialog.getExistingDirectory(self, "选择备份目录", str(self.paths.backup_dir))
        if folder:
            try:
                output = run_job(self, "正在校验并备份资料", lambda:
                    create_backup(self.paths.database_file, Path(folder), self.paths.assets_dir))
                QMessageBox.information(self, "备份完成", str(output))
            except Exception as error:
                show_error(self, error)

    def restore(self):
        if not self.flush_editor():
            return
        file, _ = QFileDialog.getOpenFileName(self, "选择备份", str(self.paths.backup_dir), "ZIP (*.zip)")
        if not file:
            return
        if QMessageBox.question(self, "确认恢复", "恢复将替换当前资料；程序会先创建安全备份。继续吗？") != QMessageBox.StandardButton.Yes:
            return
        pending = [(timer, max(1, timer.remainingTime())) for timer in self.findChildren(QTimer) if timer.isActive()]
        for timer, _ in pending:
            timer.stop()
        restored = False
        try:
            safety = run_job(self, "正在校验并恢复资料", lambda:
                restore_backup(Path(file), self.repo.database, self.paths.backup_dir, self.paths.assets_dir))
            restored = True
            for page in self.page_cache.values():
                if isinstance(page, WritingPage):
                    page.dispose()
                self.pages.removeWidget(page)
                page.deleteLater()
            self.page_cache.clear()
            works = self.repo.list_works()
            self.current_work_id = works[0].id if works else None
            self.rebuild_work_menu()
            self.show_current()
            message = f"安全备份：{safety}"
            if safety.name.startswith("recovery_"):
                message += "\n原资料未通过完整性检查，已保留原始数据供人工取回。"
            QMessageBox.information(self, "恢复完成", message)
        except Exception as error:
            show_error(self, error)
        finally:
            if not restored:
                for timer, interval in pending:
                    timer.start(interval)

    def closeEvent(self, event):
        if not self.flush_editor():
            event.ignore()
            return
        for page in self.page_cache.values():
            if isinstance(page, WritingPage):
                page.dispose()
        for timer in self.findChildren(QTimer):
            timer.stop()
        try:
            _, failures = self.repo.collect_unused_assets()
            if failures:
                QMessageBox.warning(self, "图片清理", "部分未使用图片被占用，将在下次清理时重试。")
        except Exception as error:
            QMessageBox.warning(self, "图片清理", f"正文已保存，未使用图片暂未清理：{error}")
        event.accept()
