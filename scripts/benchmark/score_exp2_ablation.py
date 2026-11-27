#!/usr/bin/env python3
"""Score Track 2: Controlled 20-claim causal ablation of prose review vs executable
verification-target obligation gate (Sun et al., Nature Machine Intelligence 2026)."""
import json
from pathlib import Path
from scipy.stats import fisher_exact

BASE = Path("data/benchmark/exp2_ablation")
gt_rows = json.loads((BASE / "ablation20_ground_truth.json").read_text())
gt = {r["blind_id"]: r["ground_truth"] for r in gt_rows}
gt_meta = {r["blind_id"]: r for r in gt_rows}

arm1 = json.loads((BASE / "arm1_claude_prose.json").read_text())
arm2 = json.loads((BASE / "arm2_codex_prose.json").read_text())
arm4 = json.loads((BASE / "arm4_executable_gate.json").read_text())

bids = sorted(gt.keys())
assert len(arm1) == 20 and len(arm2) == 20 and len(arm4) == 20, f"Counts: {len(arm1)}, {len(arm2)}, {len(arm4)}"

# Define 5 exact arms:
# 1. Claude prose-only (claude-opus-5-5)
# 2. Codex prose-only (gpt-6.1-sol)
# 3. Cross-family prose union (flagged by Claude OR Codex)
# 4. Cross-family prose intersection (flagged by BOTH Claude AND Codex)
# 5. Executable verification-target obligation gate (standalone Arm 4)
# 6. Prose union -> Executable obligation gate (Arm 3 AND Arm 4)

arms = {
    "arm1_claude_prose": {b: arm1[b]["verdict"] for b in bids},
    "arm2_codex_prose": {b: arm2[b]["verdict"] for b in bids},
    "arm3_prose_union": {b: ("FLAWED" if arm1[b]["verdict"] == "FLAWED" or arm2[b]["verdict"] == "FLAWED" else "VALID") for b in bids},
    "arm3b_prose_intersection": {b: ("FLAWED" if arm1[b]["verdict"] == "FLAWED" and arm2[b]["verdict"] == "FLAWED" else "VALID") for b in bids},
    "arm4_exec_gate_standalone": {b: arm4[b]["verdict"] for b in bids},
    "arm5_prose_union_plus_exec_gate": {
        b: ("FLAWED" if (arm1[b]["verdict"] == "FLAWED" or arm2[b]["verdict"] == "FLAWED") and arm4[b]["verdict"] == "FLAWED" else "VALID")
        for b in bids
    },
}

def eval_arm(preds):
    tp = sum(1 for b in bids if gt[b] == "FLAWED" and preds[b] == "FLAWED")
    fn = sum(1 for b in bids if gt[b] == "FLAWED" and preds[b] == "VALID")
    fp = sum(1 for b in bids if gt[b] == "VALID" and preds[b] == "FLAWED")
    tn = sum(1 for b in bids if gt[b] == "VALID" and preds[b] == "VALID")
    recall = tp / (tp + fn)
    fpr = fp / (fp + tn)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0
    acc = (tp + tn) / len(bids)
    _, p_fisher = fisher_exact([[tp, fp], [fn, tn]], alternative="two-sided")
    return {
        "TP": tp, "FN": fn, "FP": fp, "TN": tn,
        "recall_pct": round(100 * recall, 1),
        "fpr_slop_pct": round(100 * fpr, 1),
        "precision_pct": round(100 * prec, 1),
        "f1_pct": round(100 * f1, 1),
        "accuracy_pct": round(100 * acc, 1),
        "fisher_exact_p": round(float(p_fisher), 6),
    }

summary = {"n_total": 20, "n_flawed": 10, "n_valid": 10, "arms": {}, "per_claim": []}
print("=== Track 2: 20-Claim Mechanistic Ablation (10 Real Flawed + 10 Matched Valid) ===")
for name, preds in arms.items():
    m = eval_arm(preds)
    summary["arms"][name] = m
    print(f"  {name:32s} | TP={m['TP']:2d}/10 FP={m['FP']:2d}/10 | Rec={m['recall_pct']:5.1f}% FPR(Slop)={m['fpr_slop_pct']:5.1f}% Prec={m['precision_pct']:5.1f}% F1={m['f1_pct']:5.1f}% Acc={m['accuracy_pct']:5.1f}% p={m['fisher_exact_p']:.6f}")

print("\n=== Per-Claim Breakdown ===")
for b in bids:
    row = {
        "blind_id": b,
        "item_id": gt_meta[b]["orig_id"],
        "source_arxiv": gt_meta[b]["source_arxiv"],
        "ground_truth": gt[b],
        "claude_prose": arm1[b]["verdict"],
        "codex_prose": arm2[b]["verdict"],
        "exec_gate": arm4[b]["verdict"],
        "exec_gate_status": arm4[b]["gate_status"],
    }
    summary["per_claim"].append(row)
    flag_note = ""
    if gt[b] == "VALID" and (arm1[b]["verdict"] == "FLAWED" or arm2[b]["verdict"] == "FLAWED"):
        flag_note = " <-- PROSE FALSE POSITIVE (SLOP)"
    elif gt[b] == "FLAWED" and arm4[b]["verdict"] == "VALID":
        flag_note = f" <-- EXEC MISS ({arm4[b]['gate_status']})"
    print(f"  {b} ({gt_meta[b]['orig_id']:26s} | GT={gt[b]:6s}) | Claude={arm1[b]['verdict']:6s} | Codex={arm2[b]['verdict']:6s} | ExecGate={arm4[b]['verdict']:6s} ({arm4[b]['gate_status']}){flag_note}")

(BASE / "ablation_obligation_threshold.json").write_text(json.dumps(summary, indent=2))
print(f"\nSaved -> {BASE / 'ablation_obligation_threshold.json'}")
