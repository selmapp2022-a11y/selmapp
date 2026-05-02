from dataclasses import dataclass

from app.services.content_access_service import ContentAccessService


@dataclass
class _DummyUser:
    id: int = 1
    is_admin: bool = False
    is_premium: bool = False


def _build_service_for_free_user(*, free_levels=None, free_modules=None, free_quota=7, completed_lessons=0):
    service = ContentAccessService()
    service.is_content_lock_enabled = lambda db: True
    service.user_has_premium_access = lambda db, user: False
    service.get_free_cefr_levels = lambda db: free_levels if free_levels is not None else ["A1"]
    service.get_free_modules = lambda db: free_modules if free_modules is not None else ["reading"]
    service.get_free_lessons_quota = lambda db: free_quota
    service.get_completed_lessons_count = lambda db, user: completed_lessons
    return service


def test_can_start_new_lesson_allows_when_within_free_limits():
    service = _build_service_for_free_user(
        free_levels=["A1", "A2"],
        free_modules=["reading", "vocabulary"],
        free_quota=7,
        completed_lessons=3,
    )

    allowed, reason = service.can_start_new_lesson(
        db=None,
        user=_DummyUser(),
        module="reading",
        cefr_level="A2",
    )

    assert allowed is True
    assert reason == "Free access allowed"


def test_can_start_new_lesson_denies_when_level_not_free():
    service = _build_service_for_free_user(
        free_levels=["A1"],
        free_modules=["reading"],
        free_quota=7,
        completed_lessons=0,
    )

    allowed, reason = service.can_start_new_lesson(
        db=None,
        user=_DummyUser(),
        module="reading",
        cefr_level="B1",
    )

    assert allowed is False
    assert "CEFR level B1 requires premium subscription" in reason


def test_can_start_new_lesson_denies_when_module_not_free():
    service = _build_service_for_free_user(
        free_levels=["A1", "A2"],
        free_modules=["reading"],
        free_quota=7,
        completed_lessons=0,
    )

    allowed, reason = service.can_start_new_lesson(
        db=None,
        user=_DummyUser(),
        module="grammar",
        cefr_level="A1",
    )

    assert allowed is False
    assert "Module grammar requires premium subscription" in reason


def test_can_start_new_lesson_denies_when_quota_reached():
    service = _build_service_for_free_user(
        free_levels=["A1"],
        free_modules=["reading"],
        free_quota=7,
        completed_lessons=7,
    )

    allowed, reason = service.can_start_new_lesson(
        db=None,
        user=_DummyUser(),
        module="reading",
        cefr_level="A1",
    )

    assert allowed is False
    assert "Free lesson quota reached (7/7)" in reason


def test_can_start_new_lesson_denies_when_quota_is_zero():
    service = _build_service_for_free_user(
        free_levels=["A1"],
        free_modules=["reading"],
        free_quota=0,
        completed_lessons=0,
    )

    allowed, reason = service.can_start_new_lesson(
        db=None,
        user=_DummyUser(),
        module="reading",
        cefr_level="A1",
    )

    assert allowed is False
    assert "Free lesson quota reached (0/0)" in reason
