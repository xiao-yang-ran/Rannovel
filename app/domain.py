"""Shared library rules and managed image references."""
from __future__ import annotations

import re
from html.parser import HTMLParser

KINDS = {"novel": "长篇", "essay": "随笔", "fragment": "片段"}
TARGET_PERMISSIONS = {
    "chapter": {"character", "location", "event", "setting", "inspiration"},
    "essay": {"inspiration"},
    "fragment": {"character", "inspiration"},
}
GALLERY_KINDS = {"character", "location", "inspiration"}
ASSET_NAME = re.compile(r"[0-9a-f]{32}\.(?:png|jpg|bmp|gif|webp)")
SHA256 = re.compile(r"[0-9a-f]{64}")


class _ImageSources(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.sources.append(dict(attrs).get("src") or "")


def image_sources(html: str) -> list[str]:
    parser = _ImageSources()
    parser.feed(html)
    parser.close()
    return parser.sources


def asset_names(html: str) -> set[str]:
    names = set()
    for source in image_sources(html):
        if not source.startswith("assets/") or not ASSET_NAME.fullmatch(source[7:]):
            raise ValueError("正文图片必须导入本地资源目录，不能引用外部路径或 Base64 数据。")
        names.add(source[7:])
    return names


def search_pattern(query: str) -> str:
    """Treat user input literally, including SQL LIKE wildcard characters."""
    escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
