#!/usr/bin/env python3
"""Track 2: Run Arm 1 (Anthropic claude-opus-5-5 prose-only) and Arm 2 (OpenAI Codex gpt-6.1-sol
prose-only, no code execution) in parallel on all 20 blinded mathematical claims ab_01..ab_20."""
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

BASE = Path("data/benchmark/exp2_ablation")
BLIND = BASE / "blinded"

PROSE_PROMPT = """You are a strict mathematical referee evaluating a single self-contained mathematical proposition and proof sketch.
Do NOT run any code or external tools; evaluate purely by careful mathematical reading (standard prose peer review).
Decide whether the stated Proposition is mathematically VALID as stated (true under all stated hypotheses, with a sound or essentially sound argument) or FLAWED (false as stated, e.g., admits a counterexample, wrong constant/factor, or missing essential hypothesis that breaks the theorem).

Return ONLY a single valid JSON object (no markdown fences, no prose outside JSON):
{
  "verdict": "VALID" or "FLAWED",
  "confidence": 0.0 to 1.0,
  "objection": "If FLAWED, give a concise 2-3 sentence technical explanation of the exact flaw or counterexample; if VALID, give a 1-sentence confirmation."
}
"""

files = sorted(BLIND.glob("ab_*.txt"))

def run_claude_prose(path: Path):
    bid = path.stem
    prompt = f"{PROSE_PROMPT}\n\n{path.read_text()}"
    cmd = [
        "claude", "-p",
        "--model", "claude-opus-5-5",
        "--output-format", "json",
        "--tools", "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--setting-sources", "user",
    ]
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=360, check=True)
    outer = json.loads(res.stdout)
    raw = outer.get("result", "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    parsed = json.loads(m.group(0))
    parsed["_model"] = next(iter(outer.get("modelUsage", {}).keys()), "claude-opus-5-5")
    print(f"  [Claude prose] {bid}: {parsed['verdict']} (conf={parsed.get('confidence')})", flush=True)
    return bid, parsed

def run_codex_prose(path: Path):
    bid = path.stem
    out_msg = BASE / f"tmp_codex_prose_{bid}.txt"
    prompt = (
        f"{PROSE_PROMPT}\n\n"
        "IMPORTANT: Do NOT invoke shell commands, python, or any file tools. Answer strictly from mathematical reading.\n\n"
        f"{path.read_text()}"
    )
    cmd = [
        "codex", "exec",
        "-m", "gpt-6.1-sol",
        "-c", 'model_reasoning_effort="medium"',
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "-o", str(out_msg),
        "-",
    ]
    subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180, check=True)
    raw = out_msg.read_text(encoding="utf-8", errors="replace").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    parsed = json.loads(m.group(0))
    parsed["_model"] = "gpt-6.1-sol"
    out_msg.unlink(missing_ok=True)
    print(f"  [Codex prose]  {bid}: {parsed['verdict']} (conf={parsed.get('confidence')})", flush=True)
    return bid, parsed

claude_out = BASE / "arm1_claude_prose.json"
codex_out = BASE / "arm2_codex_prose.json"
res_claude = json.loads(claude_out.read_text()) if claude_out.exists() else {}
res_codex = json.loads(codex_out.read_text()) if codex_out.exists() else {}

def run_all_claude():
    todo = [p for p in files if p.stem not in res_claude]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for bid, parsed in ex.map(run_claude_prose, todo):
            res_claude[bid] = parsed
            claude_out.write_text(json.dumps(res_claude, indent=2))

def run_all_codex():
    todo = [p for p in files if p.stem not in res_codex]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for bid, parsed in ex.map(run_codex_prose, todo):
            res_codex[bid] = parsed
            codex_out.write_text(json.dumps(res_codex, indent=2))

print(f"Launching Track 2 prose review arms across {len(files)} claims (Claude + Codex in parallel)...", flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as top:
    f1 = top.submit(run_all_claude)
    f2 = top.submit(run_all_codex)
    f1.result()
    f2.result()

print("Track 2 prose arms COMPLETE!", flush=True)
