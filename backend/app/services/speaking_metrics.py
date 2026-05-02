from typing import List, Dict, Any, Tuple
import re


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z']+", text.lower())
    return tokens


def compute_alignment(reference: str, hypothesis: str) -> Dict[str, int]:
    ref = _tokenize(reference)
    hyp = _tokenize(hypothesis)

    # Levenshtein alignment counts
    m, n = len(ref), len(hyp)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost,
            )

    # Backtrack to count types
    i, j = m, n
    subs = ins = dels = correct = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] and ref[i - 1] == hyp[j - 1]:
            correct += 1
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            subs += 1
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            ins += 1
            j -= 1
        else:
            dels += 1
            i -= 1

    wer = (subs + ins + dels) / max(1, m)
    return {
        "wer": wer,
        "correct": correct,
        "insertions": ins,
        "deletions": dels,
        "substitutions": subs,
    }


def compute_fluency(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    # expects each word entry: {word, startMs, endMs}
    if not words:
        return {"wpm": 0.0, "avgPauseMs": None, "longPauses": []}

    # words per minute based on total duration
    start = next((w.get("startMs") for w in words if w.get("startMs") is not None), None)
    end = next((w.get("endMs") for w in reversed(words) if w.get("endMs") is not None), None)
    if start is None or end is None or end <= start:
        duration_min = 1.0 / 60.0
    else:
        duration_min = (end - start) / 60000.0

    wpm = len(words) / max(1e-6, duration_min)

    # pauses between words (>300ms considered long)
    pauses = []
    total_pause = 0
    count_pause = 0
    for i in range(1, len(words)):
        prev_end = words[i - 1].get("endMs")
        curr_start = words[i].get("startMs")
        if prev_end is not None and curr_start is not None and curr_start > prev_end:
            gap = curr_start - prev_end
            total_pause += gap
            count_pause += 1
            if gap >= 300:
                pauses.append({"start": int(prev_end), "end": int(curr_start)})

    avg_pause = (total_pause / count_pause) if count_pause > 0 else None
    return {"wpm": float(wpm), "avgPauseMs": avg_pause, "longPauses": pauses}



