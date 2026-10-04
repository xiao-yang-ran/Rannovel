"""RanNovel media interface."""
from __future__ import annotations
import tempfile
from pathlib import Path
from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap, QTextImageFormat
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QTextEdit, QVBoxLayout, QWidget
from app.domain import asset_names
from app.ui.common import button, show_error


class ImageTextEdit(QTextEdit):
    image_added = Signal(str)
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.asset_owner = id(self)
        self.setAcceptDrops(True)
        self.document().setBaseUrl(QUrl.fromLocalFile(str(repo.paths.data_dir) + "/"))
        self.destroyed.connect(lambda _=None, owner=self.asset_owner: repo.release_assets(owner))

    def reset_asset_protection(self):
        self.repo.release_assets(self.asset_owner)
        self.repo.protect_assets(self.asset_owner, asset_names(self.toHtml()))


    def canInsertFromMimeData(self, source):
        return bool(source.hasUrls() and any(u.isLocalFile() for u in source.urls())) or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasUrls():
            paths = [u.toLocalFile() for u in source.urls() if u.isLocalFile()]
            if paths:
                for path in paths:
                    self.insert_image(path)
                return
        if source.hasHtml():
            try:
                names = asset_names(source.html())
                if any(not (self.repo.paths.assets_dir / name).is_file() for name in names):
                    raise ValueError("图片资源已不存在。")
                self.repo.protect_assets(self.asset_owner, names)
            except ValueError:
                self.insertPlainText(source.text())
                QMessageBox.information(self, "已粘贴文字", "外部图片未粘贴，请用“插入图片”或拖入图片文件添加。")
                return
        elif source.hasImage():
            image = QImage(source.imageData())
            if not image.isNull():
                with tempfile.TemporaryDirectory(prefix="clipboard_", dir=self.repo.paths.data_dir) as temporary:
                    path = Path(temporary) / "clipboard.png"
                    if image.save(str(path), "PNG"):
                        self.insert_image(path)
                return
        super().insertFromMimeData(source)


    def insert_image(self, path):
        try:
            _, relative = self.repo.import_image(path)
            self.repo.protect_assets(self.asset_owner, {relative.removeprefix("assets/")})
            fmt = QTextImageFormat()
            fmt.setName(relative)
            image = QImage(str(self.repo.paths.data_dir / relative))
            if image.isNull():
                raise ValueError("图片无法读取。")
            if image.width() > 680:
                fmt.setWidth(680)
                fmt.setHeight(680 * image.height() / image.width())
            self.textCursor().insertImage(fmt)
            self.image_added.emit(relative)
        except Exception as error:
            show_error(self, error)


class GalleryList(QListWidget):
    files_dropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setIconSize(QSize(96, 72))
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths: self.files_dropped.emit(paths); event.acceptProposedAction()
        else: super().dropEvent(event)


class GalleryDialog(QDialog):
    def __init__(self, repo, kind, source_id, parent=None):
        super().__init__(parent)
        self.repo, self.kind, self.source_id = repo, kind, source_id
        self.setWindowTitle("条目配图 · 可拖入本地图片")
        self.resize(550, 430)
        layout = QVBoxLayout(self)
        self.list = GalleryList(); layout.addWidget(self.list)
        self.list.files_dropped.connect(self.add_paths)
        self.list.itemDoubleClicked.connect(self.preview)
        row = QHBoxLayout(); layout.addLayout(row)
        button("添加图片…", self.select_files, row)
        button("移除选中图片", self.remove_selected, row)
        button("关闭", self.accept, row)
        self.refresh()
    def refresh(self):
        self.list.clear()
        for link, path in self.repo.gallery(self.kind, self.source_id):
            item = QListWidgetItem(path.name if path.exists() else f"文件丢失：{path.name}")
            item.setData(Qt.ItemDataRole.UserRole, link.id)
            if path.exists(): item.setIcon(QIcon(QPixmap(str(path)).scaled(96, 72, Qt.AspectRatioMode.KeepAspectRatio)))
            self.list.addItem(item)
    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添加本地图片", str(Path.home()), "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        self.add_paths(paths)
    def add_paths(self, paths):
        for path in paths:
            try:
                self.repo.import_gallery_image(self.kind, self.source_id, path)
            except Exception as error:
                show_error(self, error)
        self.refresh()

    def remove_selected(self):
        item = self.list.currentItem()
        if item and QMessageBox.question(self, "移除图片", "从此图库移除所选图片？") == QMessageBox.StandardButton.Yes:
            try:
                _, failures = self.repo.remove_gallery_image(item.data(Qt.ItemDataRole.UserRole))
                self.refresh()
                if failures:
                    QMessageBox.warning(self, "图片清理", "图片已解除关联，但部分文件被占用，将在下次清理时重试。")
            except Exception as error:
                show_error(self, error)

    def preview(self, item):
        for link, path in self.repo.gallery(self.kind, self.source_id):
            if link.id != item.data(Qt.ItemDataRole.UserRole): continue
            if not path.exists(): show_error(self, FileNotFoundError(path)); return
            dialog = QDialog(self); dialog.setWindowTitle(path.name); dialog.resize(800, 600)
            layout = QVBoxLayout(dialog); label = QLabel(); label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setPixmap(QPixmap(str(path)).scaled(760, 540, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(label); button("关闭", dialog.accept, layout); dialog.exec(); return


def image_controls(form, repo, kind, item_id, parent):
    """Choose optional images before saving; manage existing images on this item."""
    pending = []
    container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0, 0, 0, 0)
    status = QLabel(); row.addWidget(status)
    def update_status():
        existing = len(repo.gallery(kind, item_id)) if item_id is not None else 0
        status.setText(f"已有 {existing} 张 · 待添加 {len(pending)} 张" if pending else
                       f"已有 {existing} 张" if existing else "无图片")
    def select_files():
        paths, _ = QFileDialog.getOpenFileNames(parent, "为此条目选择图片", str(Path.home()),
                                                "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        pending.extend(paths)
        update_status()
    update_status()
    button("选择图片…", select_files, row)
    if item_id is not None:
        def manage_images():
            GalleryDialog(repo, kind, item_id, parent).exec(); update_status()
        button("管理已有图片（立即生效）…", manage_images, row)
    form.addRow("配图（可选）", container)
    return pending


def attach_images(repo, kind, item_id, paths):
    errors = []
    for path in paths:
        try:
            repo.import_gallery_image(kind, item_id, path)
        except Exception as error:
            errors.append(f"{Path(path).name}：{error}")
    if errors:
        raise ValueError("\n".join(errors))
