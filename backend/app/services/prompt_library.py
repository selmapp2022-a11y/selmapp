"""
Shared prompt-building helpers used by ai_service / ai_reading_service / etc.

Why this file exists
====================

Before 2026-05-13 every content-generation prompt just passed the CEFR label
("for B1 learners") and hoped Gemini would pick the right vocabulary and
grammar. Output was inconsistent, often too easy or too academic, and read
like translated textbook material instead of real English. Users called the
content "shallow" on iPhone testing.

This module fixes that in three ways:

1. ``CEFR_MATRIX`` — an explicit spec for each CEFR level: vocabulary size,
   permitted grammar structures, sentence length, discourse markers,
   register. Prompts paste this block in so the model has hard rules, not
   a vague label.

2. ``HUMAN_VOICE_RULES`` — style guardrails that push every prompt away from
   the "textbook robot" voice and toward something a real human would say.
   Examples: contractions, natural hesitation markers in dialogue,
   concrete specific detail over generic phrasing, varied sentence rhythm.

3. ``build_learner_context`` — assembles a short, neutral learner profile
   block (level, goals, weak areas, interests) without any nationality or
   native-language assumption. SELM ships globally — Persian-specific
   defaults were removed the same day.

Keep this module **prompt-only**. No I/O, no SDK calls, no async — just
string builders.  Anything more belongs in the calling service.
"""
from __future__ import annotations

import random
from typing import Any, Dict, Iterable, List, Optional


# ── CEFR level matrix ────────────────────────────────────────────────
#
# These ranges follow the Council of Europe's CEFR descriptors and the
# Cambridge/Pearson vocabulary-band research. They are intentionally
# concrete so Gemini can comply, not "use vocabulary appropriate for B1".

