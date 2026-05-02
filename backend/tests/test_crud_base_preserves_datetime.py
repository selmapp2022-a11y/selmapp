import asyncio
from datetime import datetime

from pydantic import BaseModel

from app.crud.base import CRUDBase


class _DummyCreate(BaseModel):
    user_id: int
    date: datetime


class _DummyModel:
    """Minimal model capturing ctor kwargs; does not require a real DB."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _DummySession:
    """Minimal async session stub used by CRUDBase.create()."""

    def __init__(self):
        self.added = None

    def add(self, obj):
        self.added = obj

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


def test_crud_create_preserves_datetime_objects():
    async def _run():
        crud = CRUDBase(_DummyModel)
        dt = datetime(2025, 12, 25, 0, 0, 0)
        obj_in = _DummyCreate(user_id=1, date=dt)

        db = _DummySession()
        created = await crud.create(db, obj_in=obj_in)

        assert isinstance(created.kwargs["date"], datetime)
        assert created.kwargs["date"] == dt

    asyncio.run(_run())





