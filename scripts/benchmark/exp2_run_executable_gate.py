#!/usr/bin/env python3
"""Track 2 (Arm 4 — Executable Verification-Target Obligation Gate):
For each blinded mathematical claim ab_01..ab_20, ask an independent coding agent
(OpenAI Codex gpt-6.1-sol) to write a self-contained Python 3 verification script that
tests the stated Proposition against explicit hypotheses and prints either:
  VERDICT: COUNTEREXAMPLE_VERIFIED   (only if an explicit witness satisfies ALL stated hypotheses and violates the conclusion)
  VERDICT: CONSISTENT_NO_COUNTEREXAMPLE  (if exhaustive/constructive tests all satisfy the proposition)
Then our harness independently executes each generated script in a fresh subprocess and records
the deterministic execution outcome. Zero ground-truth information is ever exposed."""
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path("data/benchmark/exp2_ablation")
BLIND = BASE / "blinded"
SCRIPTS = BASE / "arm4_scripts"
SCRIPTS.mkdir(parents=True, exist_ok=True)
OUT = BASE / "arm4_executable_gate.json"

PROMPT_TMPL = """You are an automated executable verification-target generator for mathematical peer review.
Read the blinded mathematical Proposition and proof sketch below.
Your task is to write a single, completely self-contained Python 3 script (using only Python standard library, plus numpy/scipy/sympy if helpful) that rigorously tests whether the stated Proposition is FALSE as stated by searching for an explicit counterexample, or testing it exhaustively/systematically on concrete instances.

STRICT OBLIGATION RULES:
1. Your script MUST verify that any candidate counterexample strictly satisfies EVERY hypothesis stated in the Proposition (e.g., positivity, normalization, Hermiticity, trace=1, parity, graph connectedness, odd prime distinctness, length bounds, etc.) using exact arithmetic (fractions/integers) or high-precision checks (tolerance >= 1e-6 for floating-point strict violations).
2. Your script must finish within 15 seconds.
3. If your script finds an explicit witness that satisfies ALL stated hypotheses AND clearly violates the stated conclusion, print the witness details and end with the exact final line:
VERDICT: COUNTEREXAMPLE_VERIFIED
4. Otherwise (if the proposition holds on all tested/exhaustive instances and no valid counterexample is constructed), print a short summary of the checks performed and end with the exact final line:
VERDICT: CONSISTENT_NO_COUNTEREXAMPLE
5. Do NOT run any shell commands yourself; simply output ONLY the Python 3 code inside a single ```python ... ``` fenced block.

=== BLINDED CLAIM {bid} ===
{claim_text}
=== END BLINDED CLAIM {bid} ===
"""

files = sorted(BLIND.glob("ab_*.txt"))
results = json.loads(OUT.read_text()) if OUT.exists() else {}

def run_one(path: Path):
    bid = path.stem
    script_path = SCRIPTS / f"verify_{bid}.py"
    out_msg = SCRIPTS / f"msg_{bid}.txt"
    prompt = PROMPT_TMPL.format(bid=bid, claim_text=path.read_text(encoding="utf-8"))
    cmd = [
        "codex", "exec",
        "-m", "gpt-6.1-sol",
        "-c", 'model_reasoning_effort="medium"',
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "-o", str(out_msg),
        "-",
    ]
    subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=240, check=True)
    raw = out_msg.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"```python\s*(.*?)```", raw, re.S)
    code = m.group(1).strip() if m else raw.strip()
    script_path.write_text(code + "\n", encoding="utf-8")
    out_msg.unlink(missing_ok=True)

    # Independent deterministic execution in a clean subprocess
    try:
        exec_res = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=30,
        )
        stdout = exec_res.stdout.strip()
        stderr = exec_res.stderr.strip()
        rc = exec_res.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "TIMEOUT (30s)", -1

    verdict = "VALID"
    gate_status = "NO_COUNTEREXAMPLE"
    if rc == 0 and re.search(r"(?m)^VERDICT:\s*COUNTEREXAMPLE_VERIFIED\s*$", stdout):
        verdict = "FLAWED"
        gate_status = "COUNTEREXAMPLE_VERIFIED"
    elif rc != 0:
        gate_status = f"EXEC_ERROR_{rc}"

    rec = {
        "verdict": verdict,
        "gate_status": gate_status,
        "returncode": rc,
        "script_path": str(script_path),
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-400:],
        "_model": "gpt-6.1-sol",
    }
    print(f"  [Arm 4 ExecGate] {bid}: {verdict} ({gate_status}, rc={rc})", flush=True)
    return bid, rec

todo = [p for p in files if p.stem not in results]
print(f"Launching Track 2 Arm 4 (Executable Verification-Target Gate) on {len(todo)}/{len(files)} claims...", flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    for bid, rec in ex.map(run_one, todo):
        results[bid] = rec
        OUT.write_text(json.dumps(results, indent=2))

print("Track 2 Arm 4 COMPLETE!", flush=True)
