#!/usr/bin/env python3
"""Run OpenAI Codex (gpt-6.1-sol, xhigh) and Anthropic Claude (claude-opus-5-5) in parallel
as independent blind referees on ext_16..ext_30 under the exact same rubric used for ext_01..ext_15."""
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

BASE = Path("data/benchmark/ext_bench_n30")
BLIND_DIR = BASE / "blinded"

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
{"correctness_rigor": 0.0, "claim_calibration": 0.0, "verification_grounding": 0.0, "novelty_significance": 0.0, "literature_attribution": 0.0, "clarity_exposition": 0.0, "overall": 0.0, "rationale": "2-3 concise English sentences citing concrete strengths and weaknesses observed in the text."}
"""

files = [BLIND_DIR / f"ext_{i:02d}.txt" for i in range(16, 31)]
codex_out = BASE / "judge_codex_ext16_30.json"
claude_out = BASE / "judge_claude_opus55_ext16_30.json"
res_codex = json.loads(codex_out.read_text()) if codex_out.exists() else {}
res_claude = json.loads(claude_out.read_text()) if claude_out.exists() else {}

def score_codex(path: Path):
    bid = path.stem
    out_msg = BASE / f"tmp_codex_{bid}.txt"
    text = path.read_text(encoding="utf-8", errors="replace")
    prompt = (
        f"{RUBRIC}\n\n"
        "IMPORTANT: Do NOT invoke shell commands or file tools; evaluate strictly from the manuscript text below.\n\n"
        f"=== MANUSCRIPT {bid} ===\n{text}\n=== END MANUSCRIPT {bid} ==="
    )
    cmd = [
        "codex", "exec",
        "-m", "gpt-6.1-sol",
        "-c", 'model_reasoning_effort="xhigh"',
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "-o", str(out_msg),
        "-",
    ]
    subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=360, check=True)
    raw = out_msg.read_text(encoding="utf-8", errors="replace").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"Non-JSON Codex response for {bid}: {raw[:300]}")
    parsed = json.loads(m.group(0))
    parsed["_model"] = "gpt-6.1-sol"
    out_msg.unlink(missing_ok=True)
    print(f"  [Codex  gpt-6.1-sol]    {bid}: overall={parsed['overall']}", flush=True)
    return bid, parsed

def score_claude(path: Path):
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
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300, check=True)
    outer = json.loads(res.stdout)
    raw = outer.get("result", "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"Non-JSON Claude response for {bid}: {raw[:300]}")
    parsed = json.loads(m.group(0))
    parsed["_model"] = next(iter(outer.get("modelUsage", {}).keys()), "claude-opus-5-5")
    print(f"  [Claude claude-opus-5-5] {bid}: overall={parsed['overall']}", flush=True)
    return bid, parsed

def run_codex_all():
    todo = [p for p in files if p.stem not in res_codex]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for bid, parsed in ex.map(score_codex, todo):
            res_codex[bid] = parsed
            codex_out.write_text(json.dumps(res_codex, indent=2))

def run_claude_all():
    todo = [p for p in files if p.stem not in res_claude]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for bid, parsed in ex.map(score_claude, todo):
            res_claude[bid] = parsed
            claude_out.write_text(json.dumps(res_claude, indent=2))

print("Scoring ext_16..ext_30 with Codex (gpt-6.1-sol) and Claude (claude-opus-5-5) in parallel...", flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as top:
    f1 = top.submit(run_codex_all)
    f2 = top.submit(run_claude_all)
    f1.result()
    f2.result()

print("Completed ext_16..ext_30 for BOTH Codex and Claude!", flush=True)
