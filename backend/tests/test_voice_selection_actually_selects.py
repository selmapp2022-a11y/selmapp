"""A parameter that selects behaviour must be PROVEN to select it.

Ruled 29 August 2026, `SELM-RULINGS-voices.md` §4.1, after the seventh
occurrence of one defect:

    dialect: 'en-us' pinned · language_code discarded · task_type hard-coded ·
    the elision counter · target_language read by a service nobody had found ·
    generate_listening_content accepting `language` and never passing it to
    voice selection · generate_multi_speaker_audio running `del accent`.

    "Every one was a value that should have come from configuration and was
    written into code, or accepted at the door and dropped inside. The pattern
    is not carelessness — it is that A PARAMETER WHICH IS ACCEPTED AND IGNORED
    LOOKS IDENTICAL TO ONE THAT WORKS, from the outside and from the type
    signature."

    "So the standing check is: when a function takes a parameter that selects
    behaviour, there must be a test that proves a DIFFERENT value produces a
    DIFFERENT result. Not that it runs."

Every test below is that shape. None of them assert "returns something"; each
asserts that changing one argument changes the answer. `del accent` passes a
smoke test perfectly, and passes nothing here.

No network: the catalogue is stubbed, so this runs in CI and on a laptop with
no key. What is being tested is the selection logic, which is where the defect
lived — not the vendor.
"""
from __future__ import annotations

import asyncio

from app.services.elevenlabs_tts_service import ElevenLabsTTSService


def _voice(voice_id, name, language, accent, gender, verified=None):
    v = {
        "voice_id": voice_id,
        "name": name,
        "labels": {"language": language, "accent": accent, "gender": gender},
    }
    if verified:
        v["verified_languages"] = verified
    return v


# A catalogue with the shape the real account has: French voices in several
# varieties, English voices in several accents, and — the case that matters —
# one English voice the vendor has verified as Quebecois when speaking French.
CATALOGUE = [
    _voice("fr-qc-f", "Amelie", "fr", "quebec", "female"),
    _voice("fr-qc-m", "Alexandre", "fr", "quebec", "male"),
    _voice("fr-pa-f", "Julia", "fr", "parisian", "female"),
    _voice("fr-pa-m", "Antoine", "fr", "parisian", "male"),
    _voice("fr-af-m", "Keli", "fr", "african", "male"),
    _voice("fr-be-m", "Christophe", "fr", "belgian", "male"),
    _voice("en-ca-f", "Rebecca", "en", "canadian", "female"),
    _voice("en-ca-m", "Barclay", "en", "canadian", "male"),
    _voice("en-gb-f", "Alice", "en", "british", "female"),
    # The Silias case, observed live on 29 August 2026: a Canadian ENGLISH
    # narrator that the vendor verifies as fr-quebec when speaking French.
    _voice(
        "en-ca-m-fr", "Silias North", "en", "canadian", "male",
        verified=[{"language": "fr", "accent": "fr-quebec", "locale": "fr-FR"}],
    ),
]


def _service(catalogue=CATALOGUE):
    s = ElevenLabsTTSService()
    s.api_key = "test-key-not-used"
    s._voice_catalogue = list(catalogue)
    s._voice_catalogue_at = float("inf")  # never expire during a test
    return s


def _run(coro):
    return asyncio.run(coro)


# --- accent selects -------------------------------------------------------

def test_a_different_accent_gives_a_different_voice():
    s = _service()
    quebec = _run(s.pick_voice(language="fr", accent="quebec"))
    parisian = _run(s.pick_voice(language="fr", accent="parisian"))
    assert quebec != parisian
    assert quebec in {"fr-qc-f", "fr-qc-m"}
    assert parisian in {"fr-pa-f", "fr-pa-m"}


def test_every_french_variety_resolves_to_its_own_voice():
    """Not "each returns something" — each returns a DIFFERENT something."""
    s = _service()
    picked = {
        v: _run(s.pick_voice(language="fr", accent=v))
        for v in ("quebec", "parisian", "african", "belgian")
    }
    assert len(set(picked.values())) == len(picked), picked


# --- gender selects -------------------------------------------------------

def test_a_different_gender_gives_a_different_voice():
    s = _service()
    male = _run(s.pick_voice(language="fr", accent="quebec", gender="male"))
    female = _run(s.pick_voice(language="fr", accent="quebec", gender="female"))
    assert male == "fr-qc-m"
    assert female == "fr-qc-f"
    assert male != female


# --- language selects -----------------------------------------------------

def test_a_different_language_gives_a_different_set():
    s = _service()
    fr = {v["voice_id"] for v in _run(s.find_voices(language="fr"))}
    en = {v["voice_id"] for v in _run(s.find_voices(language="en"))}
    assert fr != en
    assert "en-gb-f" not in fr, "a British English voice must not answer a French request"
    assert "fr-pa-f" not in en


