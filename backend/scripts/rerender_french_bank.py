#!/usr/bin/env python
"""Re-render the 39 TCF listening recordings, one declared variety each.

    python scripts/rerender_french_bank.py --dry-run
    python scripts/rerender_french_bank.py --gate-passed

The plan ships with the code — `scripts/tcf-variety-plan.json`, generated from
`tcf-variety-plan.ts` and checked against it by `comprehension.check.ts`. It is
committed rather than carried here by hand because a hand-carried plan will one
day be a stale one, and nothing would notice: it would still parse, and 39
perfectly good files would render in the wrong varieties.

`--gate-passed` is required to write any audio, and it is not a formality.
`SELM-RULINGS-voices.md` §4.2:

    "Render one item per variety first, have it heard, then run the batch.
    Rendering 39 files against an unheard cast would repeat the mistake this
    ruling is correcting."

So: run `render_variety_gate.py`, listen to all five, confirm or replace the
entries in `french-voices.ts`, and only then pass the flag. The flag is the
person saying they listened. Nothing here can check that, which is exactly why
it is a separate deliberate act rather than a default.

## What it produces

For each recording: an mp3, and a manifest row recording the variety asked for,
the voice that answered, its id and the model. The manifest is the point as much
as the audio — `Recording.voice` exists so that a substituted accent is one
comparison away from being caught, and a batch that renders without writing
provenance rebuilds the defect it is fixing.

## What it refuses to do

If the account holds no voice of a recording's planned variety, that recording
is SKIPPED and reported. It is never rendered with a substitute. A missing file
is visible; a file in the wrong variety is not.

Two-speaker recordings need two voices of one variety. Where the account has
only one, the recording is skipped for the same reason. (The plan already keeps
Belgian off dialogues for this reason — see `tcf-variety-plan.ts`.)

## Cost

About 40,000 characters, roughly 40,000 credits, against a balance of ~348,000
running at 4% utilisation. The ruling dismissed the cost objection on those
figures; it is recorded here so nobody re-opens it.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Which cast role speaks each variety, and the fallback order within it.
# Names must match the account exactly; they mirror TCF_VOICE_CAST.
CAST = {
    "international": ["Julia - Warm French Narrator", "Antoine - Audiobook Narrator",
                      "Clémence - Advertising", "David - Professional Narrator"],
    "quebecois": ["Amélie - Young, Confident and Friendly", "Alexandre - Authentic French Canadian"],
    "west_african": ["Alimata - Professional and Welcoming", "Keli - Calm & Natural African"],
    "belgian": ["Christophe Géradon - Soft and Narrative", "Adrien Piret - Young and Friendly"],
    "swiss": ["Nathalie - Tender and Optimistic", "Peter - Clear, Engaging and Professional"],
    "acadian": ["Evangeline - Warm Acadian Conversational", "Seddik - French"],
}

MODEL = "eleven_flash_v2_5"


async def main(args) -> int:
    from app.services.elevenlabs_tts_service import ElevenLabsTTSService

    plan = json.load(open(args.plan, encoding="utf-8"))
    service = ElevenLabsTTSService()
    if not service.api_key:
        print("ELEVENLABS_API_KEY is not set.", file=sys.stderr)
        return 2

    # Resolve the whole cast up front. Discovering a missing voice on
    # recording 27 of 39 means 26 files rendered against a cast that was never
    # complete, and no clean way to say which half is trustworthy.
    resolved: dict[str, list[tuple[str, str]]] = {}
    missing: list[str] = []
    for variety, names in CAST.items():
        pairs = []
        for name in names:
            vid = await service.voice_id_for_name(name)
            if vid:
                pairs.append((name, vid))
            else:
                missing.append(f"{variety}: {name}")
        resolved[variety] = pairs

    needed = {row["variety"] for row in plan}
    unserved = sorted(v for v in needed if not resolved.get(v))
    if missing:
        print("Voices named in the cast that are not on the account:")
        for m in missing:
            print(f"  - {m}")
    if unserved:
        print(f"\nCannot proceed: no voice at all for {', '.join(unserved)}.", file=sys.stderr)
        return 2

    if not args.gate_passed and not args.dry_run:
        print(
            "Refusing to render.\n\n"
            "Run scripts/render_variety_gate.py, listen to all five samples, and\n"
            "confirm or replace the entries in french-voices.ts. Then pass\n"
            "--gate-passed. Rendering 39 files against a cast nobody has heard\n"
            "is the mistake this whole exercise is correcting.",
            file=sys.stderr,
        )
        return 3

    os.makedirs(args.out, exist_ok=True)
    manifest, skipped, chars = [], [], 0

    for row in plan:
        variety, rec_id = row["variety"], row["id"]
        speakers = int(row.get("speakers") or 1)
        script = row.get("script") or ""
        pool = resolved[variety]

        if speakers > 1 and len(pool) < 2:
            skipped.append((rec_id, variety, f"needs {speakers} voices, account has {len(pool)}"))
            continue
        if not script:
            skipped.append((rec_id, variety, "no script in the plan file"))
            continue

        name, voice_id = pool[0]
        chars += len(script)
        if args.dry_run:
            manifest.append({"id": rec_id, "variety": variety, "voice": name,
                             "voiceId": voice_id, "chars": len(script), "rendered": False})
            continue

        result = await service.generate_audio_content(
            script,
            speaker_config=[{"voice_id": voice_id}],
            voice_settings={"model_id": MODEL},
        )
        if not result.get("success"):
            skipped.append((rec_id, variety, str(result.get("error"))[:120]))
            continue

        path = os.path.join(args.out, f"{rec_id}.mp3")
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(result.get("audio_data_base64") or ""))

        manifest.append({
            "id": rec_id,
            "variety": variety,
            "audioPath": f"tcf-co/{rec_id}.mp3",
            # This block is what goes into Recording.voice. Written here, at
            # render time, by the thing that did the rendering — never inferred
            # later from a filename or a cast file that may since have changed.
            "voice": {
                "voiceId": result.get("voice_id") or voice_id,
                "vendorName": name,
                "requestedVariety": variety,
                "modelId": result.get("tts_model") or MODEL,
                "renderedAt": datetime.date.today().isoformat(),
            },
            "rendered": True,
        })
        print(f"  {rec_id:14} {variety:14} {name}")

    out = os.path.join(args.out, "manifest.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f"\n{len(manifest)} rendered, {len(skipped)} skipped, ~{chars:,} characters.")
    print(f"Manifest: {out}")
    if skipped:
        print("\nSkipped — NOT rendered with a substitute voice, deliberately:")
        for rec_id, variety, why in skipped:
            print(f"  {rec_id:14} {variety:14} {why}")
    return 1 if skipped else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "tcf-variety-plan.json"),
                    help="JSON list of {id, level, speakers, variety, script}; "
                         "defaults to the committed plan beside this script")
    ap.add_argument("--out", default="rerender-out")
    ap.add_argument("--gate-passed", action="store_true",
                    help="you have listened to every sample from render_variety_gate.py")
    ap.add_argument("--dry-run", action="store_true", help="resolve and count, render nothing")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