CEFR_MATRIX: Dict[str, Dict[str, str]] = {
    "A1": {
        "vocabulary": (
            "Top ~800 most frequent English words only. Avoid idioms and "
            "phrasal verbs except 'go to', 'come from', 'get up'."
        ),
        "grammar": (
            "Present simple, present continuous for now, past simple with "
            "the most common irregular verbs (was/were, went, had, did, "
            "saw). 'can' for ability. Subject-verb-object only."
        ),
        "sentences": (
            "Max 12 words per sentence. One idea per sentence. No "
            "subordinate clauses; join with 'and', 'but', 'because' only."
        ),
        "register": (
            "Concrete everyday topics (family, food, weather, daily "
            "routine). Friendly, neutral. No metaphor, no irony."
        ),
        "discourse": "Plain ordering. No discourse markers beyond 'first', 'then', 'so'.",
    },
    "A2": {
        "vocabulary": (
            "Top ~1500 words. A small number of common phrasal verbs "
            "('look for', 'turn on', 'pick up'). Familiar collocations."
        ),
        "grammar": (
            "All simple tenses (present, past, future with 'will' and "
            "'going to'). Present perfect for life experiences. "
            "Comparatives and superlatives. 'have to', 'should'."
        ),
        "sentences": (
            "Max 18 words. Up to two clauses joined by 'and', 'but', "
            "'because', 'so', 'when', 'if'."
        ),
        "register": (
            "Daily routines, shopping, travel, hobbies, simple opinions. "
            "Polite but informal."
        ),
        "discourse": "'first', 'next', 'after that', 'finally', 'also', 'however' (sparingly).",
    },
    "B1": {
        "vocabulary": (
            "Top ~2500 words. Common collocations and high-frequency "
            "idioms ('break the ice', 'on the other hand'). Some "
            "topic-specific vocabulary when introduced in context."
        ),
        "grammar": (
            "All tenses including continuous and perfect. First and "
            "second conditional. Modal verbs (might, could, should, "
            "must). Reported speech for statements. Defining relative "
            "clauses (who, which, that)."
        ),
        "sentences": (
            "Max 24 words. Two or three clauses with clear linking. "
            "Mix simple and complex sentence types for rhythm."
        ),
        "register": (
            "Work, education, current events, opinions and arguments. "
            "Can be light, serious, or reflective."
        ),
        "discourse": (
            "'however', 'although', 'in addition', 'on the other hand', "
            "'as a result', 'for example'."
        ),
    },
    "B2": {
        "vocabulary": (
            "Top ~4000 words. Phrasal verbs and idioms used naturally. "
            "Hedging language (tend to, appear to). Some specialist "
            "vocabulary when the topic warrants it."
        ),
        "grammar": (
            "All conditionals including mixed. Passive voice. Reported "
            "speech (all transformations). Gerunds vs infinitives. "
            "Non-defining relative clauses. Cleft sentences for "
            "emphasis."
        ),
        "sentences": (
            "Vary 8–32 words. Multiple subordinate clauses. Inversions "
            "occasionally for emphasis."
        ),
        "register": (
            "Abstract topics, current affairs, professional subjects, "
            "nuanced opinions, polite disagreement. Mix of formal and "
            "informal as the situation demands."
        ),
        "discourse": (
            "Full range: 'nevertheless', 'consequently', 'in contrast', "
            "'furthermore', 'arguably', 'admittedly', 'in particular'."
        ),
    },
    "C1": {
        "vocabulary": (
            "Top ~7000 words plus advanced collocations, idioms and "
            "register-appropriate jargon. Avoid only the rarest, most "
            "obscure literary terms."
        ),
        "grammar": (
            "Full grammatical range. Subjunctive (If I were…, I suggest "
            "he be…). Cleft and pseudo-cleft structures. Inversion for "
            "stylistic effect. Participle clauses. Complex passive forms."
        ),
        "sentences": (
            "Wide variation. Long sentences with multiple embedded "
            "clauses balanced against short punchy ones for emphasis."
        ),
        "register": (
            "Academic, professional, journalistic, literary. Capable of "
            "irony and understatement. Hedging and stance markers."
        ),
        "discourse": (
            "Sophisticated cohesion. Anaphoric and cataphoric reference. "
            "'notwithstanding', 'thereby', 'insofar as', 'whereas'."
        ),
    },
    "C2": {
        "vocabulary": (
            "Full native range, including rare and idiomatic items. "
            "Precise lexical choice; deploy vocabulary for stylistic "
            "effect, not just meaning."
        ),
        "grammar": (
            "Full range used flexibly. Stylistic deviations from rules "
            "(fragment sentences, fronting, ellipsis) for effect."
        ),
        "sentences": (
            "Rhythm and variation as a stylistic tool. Any length works "
            "if it serves the prose."
        ),
        "register": (
            "Any register, switched fluently. Native-like irony, humour, "
            "subtext, and cultural nuance."
        ),
        "discourse": (
            "Implicit cohesion and inference; explicit markers used only "
            "when they add precision."
        ),
    },
}


# ── Human voice rules ──────────────────────────────────────────────
#
# These apply to *all* generated text. They push the model away from the
# textbook-translation feel that users complained about and toward the
# rhythm of real English — contractions where they belong, real specifics,
# varied sentence length, conversational fillers in dialogue only.

HUMAN_VOICE_RULES: str = """\
WRITE LIKE A HUMAN, NOT A TEXTBOOK
----------------------------------
- Use contractions naturally (it's, don't, I'd, you'll). Avoid the formal
  expanded forms unless the register is specifically academic or legal.
- Prefer concrete specifics over generic abstractions. "She caught the
  6:42 train from Brighton" beats "She travelled by train every day."
- Vary sentence rhythm. Mix short, punchy sentences with longer flowing
  ones. Two short sentences. Then one that breathes a little.
- In dialogue, include real conversational features for the level:
  natural turn-taking, brief interjections ("right", "yeah", "I see"),
  the occasional incomplete thought. Never write dialogue where both
  speakers deliver perfectly-formed paragraphs in turn.
- Anchor every piece in a specific moment, place, or person — not "a
  person decided to" but "Maya stared at the espresso machine".
- Avoid lifeless filler ("In today's world…", "It is important to note
  that…"). If a sentence could open any text on any topic, cut it.
- No meta-commentary about the lesson, the level, or the vocabulary.
  The text is the lesson — it doesn't talk about itself.
- Use neutral, internationally-recognisable settings and names. Mix
  cultural backgrounds across content. Don't default to one country."""


