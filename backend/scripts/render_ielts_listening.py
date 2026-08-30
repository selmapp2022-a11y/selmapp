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

# ORDER MATTERS, and it is the same convention the French batch uses: entry 0
# is the voice a monologue gets, entries 0 and 1 are the two speakers of a
# dialogue. `None` in the second slot means the account holds ONE voice of
# this variety — and a dialogue planned onto it is skipped rather than
# rendered with a speaker of another accent.
#
# Irish is male-only on this account and Scottish is female-only. That is not
# worked around: `ielts-variety-plan.ts` keeps both off two-speaker parts, and
# `ielts-variety.check.ts` fails if that ever stops being true. This dict is
# the second line of the same defence, because a plan can be edited and this
# script is what actually spends the credits.
CAST = {
    # variety: (first speaker, second speaker or None)
    "canadian":       ("Rebecca", "Dave"),
    "british":        ("Juliet", "Jofra"),
    "australian":     ("Emily", "Neil"),
    "north_american": ("Heather", "Russ"),
    "new_zealand":    ("Ella", "Luke"),
    # Irish and Scottish are OUT of the bank as of 31 August 2026 — the
    # founder narrowed IELTS to Canadian plus the four accents ielts.org
    # names. They are left here, unreferenced by any plan row, because each is
    # a single voice on this account and the RULE that fact demands outlives
    # them: a dialogue needs two voices of one variety, and where the account
    # holds one the renderer would substitute silently.
    "irish":          ("Darren", None),
    "scottish":       ("Claire", None),
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
    ap.add_argument("--only", default="", help="Comma-separated ids. Renders only these.")
    ap.add_argument("--redo-rendered", action="store_true",
                    help="Also render rows the plan marks as already rendered. Off by default: "
                         "the four anchors were heard on 29 August and re-spending on them "
                         "silently is how a batch costs twice what it reports.")
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

    # RESOLVE THE WHOLE CAST BEFORE SPENDING ANYTHING.
    #
    # The founder, 31 August: *"if something comes back at render time that
    # does not match what is claimed — voice_not_found, or a voice whose
    # language does not match the definition — say so there and then and do
    # not continue."*
    #
    # A name that resolves to nothing is the cheap failure. The expensive one
    # is failing on the eleventh of twelve, having already spent on ten, so
    # every name every planned row needs is resolved first and the batch
    # refuses as a whole.
    need = set()
    for row in rows:
        if row["variety"] in CAST:
            a, b = CAST[row["variety"]]
            need.add(a)
            if b and row["speakers"] > 1:
                need.add(b)
    unresolved = []
    for name in sorted(need):
        if not await service.voice_id_for_name(name):
            unresolved.append(name)
    if unresolved:
        print("REFUSING TO RENDER. These cast names do not resolve on this account:")
        for n in unresolved:
            print(f"  {n}")
        print("\nNothing was rendered and nothing was spent. Either the account changed or\n"
              "the name in CAST is stale — a hard-coded id that goes stale returns\n"
              "voice_not_found at render time, which is why this cast is names.")
        return 1

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    manifest, skipped, chars = [], [], 0
    for row in rows:
        if only and row["id"] not in only:
            continue
        # Already rendered and already heard. Skipping is the default because
        # the alternative is a re-run that quietly doubles the bill and
        # replaces four files a person has listened to with four nobody has.
        # Already rendered AND still allowed by the plan. `keep` is what says
        # so: `gt-l-p4` is rendered and NOT kept, because it was spoken Irish
        # before Irish was taken out of the bank, and audio that plays
        # perfectly in a variety the plan forbids is the substitution defect
        # with our own name on it.
        if row.get("rendered") and row.get("keep") and not args.redo_rendered and not only:
            continue
        turns = _turns(row)
        chars += sum(len(t["text"]) for t in turns)
        if row["variety"] not in CAST:
            skipped.append((row["id"], f"no cast entry for variety {row['variety']!r}"))
            continue
        first, second = CAST[row["variety"]]
        # A dialogue needs two voices OF ONE VARIETY. Where the account holds
        # one, the recording is skipped and named — never rendered with a
        # second speaker of another accent. A missing file is visible; a file
        # in the wrong variety is not, and it plays perfectly.
        if row["speakers"] > 1 and second is None:
            skipped.append((row["id"], f"{row['variety']} has one voice on this account and this is a dialogue"))
            continue
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
