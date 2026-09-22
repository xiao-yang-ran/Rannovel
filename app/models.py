"""RanNovel's versioned, offline library schema."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (CheckConstraint("kind IN ('novel','essay','fragment')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Volume(Base):
    __tablename__ = "volumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chapters: Mapped[list["Chapter"]] = relationship(order_by="Chapter.sort_order")


class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[int] = mapped_column(primary_key=True)
    volume_id: Mapped[int] = mapped_column(ForeignKey("volumes.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    core_events: Mapped[str] = mapped_column(Text, default="", nullable=False)
    estimated_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Faction(Base):
    __tablename__ = "factions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(80), default="阵营", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Character(Base):
    __tablename__ = "characters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    personality: Mapped[str] = mapped_column(Text, default="", nullable=False)
    motivation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    skills: Mapped[str] = mapped_column(Text, default="", nullable=False)
    background: Mapped[str] = mapped_column(Text, default="", nullable=False)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    faction_id: Mapped[int | None] = mapped_column(ForeignKey("factions.id", ondelete="RESTRICT"), nullable=True)


class CharacterRelation(Base):
    __tablename__ = "character_relations"
    __table_args__ = (UniqueConstraint("source_id", "target_id", "relation_type"), CheckConstraint("source_id <> target_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False)
    target_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="地点", nullable=False, index=True)
    layout: Mapped[str] = mapped_column(Text, default="", nullable=False)
    environment_rules: Mapped[str] = mapped_column(Text, default="", nullable=False)
    physical_laws: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="世界总纲", nullable=False, index=True)
    overview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    structure: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rules: Mapped[str] = mapped_column(Text, default="", nullable=False)
    advancement: Mapped[str] = mapped_column(Text, default="", nullable=False)
    limitations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    relationships: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (CheckConstraint("month BETWEEN 1 AND 12"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)


class EventCharacter(Base):
    __tablename__ = "event_characters"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="RESTRICT"), primary_key=True)


class Inspiration(Base):
    __tablename__ = "inspirations"
    __table_args__ = (
        CheckConstraint("pool IN ('essay','novel')"),
        Index("ix_inspiration_pool_order", "pool", "sort_order"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pool: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_work_id: Mapped[int | None] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), nullable=True, index=True)
    target_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner: Mapped[Work | None] = relationship()


class Reference(Base):
    __tablename__ = "references"
    __table_args__ = (UniqueConstraint("target_kind", "target_id", "source_kind", "source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime: Mapped[str] = mapped_column(String(30), nullable=False)


class GalleryImage(Base):
    __tablename__ = "gallery_images"
    __table_args__ = (UniqueConstraint("asset_id", "source_kind", "source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
