"""Render the four IELTS Listening recordings.

    python scripts/render_ielts_listening.py --dry-run
    python scripts/render_ielts_listening.py --cast-heard

WHAT THIS RENDERS, AND WHY IT IS SHAPED THIS WAY
------------------------------------------------
Four parts, about twenty minutes of speech, from `ielts-listening-plan.json` —
which is GENERATED from `ielts-listening.ts` and never edited here. The French
bank learned that lesson: a script that carries its own copy of the material
drifts from the definition the questions were written against, and nothing
notices until a candidate hears a recording that answers a different question.

THE NARRATOR IS A REAL VOICE, NOT A CONVENTION. In IELTS, "Now turn to Part
two" is INSIDE the recording — the candidate hears it. So each part is rendered
as narrator, then the part, then narrator again, through the same multi-voice
path the French dialogues use. That path takes any number of speakers, so the
narrator is simply a third one.

A MONOLOGUE IS STILL RENDERED THROUGH THE MULTI-VOICE PATH, for that reason
alone: it has narrator lines around it even when only one person speaks the
body.

AND IT REFUSES TO RUN WITHOUT --cast-heard, for the same reason the French
batch refuses without --gate-passed. The cast was auditioned and eight of
twenty voices were rejected by ear; the flag is a person saying that happened.
Nothing in the code can check it, which is exactly why it is a deliberate act.
"""
import argparse, asyncio, base64, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.elevenlabs_tts_service import ElevenLabsTTSService  # noqa: E402

MODEL = "eleven_flash_v2_5"
PLAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ielts-listening-plan.json")

# The cast, by display name, as heard and approved on 29 August 2026. Names
# rather than ids, for the reason `ielts-voices.ts` records: a hard-coded id
# that goes stale returns `voice_not_found` at render time, while a name that
# resolves to nothing fails loudly and immediately.
NARRATOR = "James"
CAST = {
    # variety: (first speaker, second speaker)
    "australian": ("Emily", "Neil"),
    "british": ("Juliet", "Jofra"),
    "canadian": ("Rebecca", "Dave"),
    "irish": ("Darren", "Darren"),
}


def _turns(row):
    """The turns of one part, in order, tagged with who says them.

    `N` is the narrator, `A` and `B` are the speakers. A body line beginning
    with an em dash is a turn of dialogue; anything else is continuous speech
    by the single speaker of a monologue.
    """
    out = []
    if row.get("narratorIntro"):
        out.append({"speaker": "N", "text": row["narratorIntro"]})
    if row["speakers"] > 1:
        who = 0
        for line in row["body"]:
            t = line.lstrip()
            if t.startswith("—") or t.startswith("-"):
                out.append({"speaker": "AB"[who % 2], "text": t.lstrip("—- ").strip()})
                who += 1
            elif out:
                out[-1]["text"] += " " + t
    else:
        out.append({"speaker": "A", "text": " ".join(l.strip() for l in row["body"])})
    if row.get("narratorOutro"):
        out.append({"speaker": "N", "text": row["narratorOutro"]})
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/ielts_listening")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cast-heard", action="store_true",
                    help="You have listened to the cast. Required before any audio is written.")
    args = ap.parse_args()

    if not args.dry_run and not args.cast_heard:
        print("Refusing to render: pass --cast-heard.\n"
              "The cast was auditioned on 29 August 2026 and eight of twenty voices were\n"
              "rejected by ear. This flag is a person saying that happened. Nothing here\n"
              "can check it, which is why it is deliberate rather than a default.")
        return 2

    service = ElevenLabsTTSService()
    rows = json.load(open(PLAN, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)

    narrator_id = await service.voice_id_for_name(NARRATOR)
    if not narrator_id:
        print(f"NARRATOR NOT FOUND on the account: {NARRATOR!r}. Nothing rendered.")
        return 1

    manifest, skipped, chars = [], [], 0
    for row in rows:
        turns = _turns(row)
        chars += sum(len(t["text"]) for t in turns)
        first, second = CAST.get(row["variety"], (None, None))
        ids = {}
        names = {}
        # A monologue has no second speaker. Resolving one anyway put a voice
        # into the provenance that never opened its mouth — Part 2's manifest
        # named Jofra, and Part 4 named Darren twice, for recordings in which
        # exactly one person speaks. A provenance record that lists a voice
        # that did not speak is the same defect as one that omits a voice that
        # did, and it was caught by reading the manifest rather than by any
        # check.
        wanted = (("A", first),) if row["speakers"] < 2 else (("A", first), ("B", second))
        for tag, name in wanted:
            if name is None:
                continue
            vid = await service.voice_id_for_name(name)
            if not vid:
                skipped.append((row["id"], f"voice not on the account: {name}"))
                ids = {}
                break
            ids[tag] = vid
            names[tag] = name
        if not ids:
            continue
        ids["N"] = narrator_id
        names["N"] = NARRATOR

        if args.dry_run:
            manifest.append({"id": row["id"], "variety": row["variety"], "turns": len(turns),
                             "voices": names, "chars": sum(len(t['text']) for t in turns)})
            print(f"  {row['id']:10} {row['variety']:11} {len(turns):3} turns  "
                  f"{'+'.join(names[k] for k in sorted(names))}")
            continue

        audio = await service._render_dialogue_via_legacy(turns, ids)
        if not audio:
            skipped.append((row["id"], "render returned no audio"))
            continue
        path = os.path.join(args.out, f"{row['id']}.mp3")
        with open(path, "wb") as fh:
            fh.write(audio)
        manifest.append({
            "id": row["id"],
            "variety": row["variety"],
            "speakers": row["speakers"],
            "audioPath": f"ielts-listening/{row['id']}.mp3",
            # Written here, at render time, by the thing that did the
            # rendering — never inferred later from a filename.
            "voice": {
                "voiceId": ids["A"],
                "voiceIds": [ids[k] for k in ("A", "B", "N") if k in ids],
                "vendorName": " + ".join(names[k] for k in ("A", "B", "N") if k in names),
                "requestedVariety": row["variety"],
                "modelId": MODEL,
                "renderedAt": __import__("datetime").date.today().isoformat(),
            },
            "bytes": len(audio),
            "rendered": True,
        })
        print(f"  {row['id']:10} {row['variety']:11} {len(audio):>9,} bytes  "
              f"{' + '.join(names[k] for k in ('A','B','N') if k in names)}")

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f"\n{len(manifest)} rendered, {len(skipped)} skipped, ~{chars:,} characters.")
    for sid, why in skipped:
        print(f"  SKIPPED {sid}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