# ── Pedagogical scaffolding block ──────────────────────────────────

PEDAGOGY_RULES: str = """\
PEDAGOGICAL DEPTH
-----------------
- Every lesson starts with a clear, single-sentence learning objective
  ("By the end, you'll be able to ___"). Make it observable.
- For each vocabulary item, show the word in TWO different example
  sentences that use it in different senses or registers where possible.
- For each grammar point, give one positive example and one example of
  the most common learner mistake at this level, with a one-line fix.
- Include at least one open-ended question that asks the learner to
  produce, not just recognise (apply the rule / use the word in their
  own sentence about their own life).
- Build hints in layers. Don't reveal the answer in the question."""


def cefr_block(level: str) -> str:
    """Return a level-specific instruction block ready to paste into a prompt.

    Falls back to B1 if ``level`` is unrecognised so prompts still produce
    something usable rather than silently dropping the level instruction.
    """
    spec = CEFR_MATRIX.get((level or "").upper()) or CEFR_MATRIX["B1"]
    return (
        f"CEFR {level.upper()} SPEC — comply strictly\n"
        f"  • Vocabulary: {spec['vocabulary']}\n"
        f"  • Grammar:    {spec['grammar']}\n"
        f"  • Sentences:  {spec['sentences']}\n"
        f"  • Register:   {spec['register']}\n"
        f"  • Discourse:  {spec['discourse']}"
    )


def build_learner_context(
    profile: Optional[Dict[str, Any]],
    *,
    include_history_hint: bool = False,
) -> str:
    """Render a short, optional learner-profile block.

    Returns an empty string if ``profile`` has nothing actionable, so the
    prompt stays uncluttered for anonymous / first-visit generations. We
    deliberately do **not** assume native language, country, or culture —
    SELM is global and these defaults bias the model's output.
    """
    if not profile:
        return ""
    parts: List[str] = []
    level = profile.get("current_level")
    if level:
        parts.append(f"current CEFR level {level}")

    goals = _as_clean_list(profile.get("learning_goals"))
    if goals:
        parts.append(f"learning goals: {', '.join(goals)}")

    weak = _as_clean_list(profile.get("weak_areas"))
    if weak:
        parts.append(f"areas to strengthen: {', '.join(weak)}")

    interests = _as_clean_list(
        profile.get("preferred_categories") or profile.get("interests")
    )
    if interests:
        parts.append(f"interests: {', '.join(interests)}")

    style = profile.get("learning_style")
    if style:
        parts.append(f"prefers {style} learning style")

    daily = profile.get("daily_study_commitment")
    if daily:
        parts.append(f"~{daily} min/day study budget")

    if not parts:
        return ""

    out = "LEARNER PROFILE (use to tune topic, examples, and difficulty)\n  - " + "\n  - ".join(parts)
    if include_history_hint:
        out += (
            "\n  - if recent conversation context is provided below, "
            "build on it rather than restarting the conversation."
        )
    return out


def _as_clean_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        items: Iterable[str] = [v.strip() for v in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value]
    else:
        return []
    return [v for v in items if v]


# ════════════════════════════════════════════════════════════════════
# CREATIVE-VARIATION REPOSITORY
# ════════════════════════════════════════════════════════════════════
#
# The shallow / templated content problem
# ---------------------------------------
# Before this block existed, every reading text at a given level / type
# came out feeling identical: same Title → Intro → Body → Conclusion,
# same generic narrator, same "In today's world…" opening. The model
# was given one structural recipe per text_type and obediently followed
# it on every call.
#
# What this block does
# --------------------
# It supplies a *deep* pool of dimensions (scenes, opening hooks,
# perspectives, registers, structures, places, professions, etc.) so
# every prompt can pull a fresh random combination. Because the choices
# are made in Python BEFORE the prompt is sent, the model has no chance
# to drift back to its template — the brief it receives is already
# specific. Two requests for "the environment" at B1 produce two
# genuinely different texts: one might be a 2-AM dispatcher's diary
# during a wildfire, the other a daytime market-vendor's interview
# about plastic packaging.
#
# Coverage
# --------
# All values are deliberately INTERNATIONAL and culturally neutral —
# protagonists, cities, professions span every continent. Nothing
# defaults to one country, one religion, or one demographic.
#
# Sizing
# ------
# Each list is large enough that ten consecutive generations are
# extremely unlikely to repeat the same combination. Keep these lists
# growing over time; that's the whole point.

