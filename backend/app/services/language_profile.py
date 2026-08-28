"""
The language a generated exercise is in — as configuration, not as code.

This file exists because of a defect class the project has now paid for
five times. THE PLAN §5.2 lists four:

    dialect pinned · language_code discarded · task_type hard-coded ·
    the voice list filtered to startsWith('en')

and *"each was a value that should have come from configuration and was
written into code instead. Each was found late."* The fifth was found on
2026-08-28: the exam engine's word counter treated French elision as
English, under-counting by 5% and wrongly zeroing a third of
correct-length answers.

Amendment 2 §2.3 restores the four generation-side blockers to the plan and
says what the fix is: *"All four come from the exam definition, exactly as
dialect, task_type and now segmentationFor() do."*

So: a profile is DATA. Adding Spanish means adding a dict below and no
branch anywhere. Nothing in this file asks which language it is looking at
except the lookup itself, and an unknown code falls back to English loudly
rather than silently producing an English exercise labelled French.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class LanguageProfile:
    """Everything a prompt needs to know about the target language."""

    code: str
    """BCP-47 primary subtag: 'en', 'fr'."""

    english_name: str
    """How the language is named INSIDE a prompt, which is written in English."""

    tutor: str
    """The role a generation prompt assumes. Was hard-coded as
    'an English-language tutor' in ai_reading_service.py."""

    writer: str
    """The role a passage-writing prompt assumes."""

    write_in: str
    """The instruction that forces the OUTPUT language. This is the line
    that actually matters: a prompt written in English will produce English
    unless it is told otherwise, which is exactly why 'You are an
    English-language tutor' was never noticed as a blocker — it read like a
    description of the tutor rather than a choice of output language."""

    speech_locale: str
    """BCP-47 tag for speech recognition and word segmentation."""

    tts_voices: Dict[str, str]
    """ElevenLabs voice ids by role. Was hard-coded to two American voices."""

    voice_note: str
    """What we may and may not claim about these voices. STEP-10-B2 measured
    the pronunciation scorer treating fr-ca and fr-fr identically, so no
    Quebec-specific claim is made anywhere."""


ENGLISH = LanguageProfile(
    code="en",
    english_name="English",
    tutor="an English-language tutor",
    writer="an expert English-language writer",
    write_in="Write everything in English.",
    speech_locale="en-US",
    # Rachel and Adam. American, and said so rather than left implicit.
    tts_voices={"female": "21m00Tcm4TlvDq8ikWAM", "male": "pNInz6obpgDQGcFmaJgB"},
    voice_note="American English voices.",
)

FRENCH = LanguageProfile(
    code="fr",
    english_name="French",
    tutor="a French-language tutor",
    writer="an expert French-language writer",
    # Explicit, and it names the register too: TCF Canada candidates are
    # examined in standard international French, not in a regional variety.
    write_in=(
        "Write everything in French. Use neutral international French — "
        "standard spelling, standard grammar, no regional idiom. Canadian "
        "vocabulary where it is the standard term (courriel, not e-mail)."
    ),
    speech_locale="fr-CA",
    # Multilingual voices. ElevenLabs' turbo/multilingual models render
    # French from these ids; they are not French-native speakers and the
    # note below is what stops that being claimed.
    tts_voices={"female": "EXAVITQu4vr4xnSDxMaL", "male": "onwK4e9ZLuTAKqWW03F9"},
    voice_note=(
        "Multilingual voices rendering French. No claim is made that these "
        "are Quebec French: STEP-10-B2 measured the pronunciation scorer "
        "treating fr-ca and fr-fr identically, so a regional claim would be "
        "one the product cannot support."
    ),
)

PROFILES: Dict[str, LanguageProfile] = {"en": ENGLISH, "fr": FRENCH}

SUPPORTED = tuple(PROFILES)


def profile_for(code: Optional[str]) -> LanguageProfile:
    """Look up a profile. Falls back to English for an unknown code.

    The fallback is deliberate and it is deliberately not silent at the call
    site: a caller that cares should check ``is_supported`` first. What must
    never happen is an unknown code producing a French-labelled exercise
    written in English, which is the failure the hard-coded prompts caused.
    """
    if not code:
        return ENGLISH
    return PROFILES.get(code.split("-")[0].lower(), ENGLISH)


def is_supported(code: Optional[str]) -> bool:
    return bool(code) and code.split("-")[0].lower() in PROFILES
