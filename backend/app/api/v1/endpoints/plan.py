"""
The study-package explainer — SELM-PLANNER-SPEC.md.

The division that governs everything: **deterministic code decides WHAT the
plan is; the model writes WHY, in the candidate's language, grounded only in
facts passed to it.** The plan (slots, order, gaps, governing level) is
computed on the client by `buildPlan` and arrives here already decided. This
endpoint's only job is to attach prose, and to refuse prose that rewrites the
plan or invents a number.

Same shape as the scoring engine: the gate is code and runs first; the model
is a judge that never overrides it.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api import deps
from app.models.user import User

router = APIRouter()

# §4.1 — the system prompt, verbatim. Shipped as written.
SYSTEM_PROMPT = """You write study plans for candidates preparing for a language examination
required for immigration or study.

You are given a plan that has already been decided. Your only task is to
explain it.

RULES — these are absolute:

1. Do not change the plan. Do not reorder, add, remove or merge anything.
2. Do not state any number that is not given to you. Do not compute,
   estimate, round or infer a score, level or date.
3. If a skill has no score, say it is not known. Never guess it.
4. You are told which skills fell short. You are NOT told which criterion
   within a skill failed, because the examination never releases that.
   Never name a criterion as the cause.
5. Never write "guaranteed", "you will pass", "you are ready", or any
   promise about the real examination result.
6. Where the plan has a gap, say plainly that this part is not built yet.
   Do not substitute a generic lesson.
7. Write in the language you are given. All of it, including headings.
8. Address the candidate directly, plainly, and without encouragement
   that the facts do not support.

