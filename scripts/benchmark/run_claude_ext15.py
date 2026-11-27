#!/usr/bin/env python3
"""Run named Anthropic Claude (claude-opus-5-5) as an independent blind referee on ext_01..ext_15
(or any given blinded directory) using `claude -p` with tools disabled and zero ground-truth access."""
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

BLIND_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/benchmark/ext_bench/blinded")
OUT_PATH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/benchmark/ext_bench/judge_claude_opus55_ext15.json")
PREFIX = sys.argv[3] if len(sys.argv) > 3 else "ext_"

RUBRIC = """You are an independent, rigorous peer referee for a top-tier mathematics, theoretical computer science, and quantitative sciences journal.
Evaluate the anonymized research manuscript below purely on its scientific substance, mathematical/methodological rigor, calibration, verification grounding, significance, literature attribution, and exposition.
Do NOT guess author identities or origins, and do NOT penalize [TRUNCATED AT 36,000 CHARS ...] merely for being capped at the evaluation window; judge the arguments, proofs, methods, and evidence actually present.

Score on a 1.0 to 10.0 scale (one decimal place) across six criteria plus holistic overall:
- correctness_rigor: Logical soundness, explicit hypotheses, proof/derivation completeness, absence of algebraic/statistical/boundary gaps.
- claim_calibration: Proportion between stated claims and actually proved/demonstrated results; honesty about open cases, assumptions, and limitations.
- verification_grounding: Strength and independence of verification (machine-checked formal proofs, exact algebraic/rational/interval certificates, counterexamples, reproducible checks or analytical derivations rather than unverified assertions).
- novelty_significance: Depth and non-triviality of the research question, structural insight, and genuine contribution to an active external literature.
- literature_attribution: Accuracy, depth, and scholarly grounding in the relevant external research literature.
- clarity_exposition: Precision of definitions, notation, structure, and readability for a specialist reader.
- overall: Holistic scientific publication readiness and research value (not a mechanical average).

Return ONLY a single valid JSON object (no markdown fences, no commentary outside JSON) with keys:
{"correctness_rigor": 0.0, "claim_calibration": 0.0, "verification_grounding": 0.0, "novelty_significance": 0.0, "literature_attribution": 0.0, "clarity_exposition": 0.0, "overall": 0.0, "rationale": "2-3 concise sentences citing concrete strengths and weaknesses observed in the text."}
"""

files = sorted(BLIND_DIR.glob(f"{PREFIX}*.txt"))
print(f"Scoring {len(files)} blinded manuscripts with Claude CLI -> {OUT_PATH}", flush=True)

def score_one(path: Path):
    bid = path.stem
    text = path.read_text(encoding="utf-8", errors="replace")
    prompt = f"{RUBRIC}\n\n=== MANUSCRIPT {bid} ===\n{text}\n=== END MANUSCRIPT {bid} ==="
    cmd = [
        "claude", "-p",
        "--model", "claude-opus-5-5",
        "--output-format", "json",
        "--tools", "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--setting-sources", "user",
    ]
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=240, check=True)
    outer = json.loads(res.stdout)
    raw = outer.get("result", "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"Non-JSON response for {bid}: {raw[:300]}")
    parsed = json.loads(m.group(0))
    model_used = next(iter(outer.get("modelUsage", {}).keys()), "claude-opus-5-5")
    parsed["_model"] = model_used
    print(f"  done {bid}: overall={parsed['overall']} ({model_used})", flush=True)
    return bid, parsed

existing = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
todo = [p for p in files if p.stem not in existing]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    for bid, parsed in ex.map(score_one, todo):
        existing[bid] = parsed
        OUT_PATH.write_text(json.dumps(existing, indent=2))

print(f"Completed {len(existing)}/{len(files)} evaluations -> {OUT_PATH}", flush=True)
