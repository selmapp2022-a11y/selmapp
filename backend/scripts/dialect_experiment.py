"""B2 — does the speech scorer behave differently under fr-fr and fr-ca?

Step 07 named the trap and this script is written around it: **the accent of
the recording is the experiment, not a disclosure.** Feed the scorer neutral
metropolitan French and a null result cannot distinguish

  * the two settings are identical, from
  * this audio never exercised the difference.

So the run reports three things, and only two of them are readable without a
Canadian-French speaker:

  1. REPEATABILITY BASELINE — ten identical calls at one dialect. Readable
     whatever the accent. Without it, "differs" has no noise floor to be
     judged against, and step 06 is the reason: a judge went from a spread of
     0 to a spread of 6 in two days.
  2. en-us AS CONTROL, not as a third condition. French audio scored at en-us
     against the same audio at fr-fr. **Readable whatever the accent.** If
     they match, the dialect parameter does nothing on this endpoint — which
     is what the writing endpoint turned out to do, and it would be the second
     time.
  3. fr-fr AGAINST fr-ca. Readable only if the audio contains something the
     two settings could plausibly disagree about.

Usage:

    SPEECHACE_API_KEY=... python3 scripts/dialect_experiment.py path/to/audio.wav \
        --speaker "who recorded it, and their accent"

Nothing here writes to the repository and nothing here is scheduled. It is
run when there is a reason to run it, and it prints a dated result.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from datetime import datetime, timezone

import aiohttp

URL = "https://api.speechace.co/api/scoring/speech/v9/json"
DIALECTS = ["fr-fr", "fr-ca", "en-us"]
BASELINE_CALLS = 10


def pick(data: dict) -> dict:
    """The comparable numbers, whatever shape the response arrives in."""
    out: dict = {}
    tf = (data.get("text_score") or {}) if isinstance(data, dict) else {}
    for k in ("quality_score", "pronunciation_score", "fluency_score"):
        v = tf.get(k)
        if isinstance(v, (int, float)):
            out[k] = float(v)
    fl = tf.get("fluency") or {}
    for k in ("overall_metrics", "fluency_score"):
        v = fl.get(k) if isinstance(fl, dict) else None
        if isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, (int, float)):
                    out[f"fluency.{kk}"] = float(vv)
        elif isinstance(v, (int, float)):
            out[f"fluency.{k}"] = float(v)
    cefr = (data.get("cefr_score") or {}).get("pronunciation")
    if cefr:
        out["cefr_pronunciation"] = cefr
    return out


async def call(session: aiohttp.ClientSession, key: str, audio: bytes, dialect: str) -> dict:
    form = aiohttp.FormData()
    form.add_field("user_audio_file", audio, filename="audio.wav", content_type="audio/wav")
    async with session.post(URL, params={"key": key, "dialect": dialect}, data=form) as r:
        body = await r.text()
        try:
            data = json.loads(body)
        except ValueError:
            return {"error": f"HTTP {r.status}, non-JSON: {body[:200]}"}
        if (data.get("status") or "").lower() not in ("", "success"):
            return {"error": data.get("detail_message") or data.get("short_message") or "vendor error"}
        return {"scores": pick(data)}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--speaker", required=True, help="who recorded it and their accent — printed in the result")
    args = ap.parse_args()

    key = os.environ.get("SPEECHACE_API_KEY")
    if not key:
        print("SPEECHACE_API_KEY is not set. Nothing was called and nothing is reported.")
        return 2
    audio = open(args.audio, "rb").read()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"B2 — dialect experiment, {stamp}")
    print(f"audio: {args.audio}  ({len(audio)} bytes)")
    print(f"speaker: {args.speaker}\n")

    async with aiohttp.ClientSession() as session:
        print(f"1. Repeatability baseline — {BASELINE_CALLS} identical calls at fr-fr")
        base = [await call(session, key, audio, "fr-fr") for _ in range(BASELINE_CALLS)]
        errs = [b["error"] for b in base if "error" in b]
        if errs:
            print(f"   vendor refused: {errs[0]}")
            return 1
        keys = sorted({k for b in base for k in b["scores"]})
        noise: dict[str, float] = {}
        for k in keys:
            vals = [b["scores"][k] for b in base if isinstance(b["scores"].get(k), float)]
            if len(vals) < 2:
                continue
            noise[k] = max(vals) - min(vals)
            print(f"   {k:28} min {min(vals):7.2f}  max {max(vals):7.2f}  spread {noise[k]:6.2f}"
                  f"  sd {statistics.pstdev(vals):5.2f}")
        print()

        print("2. One call at each dialect — en-us is the CONTROL, not a third condition")
        per = {}
        for d in DIALECTS:
            r = await call(session, key, audio, d)
            if "error" in r:
                print(f"   {d}: vendor refused — {r['error']}")
                per[d] = None
                continue
            per[d] = r["scores"]
            print(f"   {d}: " + "  ".join(f"{k}={v}" for k, v in sorted(r["scores"].items())))
        print()

        print("3. Read against the noise floor")
        fr, ca, en = per.get("fr-fr"), per.get("fr-ca"), per.get("en-us")
        for label, a, b in (("fr-fr vs fr-ca", fr, ca), ("fr-fr vs en-us", fr, en)):
            if not a or not b:
                print(f"   {label}: not comparable, one side failed")
                continue
            verdicts = []
            for k in sorted(set(a) & set(b)):
                if not isinstance(a[k], float) or not isinstance(b[k], float):
                    continue
                diff = abs(a[k] - b[k])
                floor = noise.get(k, 0.0)
                verdicts.append(f"{k} Δ{diff:.2f} vs noise {floor:.2f} → "
                                + ("INSIDE the noise" if diff <= floor else "OUTSIDE"))
            print(f"   {label}:")
            for v in verdicts:
                print(f"      {v}")
        print()
        print("Reading it: a difference inside the noise floor is not a difference.")
        print("If fr-fr and en-us agree, the dialect parameter does nothing here.")
        print("If fr-fr and fr-ca agree, that is only readable as 'no difference'")
        print("when the audio actually contained Quebec phonology or vocabulary —")
        print(f"which depends entirely on: {args.speaker}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