Return only the JSON described in the schema."""

# §4.3 — the response schema. Structured output; the model returns this shape.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "opening": {"type": "string"},
        "why_this_order": {"type": "string"},
        "slot_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"order": {"type": "integer"}, "note": {"type": "string"}},
                "required": ["order", "note"],
            },
        },
        "gaps_note": {"type": "string"},
        "time_note": {"type": "string"},
    },
    "required": ["opening", "why_this_order", "slot_notes"],
}

FORBIDDEN = ["guaranteed", "will pass", "you are ready", "100%", "garanti", "vous réussirez", "vous êtes prêt"]


# ── §4.2 input ────────────────────────────────────────────────────────────
class Gap(BaseModel):
    skill: str
    short_by: Optional[int] = None
    unit: Optional[str] = None


class Score(BaseModel):
    skill: str
    mark: Optional[float] = None
    scale: Optional[str] = None


class Attestation(BaseModel):
    present: bool = False
    kind: Optional[str] = None
    sat_on: Optional[str] = None
    scores: List[Score] = []
    governing_level: Optional[int] = None
    gaps: List[Gap] = []


class Target(BaseModel):
    scale: str
    value: int
    rule: str = "every skill"


class Slot(BaseModel):
    order: int
    skill: str
    tache: str
    level: Optional[str] = None
    prescription: Optional[str] = None


class BankGap(BaseModel):
    skill: str
    tache: str
    reason: str = "no content yet"


class PlanPayload(BaseModel):
    language: str            # "fr-CA" | "en"
    exam: str
    target: Target
    attestation: Attestation = Field(default_factory=Attestation)
    days_remaining: Optional[int] = None
    fits_in_time: bool = True
    slots: List[Slot]
    gaps_in_bank: List[BankGap] = []
    # The four official criteria for this exam, so the validator can refuse a
    # causal criterion claim. Passed in because it is exam-specific data, not
    # a judgement.
    criteria: List[str] = []


# ── the deterministic template fallback (§5) — a real deliverable ─────────
def _template(p: PlanPayload) -> Dict[str, Any]:
    fr = p.language.lower().startswith("fr")
    sys = p.target.scale

    if p.attestation.present and p.attestation.governing_level is not None:
        gl = p.attestation.governing_level
        opening = (
            f"Votre plan est construit à partir de vos notes réelles. "
            f"Le niveau qui compte est le plus bas de vos compétences : {sys} {gl}. "
            f"Votre cible est {sys} {p.target.value}."
            if fr else
            f"Your plan is built from your real marks. The level that governs it is your "
            f"lowest skill: {sys} {gl}. Your target is {sys} {p.target.value}."
        )
        why = (
            "La compétence la plus faible passe en premier, car c'est elle qui décide : "
            "travailler les compétences déjà à la cible ne change pas votre résultat."
            if fr else
            "The weakest skill comes first because it governs the outcome: working on skills "
            "already at target does not change your result."
        )
    else:
        opening = (
            "Votre plan est construit dans l'ordre de l'examen. Saisissez un résultat passé "
            "à tout moment et il se réorganisera autour de vos vraies notes."
            if fr else
            "Your plan is built in exam order. Enter a past result any time and it will "
            "reorder around your real marks."
        )
        why = (
            "Sans notes, aucun niveau n'est supposé ; la difficulté s'ajuste à vos réponses."
            if fr else
            "With no marks, no level is assumed; difficulty adapts to your answers."
        )

    slot_notes = [
        {"order": s.order,
         "note": (f"{s.tache} — {s.level}" if s.level else s.tache) +
                 (("" if not s.prescription else (f" · {s.prescription}")))}
        for s in p.slots
    ]

    gaps_note = None
    if p.gaps_in_bank:
        n = len(p.gaps_in_bank)
        gaps_note = (
            f"{n} coordonnée(s) de votre plan n'ont pas encore de contenu rédigé. "
            f"Elles sont affichées telles quelles, non comblées par une leçon générique."
            if fr else
            f"{n} coordinate(s) in your plan have no content authored yet. They are shown "
            f"as they are, not filled with a generic lesson."
        )

    time_note = None
    if p.days_remaining is not None:
        if not p.fits_in_time:
            time_note = (
                f"Il reste {p.days_remaining} jours, ce qui est court pour ce plan : "
                f"priorisez les premières séances."
                if fr else
                f"{p.days_remaining} days remain, which is tight for this plan: "
                f"prioritise the first sessions."
            )
        else:
            time_note = (
                f"Il reste {p.days_remaining} jours." if fr else f"{p.days_remaining} days remain."
            )

    return {
        "opening": opening,
        "why_this_order": why,
        "slot_notes": slot_notes,
        "gaps_note": gaps_note,
        "time_note": time_note,
        "_source": "template",
    }


# ── §5 validation ─────────────────────────────────────────────────────────
def _allowed_numbers(p: PlanPayload) -> set[str]:
    nums: set[str] = set()
    def add(x):
        if x is None:
            return
        nums.add(str(x))
        try:
            f = float(x)
            if f == int(f):
                nums.add(str(int(f)))
        except (ValueError, TypeError):
            pass
    add(p.target.value)
    add(p.days_remaining)
    if p.attestation.present:
        add(p.attestation.governing_level)
        for s in p.attestation.scores:
            add(s.mark)
        for g in p.attestation.gaps:
            add(g.short_by)
        # The sitting date is SUPPLIED to the model (§4.2 sat_on), so a plan
        # that says "your June 2025 sitting" is stating a number it was given,
        # not inventing one. Its digit groups are allowed, with and without a
        # leading zero (a form the model may or may not keep).
        if p.attestation.sat_on:
            for tok in re.findall(r"\d+", p.attestation.sat_on):
                nums.add(tok)
                try:
                    nums.add(str(int(tok)))
                except ValueError:
                    pass
    for s in p.slots:
        add(s.order)
        # a level like "B2" is not a bare number; a numeric level is allowed
        if s.level and re.fullmatch(r"\d+", str(s.level)):
            add(s.level)
    return nums


def _validate(out: Dict[str, Any], p: PlanPayload) -> List[str]:
    fails: List[str] = []
    blob = " ".join([
        str(out.get("opening", "")), str(out.get("why_this_order", "")),
        " ".join(n.get("note", "") for n in out.get("slot_notes", []) or []),
        str(out.get("gaps_note") or ""), str(out.get("time_note") or ""),
    ])

    # Numbers: any integer/decimal token the MODEL wrote must have been
    # supplied. First strip the verbatim passthrough strings — prescription
    # ids like "tcf-ee-t1-nclc6", tache names, the exam name — so a digit
    # buried in a code we handed in is not mistaken for a claimed number.
    passthru = [p.exam] + [s.tache for s in p.slots] + \
        [s.prescription for s in p.slots if s.prescription] + \
        [s.level for s in p.slots if s.level] + \
        [g.skill for g in p.attestation.gaps] + [sc.skill for sc in p.attestation.scores] + \
        [g.tache for g in p.gaps_in_bank] + [g.skill for g in p.gaps_in_bank]
    scan = blob
    for tok in sorted(set(x for x in passthru if x), key=len, reverse=True):
        scan = scan.replace(tok, " ")
    allowed = _allowed_numbers(p)
    for tok in re.findall(r"\d+(?:[.,]\d+)?", scan):
        norm = tok.replace(",", ".")
        if norm not in allowed and tok not in allowed:
            # allow a trailing-zero / integer form
            try:
                f = float(norm)
                if str(int(f)) in allowed or str(f) in allowed:
                    continue
            except ValueError:
                pass
            fails.append(f"number not supplied: {tok}")

    # Language: crude but effective — French output must not be dominated by
    # English function words and vice-versa.
    fr = p.language.lower().startswith("fr")
    low = blob.lower()
    if fr and re.search(r"\b(the|your|you|and|with|level|score)\b", low):
        fails.append("english words in a french plan")
    if not fr and re.search(r"\b(vous|votre|niveau|le plan|compétence)\b", low):
        fails.append("french words in an english plan")

    # Criterion claim: none of the exam's four official criteria may be named.
    for c in p.criteria:
        if c and c.lower() in low:
            fails.append(f"criterion named: {c}")

    # Forbidden promises.
    for w in FORBIDDEN:
        if w.lower() in low:
            fails.append(f"forbidden phrase: {w}")

    # Plan integrity: slot_notes must match the slots exactly, count and order.
    notes = out.get("slot_notes") or []
    if len(notes) != len(p.slots):
        fails.append(f"slot_notes count {len(notes)} != slots {len(p.slots)}")
    else:
        for i, (n, s) in enumerate(zip(notes, p.slots)):
            if int(n.get("order", -1)) != s.order:
                fails.append(f"slot_notes order mismatch at position {i}")
                break

    # Gaps: every bank gap must be acknowledged.
    if p.gaps_in_bank and not (out.get("gaps_note") or "").strip():
        fails.append("gaps present but gaps_note empty")

    return fails


def _call_model(p: PlanPayload) -> Dict[str, Any]:
    """gemini-2.5-pro, temperature 0, fixed seed, structured JSON. If any of
    the three is unavailable the caller falls back to the template and the
    response records it."""
    # google-genai (the current SDK), NOT the legacy google-generativeai 0.8.x,
    # which raises "Unknown field for GenerationConfig: seed" and so cannot meet
    # SELM-PLANNER-SPEC §1's requirement of temperature 0 AND a fixed seed AND
    # structured JSON together. Verified in the api container: the legacy SDK
    # rejects seed; this one accepts it.
    from google import genai
    from google.genai import types
    from app.core.config import settings

    client = genai.Client(api_key=settings.GOOGLE_GEMINI_API_KEY)
    payload = p.model_dump()
    payload.pop("criteria", None)  # the criteria list is for validation, not the model
    # Rule 2 forbids the model stating a date, and the sitting date is the one
    # it most often reached for and then failed validation on. It is not needed
    # to explain the ordering or the gaps, so it is withheld from the model.
    if isinstance(payload.get("attestation"), dict):
        payload["attestation"].pop("sat_on", None)
    resp = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0,
            seed=7,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )
    return json.loads(resp.text)


@router.post("/explain")
async def explain_plan(
    payload: PlanPayload,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Attach prose to an already-decided plan. Model writes why; code owns
    what. Validation → one regenerate → template fallback."""
    t0 = time.time()
    source = "model"
    out: Optional[Dict[str, Any]] = None
    fired: List[str] = []
    try:
        out = _call_model(payload)
        fails = _validate(out, payload)
        if fails:
            fired = fails
            out = _call_model(payload)  # §5: regenerate once
            fails2 = _validate(out, payload)
            if fails2:
                fired = fails2
                out = _template(payload)
                source = "template_after_validation"
    except Exception as e:  # model unavailable / bad settings / parse
        out = _template(payload)
        source = f"template_fallback:{type(e).__name__}"

    if "_source" in out:
        source = out.pop("_source")
    out["_meta"] = {"source": source, "latency_ms": int((time.time() - t0) * 1000), "checks_fired": fired}
    return out