# ── Where the piece is set ────────────────────────────────────────
SCENES: List[str] = [
    "a backstage corridor five minutes before curtain",
    "a community garden during the first frost",
    "a hospital cafeteria at 2 a.m.",
    "a remote-team video call where the connection keeps freezing",
    "a refugee resettlement office on a busy Monday morning",
    "a chef's tasting-menu trial run in an empty restaurant",
    "an airport gate during a four-hour delay",
    "a small-claims court waiting bench",
    "a startup pitch meeting that's running long",
    "a parent-teacher conference for a quiet child",
    "a film crew lunch break beside a half-built set",
    "a basement band rehearsal in mid-rainstorm",
    "a marine biologist's dive log between sample collections",
    "a Tuesday-morning meditation class",
    "a high-school reunion in a hotel ballroom",
    "an estate-sale walkthrough the week after a funeral",
    "an architect's site visit on a windy hilltop",
    "a Saturday flea-market stall at closing time",
    "a midnight emergency dispatcher's headset",
    "a copy-edit session for a magazine going to press",
    "a long-distance overnight train with one open compartment",
    "a fishing village's harbour before sunrise",
    "a bike-share docking station in the rain",
    "a vintage-camera repair shop in a narrow alley",
    "a co-working space at the end of a holiday week",
    "a city-council hearing about a small park",
    "a wildlife rehab centre during baby-bird season",
    "a hostel kitchen where three travellers meet for the first time",
    "a printer's workshop the day before a wedding",
    "a research lab the morning a new dataset arrives",
    "a small podcast studio between takes",
    "a Friday-afternoon family kitchen during dinner prep",
    "a beach clean-up after a storm",
    "a multi-storey carpark on level 7",
    "a translation booth at an international conference",
    "a craft brewery's first brew of an experimental beer",
    "an evening pottery class for total beginners",
    "a tutoring centre fifteen minutes before exams begin",
    "a long flight as it crosses a time zone",
    "a community-radio booth at 6 a.m.",
]

# ── How the piece opens (anti-"In today's world…") ───────────────
OPENING_HOOKS: List[str] = [
    "Open with a single concrete sensory detail — a smell, a sound, a texture.",
    "Open mid-action with a named character doing something specific.",
    "Open with a surprising one-line statistic or fact, then anchor.",
    "Open with a direct quote from someone in the scene, no setup.",
    "Open with a question the reader will want answered.",
    "Open with a small object that becomes meaningful by the end.",
    "Open with a confession or an admission.",
    "Open with a counter-intuitive claim, then justify.",
    "Open with a timestamp + place + a tiny tension.",
    "Open with the sentence 'Three things' (or 'Two things' / 'Five things').",
    "Open with weather that mirrors the emotional state.",
    "Open with the protagonist arriving somewhere or leaving somewhere.",
    "Open with a misheard or misread thing — a sign, a message, a name.",
    "Open with a piece of unsolicited advice the protagonist received.",
    "Open with a number that doesn't quite add up.",
    "Open with two short declarative sentences. Then a longer one.",
    "Open with someone laughing or crying, before we know why.",
    "Open with a memory the protagonist immediately interrupts.",
    "Open with a list of names, of which one will matter.",
    "Open in the middle of a half-finished sentence the narrator continues.",
]

# ── Narrative perspective ────────────────────────────────────────
PERSPECTIVES: List[str] = [
    "first-person participant in the scene",
    "first-person observer who isn't the protagonist",
    "third-person limited to one character's inner thoughts",
    "third-person omniscient, gently moving between two characters",
    "second-person address ('you walk into…')",
    "documentary / journalistic, with a neutral reporter voice",
    "diary or journal entry, dated",
    "letter to a specific named person",
    "email or message thread with timestamps",
    "interview transcript with Q: and A: labels",
    "bullet-pointed expert tips written by a practitioner",
    "voice-memo transcript — slightly meandering, conversational",
    "obituary-style retrospective (only for serious topics)",
    "field notes by a researcher",
    "podcast-script style with [music in] / [music out] cues",
    "advice-column format: a letter, then a thoughtful reply",
]

