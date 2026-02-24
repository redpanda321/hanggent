"""Admin Settings model.

A generic key-value store for system-wide admin configuration.
For example the "additional_fee_percent" that is applied on top of base
model token costs for all Hanggent cloud models.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, String, Text
from sqlmodel import Field, Session, select

from app.model.abstract.model import AbstractModel, DefaultTimes


class AdminSettings(AbstractModel, DefaultTimes, table=True):
    """System-wide admin settings (key-value store)."""

    __tablename__ = "admin_settings"

    id: int = Field(default=None, primary_key=True)
    key: str = Field(sa_column=Column(String(100), nullable=False, unique=True, index=True))
    value: str = Field(default="", sa_column=Column(Text, nullable=False))
    description: str = Field(default="", sa_column=Column(Text))

    # --------------- helpers ---------------

    @classmethod
    def get_value(cls, session: Session, key: str, default: str = "") -> str:
        """Return the value for *key*, or *default* if it doesn't exist."""
        row = session.exec(
            select(cls).where(cls.key == key)
        ).first()
        return row.value if row else default

    @classmethod
    def set_value(cls, session: Session, key: str, value: str, description: str = "") -> "AdminSettings":
        """Upsert a setting."""
        row = session.exec(select(cls).where(cls.key == key)).first()
        if row:
            row.value = value
            if description:
                row.description = description
        else:
            row = cls(key=key, value=value, description=description)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    @classmethod
    def get_additional_fee_percent(cls, session: Session) -> float:
        """Return the global additional fee percentage (default 5.0)."""
        raw = cls.get_value(session, "additional_fee_percent", "5")
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 5.0


# ---- Pydantic schemas ----

class AdminSettingCreate(BaseModel):
    key: str
    value: str
    description: str = ""


class AdminSettingUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None


class AdminSettingOut(BaseModel):
    id: int
    key: str
    value: str
    description: str
    created_at: datetime
    updated_at: datetime