# --- the honest miss ------------------------------------------------------

def test_an_accent_the_account_does_not_hold_returns_none_not_a_substitute():
    """The failure this whole design exists to prevent.

    A wrong accent in a listening exam is not a cosmetic defect — it is a
    different test. So the selector says None and lets the caller decide,
    rather than handing back a voice that will render perfectly and wrongly.
    """
    s = _service()
    assert _run(s.pick_voice(language="fr", accent="swiss")) is None


# --- verified_languages is read, not just labels --------------------------

def test_a_cross_language_voice_is_found_by_its_verified_accent():
    """`labels` says this voice is English. The vendor says it speaks
    Quebecois French. Reading only `labels` would lose it."""
    s = _service()
    ids = [v["voice_id"] for v in _run(s.find_voices(language="fr", accent="quebec"))]
    assert "en-ca-m-fr" in ids


def test_native_language_voices_come_before_cross_language_ones():
    """Order is a decision, not catalogue position."""
    s = _service()
    ids = [v["voice_id"] for v in _run(s.find_voices(language="fr", accent="quebec"))]
    assert ids.index("fr-qc-f") < ids.index("en-ca-m-fr")
    assert ids.index("fr-qc-m") < ids.index("en-ca-m-fr")


# --- the speaker map: the parameter that used to be deleted ---------------

def test_accent_changes_the_multi_speaker_map():
    """`generate_multi_speaker_audio` ran `del accent`. This is the test that
    would have caught it: same speakers, different accent, different voices."""
    s = _service()
    speakers = [{"name": "A", "gender": "female"}, {"name": "B", "gender": "male"}]
    quebec = _run(s._build_speaker_voice_map_async(speakers, "", language="fr", accent="quebec"))
    parisian = _run(s._build_speaker_voice_map_async(speakers, "", language="fr", accent="parisian"))
    assert quebec != parisian
    assert quebec["A"] == "fr-qc-f" and quebec["B"] == "fr-qc-m"
    assert parisian["A"] == "fr-pa-f" and parisian["B"] == "fr-pa-m"


def test_language_changes_the_multi_speaker_map():
    """`generate_listening_content` accepted `language` and never passed it to
    voice selection, so a French script was read aloud by English voices."""
    s = _service()
    speakers = [{"name": "A", "gender": "female"}]
    fr = _run(s._build_speaker_voice_map_async(speakers, "", language="fr"))
    en = _run(s._build_speaker_voice_map_async(speakers, "", language="en"))
    assert fr["A"] != en["A"]


def test_one_gender_missing_does_not_discard_the_other():
    """An account with a Belgian male and no Belgian female must get the male
    right. Falling back for both would throw away the half that was available."""
    s = _service()
    speakers = [{"name": "A", "gender": "male"}, {"name": "B", "gender": "female"}]
    m = _run(s._build_speaker_voice_map_async(speakers, "", language="fr", accent="belgian"))
    assert m["A"] == "fr-be-m"
    assert m["B"] != "fr-be-m"


# --- resolution by name ---------------------------------------------------

def test_a_different_name_gives_a_different_voice():
    s = _service()
    assert _run(s.voice_id_for_name("Amelie")) == "fr-qc-f"
    assert _run(s.voice_id_for_name("Julia")) == "fr-pa-f"
    assert _run(s.voice_id_for_name("Nobody At All")) is None


def test_a_name_prefix_resolves_because_display_names_carry_descriptions():
    """Library names are "Alexandre - Authentic French Canadian". An exact
    match would fail for every voice a person would actually name."""
    s = _service()
    catalogue = [_voice("x", "Alexandre - Authentic French Canadian", "fr", "quebec", "male")]
    s = _service(catalogue)
    assert _run(s.voice_id_for_name("Alexandre")) == "x"


# --- the resolver's order of specificity ----------------------------------

def test_resolution_prefers_explicit_id_then_name_then_traits():
    s = _service()
    by_id = _run(s._resolve_voice_id_async([{"voice_id": "explicit-wins"}]))
    by_name = _run(s._resolve_voice_id_async([{"voice_name": "Julia"}]))
    by_trait = _run(s._resolve_voice_id_async([{"language": "fr", "accent": "african"}]))
    assert by_id == "explicit-wins"
    assert by_name == "fr-pa-f"
    assert by_trait == "fr-af-m"
    assert len({by_id, by_name, by_trait}) == 3


def test_an_unreadable_catalogue_falls_back_and_does_not_raise():
    """Failure is downward. A catalogue that raised into a render would turn a
    cosmetic problem into a missing recording."""
    s = _service(catalogue=[])
    s._voice_catalogue = []
    got = _run(s._resolve_voice_id_async([{"language": "fr", "accent": "quebec"}]))
    assert isinstance(got, str) and got, "must still return a usable voice_id"