# ── Emotional / tonal register ────────────────────────────────────
REGISTERS: List[str] = [
    "curious and investigative",
    "warm and nostalgic",
    "frustrated, venting honestly",
    "calmly resolute under pressure",
    "playful and teasing",
    "solemn, weighty, slow",
    "excited and breathless",
    "reflective and melancholic",
    "persuasive and confident",
    "self-deprecating and quietly funny",
    "dry, deadpan observer",
    "tenderly affectionate without sentimentality",
    "wry, faintly cynical but not bitter",
    "earnest and unguarded",
    "polite but firm — a complaint kept under control",
    "hopeful in a way that knows the odds",
]

# ── Structural variation (replaces fixed Title→Intro→Body→Conclusion) ──
STRUCTURES_GENERIC: List[str] = [
    "linear chronological narrative",
    "in-medias-res open, then a brief flashback, then forward",
    "Q&A format — questions a reader would actually ask",
    "listicle: five short numbered points, each with one specific example",
    "compare & contrast: two cases, side-by-side, then a takeaway",
    "problem → exploration → tentative resolution",
    "three short vignettes, each one paragraph",
    "hypothetical scenario walkthrough ('imagine that…')",
    "step-by-step expert breakdown",
    "two-voice interview — one curious, one experienced",
    "letter to one's younger self, then a P.S.",
    "found-object meditation — describe a single object, expand outward",
    "before / during / after triptych",
    "myth-bust: three common beliefs, with the truth after each",
    "ring composition — end echoes the opening image",
    "diary entries from three consecutive days",
    "monologue with one short interjection from a second voice",
    "case study format: situation → complication → response → outcome",
]

# Specialised structures keyed by text_type so an "article" doesn't end
# up as a "letter to younger self" if the caller asked specifically for
# an article. Fall back to STRUCTURES_GENERIC.
STRUCTURES_BY_TYPE: Dict[str, List[str]] = {
    "article": [
        "lead with a specific human moment, then widen to the broader idea, narrow back",
        "expert-tip listicle — five concrete tips, each with a one-sentence example",
        "myth-bust format — three common misconceptions, each followed by the reality",
        "case-study deep-dive — one specific situation, traced from cause to result",
        "compare two approaches side-by-side, then state which works when and why",
        "Q&A: a curious reader's five questions answered briefly",
        "before / during / after — show the same thing across three moments in time",
    ],
    "story": [
        "linear narrative with one clear turning point",
        "in-medias-res open, brief flashback to fill in stakes, forward to resolution",
        "ring composition — closing image echoes the opening image but changed",
        "three short scenes from one day, in order",
        "two parallel storylines that touch at the end",
        "frame story — a character tells the inner story to someone else",
        "second-person — 'you' as the protagonist throughout",
    ],
    "news": [
        "classic inverted pyramid — most important facts first, context after",
        "feature-news hybrid — open on the human at the centre, widen to the facts",
        "Q&A explainer — what happened / why it matters / what's next",
        "by-the-numbers — frame the story around three concrete figures",
        "voices-from-the-scene — quote first, then context, then more quotes",
    ],
    "letter": [
        "personal letter — warm greeting, specific shared memory, the real reason for writing",
        "complaint letter — polite opener, specific incident, the remedy requested",
        "letter of recommendation — concrete examples of the person's work, then the verdict",
        "thank-you letter — what you did, why it mattered, what changed",
        "letter to a stranger — explain why you're writing to someone you've never met",
        "open letter — addressed to a person, but written for a wider audience",
    ],
    "essay": [
        "argumentative — thesis → strongest reason → counter-argument → rebuttal → conclusion",
        "reflective — a personal incident, what it taught, what the writer now believes",
        "compare-and-contrast — two ideas weighed against each other, then a stance",
        "definition essay — what a contested word actually means, with three examples",
        "process essay — how something happens or is done, in stages",
        "exploratory — three angles on a question with no firm conclusion, just better questions",
    ],
    "dialogue": [
        "everyday transaction with a small wrinkle — neither speaker is angry",
        "expert-to-novice — one explains, the other asks naturally curious follow-ups",
        "polite disagreement that ends in compromise, not a winner",
        "reconnection — two people who haven't talked in a while feel each other out",
        "negotiation over a small but specific stake",
        "venting + listening — one speaker unloads, the other helps without fixing",
        "shared discovery — both speakers learn the same thing at the same time",
    ],
    "instruction": [
        "step-by-step with a 'common mistake' callout after each step",
        "two-track instructions — 'if you have X, do this; if you have Y, do this'",
        "warning-first — what to be careful of before starting",
        "story-driven — a short anecdote of someone doing it wrong, then the right way",
        "checklist + explanation — short imperative bullets, then a sentence on each",
        "troubleshooting matrix — symptom → cause → fix",
    ],
}

