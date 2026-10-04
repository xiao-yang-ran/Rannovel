"""Library operations and cross-domain invariants."""
from __future__ import annotations

import hashlib
import html as html_lib
import re
import uuid
from pathlib import Path
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import load_only, selectinload
from app.domain import ASSET_NAME, GALLERY_KINDS, KINDS, TARGET_PERMISSIONS, asset_names, search_pattern
from app.models import (Asset, Chapter, Character, CharacterRelation, Event, EventCharacter, Faction,
                        GalleryImage, Inspiration, Location, Reference, Setting, Volume, Work)

SOURCE_MODELS = {"character": Character, "location": Location, "event": Event, "setting": Setting}


class LibraryRepository:
    def __init__(self, database, paths):
        self.database, self.paths = database, paths
        self._protected_assets = {}

    def protect_assets(self, owner, names):
        # Include removed images until the editor's undo history has been discarded.
        self._protected_assets.setdefault(owner, set()).update(names)

    def release_assets(self, owner):
        self._protected_assets.pop(owner, None)

    def collect_unused_assets(self):
        protected = set().union(*self._protected_assets.values()) if self._protected_assets else set()
        with self.database.session_factory.begin() as s:
            s.connection().exec_driver_sql("BEGIN IMMEDIATE")
            used = set(s.scalars(select(Asset.filename).join(GalleryImage, GalleryImage.asset_id == Asset.id)))
            for model in (Work, Chapter):
                for body in s.scalars(select(model.body_html)):
                    used.update(asset_names(body))
            used.update(protected)
            for asset in s.scalars(select(Asset)):
                if asset.filename not in used and ASSET_NAME.fullmatch(asset.filename):
                    s.delete(asset)
            s.flush()
            kept = set(s.scalars(select(Asset.filename))) | protected
        removed, failures = 0, []
        for path in self.paths.assets_dir.iterdir():
            if ASSET_NAME.fullmatch(path.name) and path.name not in kept and path.is_file() and not path.is_symlink():
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    failures.append(path.name)
        return removed, failures


    def list_works(self, archived=False):
        with self.database.session_factory() as s:
            return list(s.scalars(select(Work).options(load_only(Work.id, Work.title, Work.kind, Work.archived, Work.word_count)).where(Work.archived == archived).order_by(Work.id.desc())))

    def get_work(self, work_id):
        with self.database.session_factory() as s:
            return s.get(Work, work_id)

    def create_work(self, title, kind):
        if kind not in KINDS or not title.strip():
            raise ValueError("请选择写作模式并填写作品名称。")
        with self.database.session_factory.begin() as s:
            item = Work(title=title.strip(), kind=kind)
            s.add(item); s.flush()
            return item.id

    def rename_work(self, work_id, title):
        if not title.strip():
            raise ValueError("作品名称不能为空。")
        with self.database.session_factory.begin() as s:
            item = s.get(Work, work_id)
            if item is None:
                raise LookupError("作品不存在。")
            item.title = title.strip()


    def archive_work(self, work_id, archived=True):
        with self.database.session_factory.begin() as s:
            item = s.get(Work, work_id)
            if item is None: raise LookupError("作品不存在。")
            item.archived = archived

    def _novel(self, s, work_id):
        work = s.get(Work, work_id)
        if work is None or work.kind != "novel": raise ValueError("此操作只适用于长篇。")
        return work

    def list_volumes(self, work_id):
        with self.database.session_factory() as s:
            self._novel(s, work_id)
            return list(s.scalars(select(Volume).options(selectinload(Volume.chapters).load_only(Chapter.id, Chapter.volume_id, Chapter.title, Chapter.summary, Chapter.core_events, Chapter.estimated_words, Chapter.sort_order, Chapter.word_count)).where(Volume.work_id == work_id).order_by(Volume.sort_order, Volume.id)))

    def add_volume(self, work_id, title, summary=""):
        with self.database.session_factory.begin() as s:
            self._novel(s, work_id)
            order = s.scalar(select(func.max(Volume.sort_order)).where(Volume.work_id == work_id)) or 0
            item = Volume(work_id=work_id, title=title.strip(), summary=summary, sort_order=order+10)
            if not item.title: raise ValueError("卷名不能为空。")
            s.add(item); s.flush(); return item.id

    def add_chapter(self, volume_id, title, summary="", core_events="", estimated_words=0):
        with self.database.session_factory.begin() as s:
            volume = s.get(Volume, volume_id)
            if volume is None: raise LookupError("分卷不存在。")
            order = s.scalar(select(func.max(Chapter.sort_order)).where(Chapter.volume_id == volume_id)) or 0
            item = Chapter(volume_id=volume_id, title=title.strip(), summary=summary,
                           core_events=core_events, estimated_words=max(0, int(estimated_words)), sort_order=order+10)
            if not item.title: raise ValueError("章节名不能为空。")
            s.add(item); s.flush(); return item.id

    def rename_outline(self, kind, item_id, title):
        model = {"volume": Volume, "chapter": Chapter}[kind]
        if not title.strip():
            raise ValueError("名称不能为空。")
        with self.database.session_factory.begin() as s:
            item = s.get(model, item_id)
            if item is None:
                raise LookupError("卷章不存在。")
            item.title = title.strip()


    def update_outline_details(self, kind, item_id, summary, core_events="", estimated_words=0):
        model = {"volume": Volume, "chapter": Chapter}[kind]
        with self.database.session_factory.begin() as s:
            item = s.get(model, item_id)
            if item is None: raise LookupError("卷章不存在。")
            item.summary = summary
            if kind == "chapter":
                item.core_events = core_events
                item.estimated_words = max(0, int(estimated_words))

    def move_outline(self, kind, item_id, direction):
        model = {"volume": Volume, "chapter": Chapter}[kind]
        with self.database.session_factory.begin() as s:
            item = s.get(model, item_id)
            if item is None: raise LookupError("卷章不存在。")
            scope = model.work_id == item.work_id if kind == "volume" else model.volume_id == item.volume_id
            peers = list(s.scalars(select(model).where(scope).order_by(model.sort_order, model.id)))
            index = peers.index(item); target = index + direction
            if 0 <= target < len(peers): item.sort_order, peers[target].sort_order = peers[target].sort_order, item.sort_order

    def delete_outline(self, kind, item_id):
        model = {"volume": Volume, "chapter": Chapter}[kind]
        with self.database.session_factory.begin() as s:
            item = s.get(model, item_id)
            if item is None: return
            if kind == "volume":
                if s.scalar(select(func.count(Chapter.id)).where(Chapter.volume_id == item_id)):
                    raise ValueError("此卷包含章节，请先逐章处理。")
            else:
                refs = s.scalar(select(func.count(Reference.id)).where(Reference.target_kind == "chapter", Reference.target_id == item_id))
                ideas = s.scalar(select(func.count(Inspiration.id)).where(Inspiration.target_kind == "chapter", Inspiration.target_id == item_id))
                body_without_head = re.sub(r"<head\b[^>]*>.*?</head>", "", item.body_html, flags=re.IGNORECASE | re.DOTALL)
                plain_body = html_lib.unescape(re.sub(r"<[^>]+>", "", body_without_head)).strip()
                if item.word_count or plain_body or "<img" in item.body_html.lower() or refs or ideas:
                    raise ValueError("章节含有正文、图片或关联资料；请先清空并解除关联，再删除。")
            s.delete(item)

    def target_work(self, s, kind, target_id):
        if kind == "chapter":
            chapter = s.get(Chapter, target_id)
            if chapter is None: raise LookupError("章节不存在。")
            return s.get(Volume, chapter.volume_id).work_id
        if kind in ("essay", "fragment"):
            work = s.get(Work, target_id)
            if work is None or work.kind != kind: raise LookupError("正文不存在。")
            return work.id
        raise ValueError("无效正文类型。")

    def get_body(self, kind, target_id):
        with self.database.session_factory() as s:
            self.target_work(s, kind, target_id)
            return s.get(Chapter if kind == "chapter" else Work, target_id)

    def missing_body_images(self, kind, target_id):
        names = asset_names(self.get_body(kind, target_id).body_html)
        return sorted(name for name in names if not (self.paths.assets_dir / name).is_file())


    def save_body(self, kind, target_id, html, word_count):
        names = asset_names(html)
        with self.database.session_factory.begin() as s:
            self.target_work(s, kind, target_id)
            registered = set(s.scalars(select(Asset.filename).where(Asset.filename.in_(names)))) if names else set()
            if registered != names or any(not (self.paths.assets_dir / name).is_file() for name in names):
                raise ValueError("正文图片引用的资源不存在。")
            item = s.get(Chapter if kind == "chapter" else Work, target_id)
            item.body_html = html
            item.word_count = max(0, int(word_count))


    def list_entities(self, kind, work_id=None, query="", limit=200, offset=0, category=None):
        model = SOURCE_MODELS[kind]
        with self.database.session_factory() as s:
            statement = select(model)
            if kind != "character":
                self._novel(s, work_id)
                statement = statement.where(model.work_id == work_id)
            if category and kind in ("location", "setting"):
                statement = statement.where(model.category == category)
            if query.strip():
                searchable = [model.name, model.details]
                if kind == "character": searchable += [model.personality, model.motivation, model.skills, model.background, cast(model.custom_fields, String)]
                if kind == "location": searchable += [model.category, model.layout, model.environment_rules, model.physical_laws, model.notes]
                if kind == "setting": searchable += [model.category, model.overview, model.structure, model.rules, model.advancement, model.limitations, model.relationships, model.notes, cast(model.custom_fields, String)]
                statement = statement.where(or_(*(column.ilike(search_pattern(query), escape="\\") for column in searchable)))
            ordering = (model.year, model.month, model.id) if kind == "event" else (model.id.desc(),)
            return list(s.scalars(statement.order_by(*ordering).limit(limit).offset(offset)))

    def list_categories(self, kind, work_id):
        model = SOURCE_MODELS[kind]
        with self.database.session_factory() as s:
            return list(s.scalars(select(model.category).where(model.work_id == work_id).distinct().order_by(model.category)))

    def get_entity(self, kind, item_id):
        with self.database.session_factory() as s:
            return s.get(SOURCE_MODELS[kind], item_id)

    def save_entity(self, kind, item_id=None, work_id=None, **values):
        model = SOURCE_MODELS[kind]
        with self.database.session_factory.begin() as s:
            if kind != "character": self._novel(s, work_id)
            item = s.get(model, item_id) if item_id else model()
            if item is None: raise LookupError("资料不存在。")
            if item_id and kind != "character" and item.work_id != work_id: raise ValueError("不能跨作品修改资料。")
            item.name = str(values.get("name", "")).strip()
            if not item.name: raise ValueError("名称不能为空。")
            item.details = str(values.get("details", ""))
            if kind != "character": item.work_id = work_id
            extra = {"character": ("personality", "motivation", "skills", "background"),
                      "location": ("category", "layout", "environment_rules", "physical_laws", "notes"),
                      "setting": ("category", "overview", "structure", "rules", "advancement", "limitations", "relationships", "notes")}
            for field in extra.get(kind, ()):
                if field in values: setattr(item, field, str(values[field]))
            if kind == "character":
                if "custom_fields" in values: item.custom_fields = dict(values["custom_fields"])
                if "faction_id" in values:
                    faction_id = values["faction_id"]
                    if faction_id is not None and not s.get(Faction, faction_id): raise ValueError("阵营不存在。")
                    item.faction_id = faction_id
            if kind == "setting" and "custom_fields" in values: item.custom_fields = dict(values["custom_fields"])
            if kind == "event":
                item.year = int(values.get("year", 1))
                item.month = int(values.get("month", 1))
                if not 1 <= item.month <= 12:
                    raise ValueError("月份必须介于 1 到 12。")
            s.add(item); s.flush(); return item.id

    def delete_entity(self, kind, item_id):
        model = SOURCE_MODELS[kind]
        with self.database.session_factory.begin() as s:
            item = s.get(model, item_id)
            if item is None: return
            refs = s.scalar(select(func.count(Reference.id)).where(Reference.source_kind == kind, Reference.source_id == item_id))
            gallery = s.scalar(select(func.count(GalleryImage.id)).where(GalleryImage.source_kind == kind, GalleryImage.source_id == item_id))
            if refs or gallery: raise ValueError(f"该资料被 {refs} 处正文引用、含 {gallery} 张图片；请先解除关联并移除图库图片。")
            if kind == "character" and (s.scalar(select(func.count(CharacterRelation.id)).where(or_(CharacterRelation.source_id == item_id, CharacterRelation.target_id == item_id))) or s.scalar(select(func.count(EventCharacter.event_id)).where(EventCharacter.character_id == item_id))):
                raise ValueError("人物仍有关联关系或时间线事件，请先解除。")
            if kind == "event":
                for link in list(s.scalars(select(EventCharacter).where(EventCharacter.event_id == item_id))): s.delete(link)
            s.delete(item)

    def list_factions(self):
        with self.database.session_factory() as s:
            return list(s.scalars(select(Faction).order_by(Faction.name)))

    def save_faction(self, faction_id=None, name="", kind="阵营", description=""):
        if not name.strip(): raise ValueError("阵营名称不能为空。")
        with self.database.session_factory.begin() as s:
            item = s.get(Faction, faction_id) if faction_id else Faction()
            if item is None: raise LookupError("阵营不存在。")
            item.name, item.kind, item.description = name.strip(), kind.strip() or "阵营", description
            s.add(item); s.flush(); return item.id

    def delete_faction(self, faction_id):
        with self.database.session_factory.begin() as s:
            item = s.get(Faction, faction_id)
            if item is None: return
            if s.scalar(select(func.count(Character.id)).where(Character.faction_id == faction_id)):
                raise ValueError("阵营仍有人物成员，请先解除成员归属。")
            s.delete(item)

    def list_relations(self, character_ids=None):
        with self.database.session_factory() as s:
            statement = select(CharacterRelation)
            if character_ids is not None:
                statement = statement.where(CharacterRelation.source_id.in_(character_ids),
                                            CharacterRelation.target_id.in_(character_ids))
            return list(s.scalars(statement.order_by(CharacterRelation.id)))

    def character_names(self):
        with self.database.session_factory() as s:
            return dict(s.execute(select(Character.id, Character.name)).all())


    def add_relation(self, source_id, target_id, relation_type, details=""):
        if not relation_type.strip():
            raise ValueError("关系名称不能为空。")
        with self.database.session_factory.begin() as s:
            if source_id == target_id or not all(s.get(Character, i) for i in (source_id, target_id)):
                raise ValueError("请选择两个不同的人物。")
            exists = s.scalar(select(CharacterRelation.id).where(
                CharacterRelation.source_id == source_id, CharacterRelation.target_id == target_id,
                CharacterRelation.relation_type == relation_type.strip()))
            if exists:
                raise ValueError("这两个人物之间已存在同名关系。")
            s.add(CharacterRelation(source_id=source_id, target_id=target_id,
                                    relation_type=relation_type.strip(), details=details))


    def delete_relation(self, relation_id):
        with self.database.session_factory.begin() as s:
            item = s.get(CharacterRelation, relation_id)
            if item: s.delete(item)

    def update_relation(self, relation_id, relation_type, details):
        with self.database.session_factory.begin() as s:
            item = s.get(CharacterRelation, relation_id)
            if item is None: raise LookupError("关系不存在。")
            if not relation_type.strip(): raise ValueError("关系名称不能为空。")
            item.relation_type, item.details = relation_type.strip(), details

    def link_event_character(self, event_id, character_id):
        with self.database.session_factory.begin() as s:
            if not s.get(Event, event_id) or not s.get(Character, character_id): raise LookupError("事件或人物不存在。")
            if not s.get(EventCharacter, (event_id, character_id)): s.add(EventCharacter(event_id=event_id, character_id=character_id))

    def event_characters(self, event_id):
        with self.database.session_factory() as s:
            return list(s.scalars(select(Character).join(EventCharacter, EventCharacter.character_id == Character.id)
                                  .where(EventCharacter.event_id == event_id).order_by(Character.name, Character.id)))


    def unlink_event_character(self, event_id, character_id):
        with self.database.session_factory.begin() as s:
            item = s.get(EventCharacter, (event_id, character_id))
            if item: s.delete(item)

    def list_inspirations(self, query="", pool=None, used=None, limit=200, offset=0):
        with self.database.session_factory() as s:
            stmt = select(Inspiration).options(selectinload(Inspiration.owner).load_only(Work.id, Work.title, Work.kind))
            if pool: stmt = stmt.where(Inspiration.pool == pool)
            if used is not None: stmt = stmt.where(Inspiration.owner_work_id.is_not(None) if used else Inspiration.owner_work_id.is_(None))
            if query.strip():
                needle = search_pattern(query)
                stmt = stmt.where(or_(Inspiration.content.ilike(needle, escape="\\"), Inspiration.tags.ilike(needle, escape="\\")))
            return list(s.scalars(stmt.order_by(Inspiration.sort_order, Inspiration.id).limit(limit).offset(offset)))

    def add_inspiration(self, content, tags, pool):
        if pool not in ("essay", "novel") or not content.strip(): raise ValueError("灵感内容和来源池不能为空。")
        with self.database.session_factory.begin() as s:
            order = s.scalar(select(func.max(Inspiration.sort_order)).where(Inspiration.pool == pool)) or 0
            item = Inspiration(content=content.strip(), tags=tags.strip(), pool=pool, sort_order=order+10)
            s.add(item); s.flush(); return item.id

    def available_inspirations(self, work_id, query="", limit=200, offset=0):
        with self.database.session_factory() as s:
            work = s.get(Work, work_id)
            if work is None: raise LookupError("作品不存在。")
            pool = "essay" if work.kind == "essay" else "novel"
            statement = select(Inspiration).where(Inspiration.pool == pool,
                Inspiration.target_id.is_(None),
                or_(Inspiration.owner_work_id.is_(None), Inspiration.owner_work_id == work_id))
            if query.strip():
                needle = search_pattern(query)
                statement = statement.where(or_(Inspiration.content.ilike(needle, escape="\\"), Inspiration.tags.ilike(needle, escape="\\")))
            return list(s.scalars(statement.order_by(Inspiration.sort_order, Inspiration.id).limit(limit).offset(offset)))

    def update_inspiration(self, item_id, content, tags):
        if not content.strip():
            raise ValueError("灵感内容不能为空。")
        with self.database.session_factory.begin() as s:
            item = s.get(Inspiration, item_id)
            if item is None:
                raise LookupError("灵感不存在。")
            item.content, item.tags = content.strip(), tags.strip()

    def get_inspiration(self, item_id):
        with self.database.session_factory() as s:
            return s.get(Inspiration, item_id)


    def reorder_inspiration(self, item_id, direction):
        with self.database.session_factory.begin() as s:
            item = s.get(Inspiration, item_id)
            if item is None:
                raise LookupError("灵感不存在。")
            if item.owner_work_id is not None:
                raise ValueError("只能调整未使用灵感。")
            peers = list(s.scalars(select(Inspiration).where(Inspiration.pool == item.pool,
                Inspiration.owner_work_id.is_(None)).order_by(Inspiration.sort_order, Inspiration.id)))
            i, j = peers.index(item), peers.index(item) + direction
            if 0 <= j < len(peers):
                peers[i], peers[j] = peers[j], peers[i]
                for n, peer in enumerate(peers):
                    peer.sort_order = (n + 1) * 10


    def move_inspiration_before(self, item_id, target_id):
        if item_id == target_id:
            return
        with self.database.session_factory.begin() as s:
            item, target = s.get(Inspiration, item_id), s.get(Inspiration, target_id)
            if not item or not target or item.owner_work_id is not None or target.owner_work_id is not None or item.pool != target.pool:
                raise ValueError("只能在同一个待用池内排序。")
            peers = list(s.scalars(select(Inspiration).where(Inspiration.pool == item.pool,
                Inspiration.owner_work_id.is_(None)).order_by(Inspiration.sort_order, Inspiration.id)))
            peers.remove(item)
            peers.insert(peers.index(target), item)
            for n, peer in enumerate(peers):
                peer.sort_order = (n + 1) * 10


    def assign_inspiration(self, item_id, work_id, target_kind=None, target_id=None):
        with self.database.session_factory.begin() as s:
            item, work = s.get(Inspiration, item_id), s.get(Work, work_id)
            if item is None or work is None: raise LookupError("灵感或作品不存在。")
            required_pool = "essay" if work.kind == "essay" else "novel"
            if item.pool != required_pool: raise ValueError("灵感来源池与作品模式不匹配。")
            if item.owner_work_id is not None and item.owner_work_id != work_id: raise ValueError("灵感只能归属一部作品。")
            if target_kind is not None:
                if target_kind != ("chapter" if work.kind == "novel" else work.kind) or self.target_work(s, target_kind, target_id) != work_id:
                    raise ValueError("灵感只能关联所属作品的正文。")
                if item.target_id is not None and (item.target_kind, item.target_id) != (target_kind, target_id):
                    raise ValueError("灵感已经关联另一篇正文或章节。")
                item.target_kind, item.target_id = target_kind, target_id
            item.owner_work_id = work_id

    def unassign_inspiration(self, item_id):
        with self.database.session_factory.begin() as s:
            item = s.get(Inspiration, item_id)
            if item is None:
                raise LookupError("灵感不存在。")
            item.owner_work_id = item.target_kind = item.target_id = None

    def detach_inspiration(self, item_id):
        """Remove a body link while keeping the inspiration assigned to its work."""
        with self.database.session_factory.begin() as s:
            item = s.get(Inspiration, item_id)
            if item is None:
                raise LookupError("灵感不存在。")
            item.target_kind = item.target_id = None


    def delete_inspiration(self, item_id):
        with self.database.session_factory.begin() as s:
            item = s.get(Inspiration, item_id)
            if item is None: return
            gallery = s.scalar(select(func.count(GalleryImage.id)).where(GalleryImage.source_kind == "inspiration", GalleryImage.source_id == item_id))
            if item.owner_work_id or gallery: raise ValueError("灵感已被使用或含有图片；请先解除归属并移除图片。")
            s.delete(item)

    def add_reference(self, target_kind, target_id, source_kind, source_id):
        if source_kind not in TARGET_PERMISSIONS.get(target_kind, set()) or source_kind == "inspiration": raise ValueError("此正文不允许关联该资料。")
        with self.database.session_factory.begin() as s:
            work_id = self.target_work(s, target_kind, target_id)
            source = s.get(SOURCE_MODELS[source_kind], source_id)
            if source is None or (source_kind != "character" and source.work_id != work_id): raise ValueError("资料不存在或属于另一部长篇。")
            exists = s.scalar(select(Reference.id).where(Reference.target_kind == target_kind, Reference.target_id == target_id, Reference.source_kind == source_kind, Reference.source_id == source_id))
            if not exists: s.add(Reference(target_kind=target_kind, target_id=target_id, source_kind=source_kind, source_id=source_id))

    def remove_reference(self, ref_id):
        with self.database.session_factory.begin() as s:
            item = s.get(Reference, ref_id)
            if item: s.delete(item)

    def references_for(self, target_kind, target_id):
        with self.database.session_factory() as s:
            refs = list(s.scalars(select(Reference).where(
                Reference.target_kind == target_kind, Reference.target_id == target_id)))
            names = {}
            for kind, model in SOURCE_MODELS.items():
                ids = [ref.source_id for ref in refs if ref.source_kind == kind]
                if ids:
                    names.update({(kind, item.id): item.name for item in s.scalars(select(model).where(model.id.in_(ids)))})
            result = [(ref, names.get((ref.source_kind, ref.source_id), f"资料已缺失 #{ref.source_id}，可解除关联"))
                      for ref in refs]
            inspirations = list(s.scalars(select(Inspiration).where(
                Inspiration.target_kind == target_kind, Inspiration.target_id == target_id)))
            return result, inspirations


    def usages(self, source_kind, source_id):
        with self.database.session_factory() as s:
            if source_kind == "inspiration":
                item = s.get(Inspiration, source_id)
                return [(item.target_kind, item.target_id)] if item and item.target_id else []
            refs = s.scalars(select(Reference).where(Reference.source_kind == source_kind, Reference.source_id == source_id)).all()
            return [(r.target_kind, r.target_id) for r in refs]

    def import_image(self, source_path):
        from PySide6.QtGui import QImageReader
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"图片文件不存在：{source}")
        if source.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("单张图片不能超过 50 MiB。")
        reader = QImageReader(str(source))
        fmt = bytes(reader.format()).decode("ascii", "ignore").lower()
        size = reader.size()
        if size.width() * size.height() > 40_000_000:
            raise ValueError("图片像素过大，请缩小到 4000 万像素以内。")
        if fmt not in {"png", "jpeg", "jpg", "bmp", "gif", "webp"} or not reader.canRead() or reader.read().isNull():
            raise ValueError("图片格式无效或文件已损坏；支持 PNG、JPEG、BMP、GIF、WebP。")
        suffix = "jpg" if fmt == "jpeg" else fmt
        name = f"{uuid.uuid4().hex}.{suffix}"
        destination = self.paths.assets_dir / name
        try:
            digest = hashlib.sha256()
            with source.open("rb") as input_file, destination.open("xb") as output_file:
                for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                    output_file.write(chunk)
                    digest.update(chunk)
            checksum = digest.hexdigest()
            with self.database.session_factory.begin() as s:
                for existing in s.scalars(select(Asset).where(Asset.sha256 == checksum)):
                    path = self.paths.assets_dir / existing.filename
                    if ASSET_NAME.fullmatch(existing.filename) and path.is_file():
                        with path.open("rb") as existing_file:
                            old_hash = hashlib.sha256()
                            for chunk in iter(lambda: existing_file.read(1024 * 1024), b""):
                                old_hash.update(chunk)
                            old_digest = old_hash.hexdigest()
                        if old_digest == checksum:
                            destination.unlink()
                            return existing.id, f"assets/{existing.filename}"
                asset = Asset(filename=name, sha256=checksum, mime=f"image/{fmt}")
                s.add(asset)
                s.flush()
                return asset.id, f"assets/{name}"
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def import_gallery_image(self, kind, source_id, source_path):
        asset_id, _ = self.import_image(source_path)
        try:
            self.add_gallery_image(kind, source_id, asset_id)
        except Exception:
            self.collect_unused_assets()
            raise
        return asset_id


    def add_gallery_image(self, kind, source_id, asset_id):
        if kind not in GALLERY_KINDS:
            raise ValueError("该条目不支持图库。")
        with self.database.session_factory.begin() as s:
            model = Inspiration if kind == "inspiration" else SOURCE_MODELS[kind]
            if not s.get(model, source_id) or not s.get(Asset, asset_id):
                raise LookupError("条目或图片不存在。")
            exists = s.scalar(select(GalleryImage.id).where(GalleryImage.source_kind == kind,
                GalleryImage.source_id == source_id, GalleryImage.asset_id == asset_id))
            if exists:
                return
            order = s.scalar(select(func.max(GalleryImage.sort_order)).where(
                GalleryImage.source_kind == kind, GalleryImage.source_id == source_id)) or 0
            s.add(GalleryImage(source_kind=kind, source_id=source_id, asset_id=asset_id, sort_order=order+10))


    def gallery(self, kind, source_id):
        with self.database.session_factory() as s:
            rows = s.execute(select(GalleryImage, Asset.filename).join(Asset, GalleryImage.asset_id == Asset.id)
                .where(GalleryImage.source_kind == kind, GalleryImage.source_id == source_id)
                .order_by(GalleryImage.sort_order, GalleryImage.id)).all()
            return [(link, self.paths.assets_dir / filename) for link, filename in rows]


    def remove_gallery_image(self, link_id):
        with self.database.session_factory.begin() as s:
            link = s.get(GalleryImage, link_id)
            if link:
                s.delete(link)
        return self.collect_unused_assets()


    def asset_path(self, asset_id):
        with self.database.session_factory() as s:
            asset = s.get(Asset, asset_id)
            return self.paths.assets_dir / asset.filename if asset else None
