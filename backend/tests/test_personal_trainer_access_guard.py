from types import SimpleNamespace
from pathlib import Path
import importlib.util
import sys
import types

import pytest
from fastapi import HTTPException

class _DummyCeleryTask:
    def delay(self, *args, **kwargs):
        return None


_fake_ai_tasks = types.ModuleType("app.tasks.ai_tasks")
_fake_ai_tasks.pre_generate_next_day_content = _DummyCeleryTask()
sys.modules.setdefault("app.tasks.ai_tasks", _fake_ai_tasks)

_fake_weekly_tasks = types.ModuleType("app.tasks.weekly_plan_tasks")
_fake_weekly_tasks.generate_week_plan_structure = lambda *args, **kwargs: None
_fake_weekly_tasks.check_and_trigger_next_week = lambda *args, **kwargs: None
_fake_weekly_tasks.retry_failed_generation = _DummyCeleryTask()
sys.modules.setdefault("app.tasks.weekly_plan_tasks", _fake_weekly_tasks)

_TRAINER_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints" / "personal_trainer.py"
_TRAINER_SPEC = importlib.util.spec_from_file_location("personal_trainer_endpoint_for_tests", _TRAINER_MODULE_PATH)
if _TRAINER_SPEC is None or _TRAINER_SPEC.loader is None:
    raise RuntimeError("Failed to load personal_trainer endpoint module for tests")
personal_trainer = importlib.util.module_from_spec(_TRAINER_SPEC)
_TRAINER_SPEC.loader.exec_module(personal_trainer)


def test_to_module_name_maps_expected_aliases():
    assert personal_trainer._to_module_name("conversation") == "speaking"
    assert personal_trainer._to_module_name("pronunciation") == "speaking"
    assert personal_trainer._to_module_name("comprehension") == "reading"
    assert personal_trainer._to_module_name("grammar") == "grammar"


def test_enforce_trainer_access_raises_403_when_denied(monkeypatch):
    def fake_can_start_new_lesson(*args, **kwargs):
        return False, "blocked by policy"

    monkeypatch.setattr(
        personal_trainer.content_access_service,
        "can_start_new_lesson",
        fake_can_start_new_lesson,
    )

    user = SimpleNamespace(current_level=SimpleNamespace(value="A1"))
    with pytest.raises(HTTPException) as exc_info:
        personal_trainer._enforce_trainer_access(object(), user, module="grammar")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "blocked by policy"


def test_enforce_trainer_access_uses_alias_and_default_level(monkeypatch):
    captured = {}

    def fake_can_start_new_lesson(_db, _user, module=None, cefr_level=None):
        captured["module"] = module
        captured["cefr_level"] = cefr_level
        return True, "ok"

    monkeypatch.setattr(
        personal_trainer.content_access_service,
        "can_start_new_lesson",
        fake_can_start_new_lesson,
    )

    user = SimpleNamespace(current_level=SimpleNamespace(value="A2"))
    personal_trainer._enforce_trainer_access(object(), user, module="conversation")

    assert captured["module"] == "speaking"
    assert captured["cefr_level"] == "A2"