# ── Time / season / place anchors (force concrete specificity) ───
TIMES_OF_DAY: List[str] = [
    "just before sunrise", "early morning", "mid-morning", "noon",
    "early afternoon", "late afternoon", "dusk", "early evening",
    "late evening", "after midnight",
]
SEASONS: List[str] = [
    "early spring", "late spring", "early summer", "high summer",
    "late summer", "early autumn", "late autumn", "early winter",
    "deep winter", "the first warm week of the year",
    "the last cold week of the year", "monsoon season",
    "the dry season",
]
# International cities — deliberate spread across regions, languages, and
# economies. Add more whenever you notice the rotation feels narrow.
GLOBAL_CITIES: List[str] = [
    "Lagos", "Helsinki", "Kyoto", "Lima", "Manchester", "Cape Town",
    "Vienna", "Bogotá", "Karachi", "Auckland", "Tunis", "Riga",
    "Cusco", "Hanoi", "Belfast", "Tbilisi", "Quito", "Reykjavik",
    "Marrakech", "Montréal", "Wellington", "Porto", "Tashkent",
    "Tallinn", "Nairobi", "Sapporo", "Bratislava", "Asunción",
    "Tirana", "Dakar", "Galway", "Hobart", "Antwerp", "Bursa",
    "Halifax", "Penang", "Bergen", "Cartagena", "Naples", "Plovdiv",
    "Yogyakarta", "Querétaro", "Ljubljana", "San Salvador",
    "Trondheim", "Ulaanbaatar", "Adelaide", "Astana", "Trieste",
    "Chiang Mai", "Maputo", "Stavanger", "Strasbourg", "Vilnius",
    "Bordeaux", "Cebu", "Aarhus", "Christchurch", "Cluj-Napoca",
    "Curitiba", "Galicia",
]
# International first names — carefully mixed across regions. The lists
# are pools to draw from; calling code picks one at random.
NAMES_F: List[str] = [
    "Amaka", "Sanne", "Yumi", "Lucía", "Aroha", "Nadia", "Liesel",
    "Ingrid", "Priya", "Mireille", "Mariana", "Ayşe", "Petra",
    "Elif", "Ndidi", "Hyun-ji", "Soraya", "Tamar", "Beatriz",
    "Anneliese", "Kavya", "Wendy", "Linnea", "Selin", "Olamide",
    "Mei", "Catalina", "Suheyla", "Aida", "Sigrid", "Anouk",
    "Anya", "Esperanza", "Halime", "Idoia",
]
NAMES_M: List[str] = [
    "Tomás", "Adebayo", "Hiroshi", "Mateusz", "Idris", "Anton",
    "Mateo", "Kwame", "Niall", "Rishi", "Aleksandar", "Olamide",
    "Heitor", "Faraz", "Diego", "Mads", "Yusuf", "Kenji",
    "Ravi", "Aapo", "Onyeka", "Ilya", "Soren", "Aki",
    "Bastian", "Eitan", "Tomi", "Hamza", "Patrick", "Mehmet",
    "Lars", "Sebastián", "Pita", "Otto",
]
PROFESSIONS: List[str] = [
    "civil-engineer", "marine biologist", "midwife", "data analyst",
    "kindergarten teacher", "paramedic", "court interpreter",
    "wildlife rehab volunteer", "freelance translator", "tram driver",
    "junior architect", "agricultural-extension officer", "barista",
    "physiotherapist", "wedding photographer", "fishery inspector",
    "subway engineer", "social worker", "lab technician",
    "indie game developer", "bicycle mechanic", "violin maker",
    "city-bus dispatcher", "field linguist", "hospice nurse",
    "documentary editor", "auditor", "park ranger", "sound designer",
    "school librarian", "podcaster", "ceramicist", "rural GP",
    "shipping clerk", "investment-fraud investigator", "luthier",
    "civic-tech engineer", "harbour pilot", "tour guide",
]

