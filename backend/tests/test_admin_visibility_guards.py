from types import SimpleNamespace
from pathlib import Path
import importlib.util

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.models.user import User


_ADMIN_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints" / "admin.py"
_ADMIN_SPEC = importlib.util.spec_from_file_location("admin_endpoint_for_tests", _ADMIN_MODULE_PATH)
if _ADMIN_SPEC is None or _ADMIN_SPEC.loader is None:
    raise RuntimeError("Failed to load admin endpoint module for tests")
admin_endpoint_module = importlib.util.module_from_spec(_ADMIN_SPEC)
_ADMIN_SPEC.loader.exec_module(admin_endpoint_module)

_apply_user_visibility_filter = admin_endpoint_module._apply_user_visibility_filter
_ensure_admin_can_access_user = admin_endpoint_module._ensure_admin_can_access_user


def _admin(role: str):
    return SimpleNamespace(admin_role=role)


def _target(role: str | None):
    return SimpleNamespace(admin_role=role)


def test_owner_cannot_access_developer_user():
    with pytest.raises(HTTPException) as exc_info:
        _ensure_admin_can_access_user(_admin("owner"), _target("developer"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


def test_owner_can_access_non_developer_user():
    _ensure_admin_can_access_user(_admin("owner"), _target("owner"))
    _ensure_admin_can_access_user(_admin("owner"), _target(None))


def test_developer_can_access_developer_user():
    _ensure_admin_can_access_user(_admin("developer"), _target("developer"))


def test_visibility_filter_applies_for_owner_only():
    base_query = select(User.id)

    owner_query = _apply_user_visibility_filter(base_query, _admin("owner"))
    owner_sql = str(owner_query)
    assert "users.admin_role" in owner_sql

    developer_query = _apply_user_visibility_filter(base_query, _admin("developer"))
    assert str(developer_query) == str(base_query)
