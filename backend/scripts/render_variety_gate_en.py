#!/usr/bin/env python
"""Render ONE recording per ENGLISH variety, so a person can hear the cast.

    python scripts/render_variety_gate_en.py            # render into ./variety-gate-en/
    python scripts/render_variety_gate_en.py --list     # resolve the cast, render nothing

The English half of the gate ruled in `SELM-RULINGS-voices.md` §4.2:

    "Before the first bank is rendered, one recording per variety, listened to,
    and the entry confirmed or replaced. A vendor's accent label is a claim by
    whoever uploaded the voice."

The French half is `render_variety_gate.py`. This is the same gate against
`ENGLISH_VARIETY_MIX` (selm-web/src/exam/model/types.ts) and `IELTS_VOICE_CAST`
(selm-web/src/exam/definitions/ielts-voices.ts) — seven varieties, one voice
each: the one that will carry the most material in that variety.

THE LINES ARE REAL. Every excerpt below is lifted verbatim from the IELTS
listening bank in `ielts-listening.ts`, so what is heard is what a candidate
would hear. Sample text would test whether the voice sounds pleasant; a bank
line tests whether it can carry an exam.

The narrator ('James - English Storyteller') is not here: it was heard on
29 August on its own real line and approved. Its note about stability stands.

Seven clips, roughly 1,100 characters, about 1,100 credits against a balance
of ~348,000. Cost is not a consideration and should not be presented as one.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# variety -> (voice display name on the account, recording id, real bank line)
GATE = [
    (
        "british",
        "Juliet - British, Natural and Engaging",
        "gt-l-p2",
        "Good morning, everyone, and thank you for giving up your Saturday. "
        "Before we put anyone to work, let me walk you round the plan so you "
        "know where things are — you'll be surprised how often people end up "
        "watering the wrong beds.",
    ),
    (
        "north_american",
        "Russ – Deep, Smooth and Articulate",
        "gt-l-p4",
        "People assume the heat is produced by the city: by cars, by air "
        "conditioning, by industry. Some of it is, but that is the smaller "
        "part. The larger part is not produced at all. It is stored.",
    ),
    (
        "canadian",
        "Rebecca - Calm, Warm and Engaging",
        "gt-l-p1",
        "Now, we run three kinds of membership. There's Standard, which is the "
        "gym and the pool. There's Active, which adds every class on the "
        "timetable. And there's Family, which covers two adults and up to "
        "three children.",
    ),
    (
        "australian",
        "Emily - Calm, clear female Australian",
        "gt-l-p3",
        "Section two is the survey design. That one I think we have to do "
        "together — if I write the questions and you analyse the answers, "
        "we'll end up with data that doesn't answer anything.",
    ),
    (
        "new_zealand",
        "Luke - New Zealand, Deep, and Steady",
        "gt-l-p3",
        "We don't present all six. We present the two case studies properly "
        "and summarise the rest in one slide. There's a difference between "
        "being ready for a question and spending eight of our twenty minutes "
        "on it.",
    ),
    (
        "irish",
        "Darren - Calm and Deep",
        "gt-l-p2",
        "We do not cancel for rain. We cancel for high wind, because of the "
        "trees along the river, and you'll get a text by eight in the morning "
        "if a session is off. If you haven't had a text, assume we're on.",
    ),
    (
        "scottish",
        "Claire - Warm and Measured",
        "gt-l-p1",
        "One more thing about the lockers. They take a one-pound coin, and you "
        "get it back when you return the key — but if you lose the key there's "
        "a charge of fifteen pounds for a replacement.",
    ),
]

OUT_DIR = os.environ.get("GATE_OUT", "variety-gate-en")
MODEL = "eleven_flash_v2_5"


async def main(list_only: bool) -> int:
    from app.services.elevenlabs_tts_service import ElevenLabsTTSService

    service = ElevenLabsTTSService()
    if not service.api_key:
        print("ELEVENLABS_API_KEY is not set in this environment.", file=sys.stderr)
        return 2

    if not list_only:
        os.makedirs(OUT_DIR, exist_ok=True)

    problems = 0
    print(f"{'variety':16} {'voice':42} {'voice_id':22} result")
    print("-" * 104)

    for variety, voice_name, rec_id, text in GATE:
        voice_id = await service.voice_id_for_name(voice_name)
        if not voice_id:
            # The honest failure. A missing voice must stop the gate, not fall
            # back — a fallback here would render the sample in the wrong
            # variety and the listener would approve the wrong thing.
            print(f"{variety:16} {voice_name:42} {'-':22} NOT ON THE ACCOUNT")
            problems += 1
            continue

        if list_only:
            print(f"{variety:16} {voice_name:42} {voice_id:22} (not rendered)")
            continue

        result = await service.generate_audio_content(
            text,
            speaker_config=[{"voice_id": voice_id}],
            voice_settings={"model_id": MODEL},
        )
        if not result.get("success"):
            print(f"{variety:16} {voice_name:42} {voice_id:22} FAILED: {result.get('error')}")
            problems += 1
            continue

        import base64

        path = os.path.join(OUT_DIR, f"{variety}__{rec_id}.mp3")
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(result.get("audio_data_base64") or ""))
        size = os.path.getsize(path)
        print(f"{variety:16} {voice_name:42} {voice_id:22} {path} ({size:,} bytes)")

    if not list_only:
        print(f"\nWritten to ./{OUT_DIR}/ — listen to all seven before running any batch.")
        print("The question is not 'is this a good voice' but 'is this the variety")
        print("it claims to be'. If it is not, replace the entry in ielts-voices.ts")
        print("and run this again.")
    if problems:
        print(f"\n{problems} problem(s). The gate is NOT passed.", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="resolve the cast, render nothing")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.list)))