# Dialogue-specific axes (used by conversation prompts).
DIALOGUE_RELATIONSHIPS: List[str] = [
    "two co-workers who don't usually work together",
    "longtime friends catching up after months apart",
    "a customer and a service worker who clearly know each other",
    "a parent and an adult child negotiating a small decision",
    "two strangers thrown together by a delay",
    "a mentor and someone they're informally coaching",
    "neighbours who get along but have one running irritation",
    "siblings who see each other rarely",
    "a host and a guest at a small gathering",
    "a teacher and a former student who's now an adult",
    "two volunteers on a one-day project",
    "a manager and a direct report in a 1:1",
    "a freelance contractor and a long-term client",
    "two members of a hobby group",
    "an interviewer and an interviewee, both relaxed",
    "a peer and a peer who disagree professionally",
]
DIALOGUE_TENSIONS: List[str] = [
    "a small misunderstanding that needs clearing up",
    "a piece of news one of them is unsure how to share",
    "a request that's awkward to ask for",
    "a difference of opinion worked out without drama",
    "a moment of recognition — they see something new in each other",
    "shared puzzlement about a third party",
    "negotiating who picks up the bill / handles the task",
    "one apologising; the other quietly accepting",
    "a return-of-a-borrowed-thing conversation with subtext",
    "celebrating a small win together",
    "polite navigation around a sensitive topic",
    "comparing notes about the same shared event",
]


def creative_seed(text_type: Optional[str] = None) -> Dict[str, str]:
    """Pull one random combination from every variation pool.

    Each call returns a fresh dict, so two requests for the same topic +
    level produce structurally different content. ``text_type`` (article,
    story, dialogue, ...) is used to pick a type-appropriate structural
    pattern; pass ``None`` for the generic pool.

    The returned dict also includes a ``voice_category`` — an ElevenLabs
    voice-pool key (e.g. ``narrator_warm``, ``young_male``) — so the
    audio-generation step can pick a voice that *fits the writing*
    instead of always using Rachel. Pass the value through to
    ``tts.generate_audio_content(..., speaker_config=[{"voice_category":
    seed["voice_category"]}])``.

    Notes for callers:
      • The dict is human-readable — feed it straight into the prompt via
        :func:`render_creative_brief`.
      • Do not persist the dict; new seed every generation = real variety.
      • All values are international/neutral by design.
    """
    tt = (text_type or "").lower()
    structures = STRUCTURES_BY_TYPE.get(tt, STRUCTURES_GENERIC)
    # 50/50 gender mix on protagonists so neither default leaks into stats.
    if random.random() < 0.5:
        name, gender, voice_g = random.choice(NAMES_F), "she/her", "female"
    else:
        name, gender, voice_g = random.choice(NAMES_M), "he/him", "male"

    # Pick a voice category that *fits* the kind of writing we're about
    # to produce. Solo narrator pools for journalistic / explanatory
    # types; person-voice pools for first-person stories and letters.
    # (No child pool — ElevenLabs' default library doesn't ship genuine
    # child voices, and faking one with style tweaks sounds uncanny.
    # Confirmed acceptable by Ebrahim 2026-05-13.)
    if tt in {"article", "essay", "news", "instruction"}:
        voice_category = random.choice(["narrator_warm", "narrator_dry"])
    elif tt in {"story", "letter"}:
        # Use a voice that matches the protagonist's gender so the
        # narrator and protagonist feel like the same person.
        # Random 70/30 between adult and young so we get a mix of
        # mature and youthful voices across content.
        if random.random() < 0.7:
            voice_category = "adult_female" if voice_g == "female" else "adult_male"
        else:
            voice_category = "young_female" if voice_g == "female" else "young_male"
    else:
        # Generic / unknown type — let the TTS fallback randomise.
        voice_category = random.choice(
            ["narrator_warm", "narrator_dry", "adult_female", "adult_male"]
        )

    return {
        "scene": random.choice(SCENES),
        "opening_hook": random.choice(OPENING_HOOKS),
        "perspective": random.choice(PERSPECTIVES),
        "register": random.choice(REGISTERS),
        "structure": random.choice(structures),
        "time_of_day": random.choice(TIMES_OF_DAY),
        "season": random.choice(SEASONS),
        "place": random.choice(GLOBAL_CITIES),
        "protagonist_name": name,
        "protagonist_pronouns": gender,
        "profession": random.choice(PROFESSIONS),
        "voice_category": voice_category,
    }


