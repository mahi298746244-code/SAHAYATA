"""Catalog models: departments and complaint categories (admin-manageable)."""
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    contact_email: Mapped[str | None] = mapped_column(String(255))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Category(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="circle")
    color: Mapped[str] = mapped_column(String(9), default="#2563eb")
    keywords: Mapped[list | None] = mapped_column(JSON)  # used by rules + admin review
    parent_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("categories.id"))
    department_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("departments.id"))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    parent = relationship("Category", remote_side="Category.id", lazy="joined")
    department = relationship("Department", lazy="joined")
