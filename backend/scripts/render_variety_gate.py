#!/usr/bin/env python
"""Render ONE recording per French variety, so a person can hear the cast.

    python scripts/render_variety_gate.py            # render into ./variety-gate/
    python scripts/render_variety_gate.py --list     # show the cast, render nothing

Ruled 29 August 2026, `SELM-RULINGS-voices.md` §4.2:

    "Before the first bank is rendered, one recording per variety, listened to,
    and the entry confirmed or replaced. A vendor's accent label is a claim by
    whoever uploaded the voice. This applies to the re-render in §1 too. Render
    one item per variety first, have it heard, then run the batch. Rendering 39
    files against an unheard cast would repeat the mistake this ruling is
    correcting."

This is that gate. It is a script rather than something already run because the
session that wrote it could not reach the vendor: the API key lives on the
server, and typing a render into the DigitalOcean console was blocked. Making it
a script is the better outcome anyway — the batch re-render uses the same voice
resolution, so if this sounds right, that will too, and anyone can re-run it
when the cast changes.

Five clips, roughly 900 characters in total, about 900 credits — against a
balance of ~348,000. Cost is not a consideration here and should not be
presented as one.

The scripts are REAL lines from the TCF bank, not sample text, so what is heard
is what a candidate would hear.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# variety -> (voice display name on the account, recording id, script)
# Mirrors TCF_VOICE_CAST in selm-web/src/exam/definitions/french-voices.ts.
# One voice per variety: the one that will carry the most material in it.
GATE = [
    (
        "international",
        "Julia - Warm French Narrator",
        "tcf-co-14-r",
        "Chers usagers, la bibliothèque restera ouverte pendant toute la durée "
        "des travaux. En revanche, l'entrée principale sera fermée : utilisez la "
        "porte située du côté du parc. Les retours de livres se font toujours à "
        "l'accueil.",
    ),
    (
        "quebecois",
        "Amélie - Young, Confident and Friendly",
        "tcf-co-12-r",
        "Bonjour Madame, je vous appelle au sujet de votre demande de logement. "
        "Votre dossier est presque complet : il ne manque que la preuve de "
        "revenus. Sans ce document, nous ne pourrons pas l'examiner avant la fin "
        "du mois.",
    ),
    (
        "west_african",
        "Keli - Calm & Natural African",
        "tcf-co-06-r",
        "Mesdames et messieurs, en raison de travaux, l'autobus numéro 12 ne "
        "s'arrête pas devant l'hôpital ce matin. Merci de descendre à l'arrêt "
        "suivant.",
    ),
    (
        "belgian",
        "Christophe Géradon - Soft and Narrative",
        "tcf-co-17-r",
        "Voici mon message pour l'équipe : la réunion de vendredi est déplacée à "
        "mardi prochain, même heure, même salle. Ceux qui ne pourront pas venir "
        "sont invités à envoyer leurs commentaires par écrit avant lundi soir.",
    ),
    (
        "swiss",
        "Peter - Clear, Engaging and Professional",
        "tcf-co-20-r",
        "Selon une étude publiée cette semaine, le télétravail n'a pas fait "
        "baisser la productivité des entreprises interrogées. Ce sont plutôt les "
        "réunions qui se sont multipliées.",
    ),
]

OUT_DIR = os.environ.get("GATE_OUT", "variety-gate")
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
    print(f"{'variety':14} {'voice':42} {'voice_id':22} result")
    print("-" * 100)

    for variety, voice_name, rec_id, text in GATE:
        voice_id = await service.voice_id_for_name(voice_name)
        if not voice_id:
            # The honest failure. A missing voice must stop the gate, not fall
            # back — a fallback here would render the sample in the wrong
            # variety and the listener would approve the wrong thing.
            print(f"{variety:14} {voice_name:42} {'-':22} NOT ON THE ACCOUNT")
            problems += 1
            continue

        if list_only:
            print(f"{variety:14} {voice_name:42} {voice_id:22} (not rendered)")
            continue

        result = await service.generate_audio_content(
            text,
            speaker_config=[{"voice_id": voice_id}],
            voice_settings={"model_id": MODEL},
        )
        if not result.get("success"):
            print(f"{variety:14} {voice_name:42} {voice_id:22} FAILED: {result.get('error')}")
            problems += 1
            continue

        import base64

        path = os.path.join(OUT_DIR, f"{variety}__{rec_id}.mp3")
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(result.get("audio_data_base64") or ""))
        size = os.path.getsize(path)
        print(f"{variety:14} {voice_name:42} {voice_id:22} {path} ({size:,} bytes)")

    if not list_only:
        print(f"\nWritten to ./{OUT_DIR}/ — listen to all five before running the batch.")
        print("For each one, the question is not 'is this a good voice' but")
        print("'is this the variety it claims to be'. If it is not, replace the")
        print("entry in french-voices.ts and run this again.")
    if problems:
        print(f"\n{problems} problem(s). The gate is NOT passed.", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="resolve the cast, render nothing")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.list)))