def dialogue_seed() -> Dict[str, str]:
    """Pull a dialogue-specific creative combination.

    Returns two named speakers with international variety, a relationship
    type, an emotional tension, and a scene. Dialogue-specific because
    "writing two people talking" needs different variation axes from
    "writing a passage".
    """
    # Two different names, possibly different genders.
    pool: List[tuple] = (
        [(n, "she/her") for n in NAMES_F]
        + [(n, "he/him") for n in NAMES_M]
    )
    a, b = random.sample(pool, 2)
    return {
        "speaker_a_name": a[0],
        "speaker_a_pronouns": a[1],
        "speaker_b_name": b[0],
        "speaker_b_pronouns": b[1],
        "relationship": random.choice(DIALOGUE_RELATIONSHIPS),
        "tension": random.choice(DIALOGUE_TENSIONS),
        "scene": random.choice(SCENES),
        "register": random.choice(REGISTERS),
        "structure": random.choice(STRUCTURES_BY_TYPE["dialogue"]),
        "time_of_day": random.choice(TIMES_OF_DAY),
        "place": random.choice(GLOBAL_CITIES),
    }


def render_creative_brief(seed: Dict[str, str]) -> str:
    """Render a creative_seed() result as a ready-to-paste prompt block.

    Wording is deliberately bossy: every line says "use THIS, not a
    default". The model is good at following concrete instructions but
    poor at maintaining diversity on its own.
    """
    return (
        "CREATIVE BRIEF — use these specific choices, do not default to a\n"
        "generic structure or a stock opening:\n"
        f"  • Scene:             {seed['scene']}\n"
        f"  • Opening hook:      {seed['opening_hook']}\n"
        f"  • Perspective:       {seed['perspective']}\n"
        f"  • Emotional tone:    {seed['register']}\n"
        f"  • Structural shape:  {seed['structure']}\n"
        f"  • Time anchor:       {seed['time_of_day']} during {seed['season']}\n"
        f"  • Place anchor:      {seed['place']}\n"
        f"  • If a person is needed: a {seed['profession']} named "
        f"{seed['protagonist_name']} ({seed['protagonist_pronouns']}).\n"
        "  Use these anchors concretely — name the place by name, name the\n"
        "  person by name. Don't write 'in a city' when the city is given."
    )


def render_dialogue_brief(seed: Dict[str, str]) -> str:
    """Render a dialogue_seed() result as a ready-to-paste prompt block."""
    return (
        "DIALOGUE BRIEF — write THIS specific conversation:\n"
        f"  • Speakers:        {seed['speaker_a_name']} "
        f"({seed['speaker_a_pronouns']}) and {seed['speaker_b_name']} "
        f"({seed['speaker_b_pronouns']})\n"
        f"  • Relationship:    {seed['relationship']}\n"
        f"  • Tension / hook:  {seed['tension']}\n"
        f"  • Scene:           {seed['scene']}\n"
        f"  • Time:            {seed['time_of_day']}\n"
        f"  • Place:           {seed['place']}\n"
        f"  • Tone:            {seed['register']}\n"
        f"  • Shape:           {seed['structure']}\n"
        "  Make each speaker sound distinct — different sentence length,\n"
        "  different reactive habits, different vocabulary preferences."
    )
