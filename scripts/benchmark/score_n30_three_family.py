#!/usr/bin/env python3
"""Aggregate and rigorously analyze the N=30 (n=10 per cohort) three-family external benchmark:
- Judge 1: OpenAI Codex (gpt-6.1-sol, reasoning_effort=xhigh)
- Judge 2: Anthropic Claude (claude-opus-5-5)
- Judge 3: Google Gemini (isolated fresh blind referee)
Computes cohort means/SDs across all 6 axes + overall, exact two-sided permutation p-values
over all C(20,10) = 184,756 assignments, pairwise dominance, category-matched head-to-head
comparisons, pairwise Spearman rho, Kendall's W concordance, full-document structural counts,
and outlier sensitivity analysis."""
from collections import Counter
import itertools
import json
import statistics
from pathlib import Path
from scipy.stats import spearmanr, rankdata

ORIG = Path("data/benchmark/ext_bench")
N30 = Path("data/benchmark/ext_bench_n30")

AXES = [
    "correctness_rigor",
    "claim_calibration",
    "verification_grounding",
    "novelty_significance",
    "literature_attribution",
    "clarity_exposition",
    "overall",
]
COHORTS = ["autonomous_ai", "human_only_arxiv", "human_in_the_loop"]

gt15 = json.loads((ORIG / "ext_ground_truth.json").read_text())
gt_new15 = json.loads((N30 / "new15_ground_truth.json").read_text())
gt30 = gt15 + gt_new15
gt_by_id = {r["blind_id"]: r for r in gt30}

codex30 = {
    **json.loads((ORIG / "judge_codex_ext.json").read_text()),
    **json.loads((N30 / "judge_codex_ext16_30.json").read_text()),
}
claude30 = {
    **json.loads((ORIG / "judge_claude_opus55_ext15.json").read_text()),
    **json.loads((N30 / "judge_claude_opus55_ext16_30.json").read_text()),
}
gemini15 = {
    **json.loads((ORIG / "judge_gemini_batch1.json").read_text()),
    **json.loads((ORIG / "judge_gemini_batch2.json").read_text()),
    **json.loads((ORIG / "judge_gemini_batch3.json").read_text()),
}
(ORIG / "judge_gemini_ext15.json").write_text(json.dumps(gemini15, indent=2))
gemini30 = {
    **gemini15,
    **json.loads((N30 / "judge_gemini_ext16_30.json").read_text()),
}

JUDGES = {
    "codex_gpt61sol": {"label": "OpenAI Codex (gpt-6.1-sol)", "short": "Codex (gpt-6.1-sol)", "scores": codex30},
    "claude_opus55": {"label": "Anthropic Claude (claude-opus-5-5)", "short": "Claude (opus-5-5)", "scores": claude30},
    "google_gemini": {"label": "Google Gemini (blind referee)", "short": "Google Gemini", "scores": gemini30},
}

# Audited papers with explicit formal or certified mathematical verification
# (Lean 4 proofs, DRAT certificates, 192-bit Arb / rational / exact polynomial / exhaustive certificates)
FORMAL_VERIF_IDS = {
    # All 10 collaborative preprints
    "ext_04", "ext_05", "ext_08", "ext_09", "ext_12",
    "ext_18", "ext_19", "ext_23", "ext_28", "ext_30",
    # Human-only Lean 4 preprint (2611.00153v1)
    "ext_16",
}

structural = {}
for c in COHORTS:
    recs = [r for r in gt30 if r["cohort"] == c]
    pages = [r["struct"]["pages"] for r in recs]
    stmts = [r["struct"]["formal_statements"] for r in recs]
    proofs = [r["struct"]["proof_blocks"] for r in recs]
    fver_m = [r["struct"]["formal_verif_mentions"] for r in recs]
    refs = [r["struct"]["references_est"] for r in recs]
    fv_papers = sum(1 for r in recs if r["blind_id"] in FORMAL_VERIF_IDS)
    structural[c] = {
        "n": len(recs),
        "pages_mean": round(statistics.mean(pages), 1),
        "pages_median": round(statistics.median(pages), 1),
        "formal_statements_total": sum(stmts),
        "formal_statements_mean": round(statistics.mean(stmts), 1),
        "proof_blocks_total": sum(proofs),
        "proof_blocks_mean": round(statistics.mean(proofs), 1),
        "papers_with_formal_verif": fv_papers,
        "formal_verif_mentions_total": sum(fver_m),
        "references_median": int(round(statistics.median(refs))),
    }

print("=== Structural Summary (N=30, n=10 per cohort) ===")
for c in COHORTS:
    print(f"  {c:18s}: {structural[c]}")

# Category-matched 10 pairs (Human-only vs Collaborative)
MATCHED_PAIRS = [
    ("quant-ph", "ext_02", "ext_05"),  # 2610.21044v1 vs 2610.05623v2
    ("math.CO",  "ext_03", "ext_08"),  # 2610.21036v1 vs 2610.24059v1
    ("math.NT",  "ext_01", "ext_12"),  # 2610.21052v1 vs 2610.29608v1
    ("cs.IT",    "ext_11", "ext_09"),  # 2610.21068v1 vs 2611.01064v1
    ("math.GR",  "ext_14", "ext_04"),  # 2610.21600v2 vs 2610.20329v1
    ("cs.FL",    "ext_16", "ext_19"),  # 2611.00153v1 vs 2610.39941v2
    ("math.CO",  "ext_25", "ext_18"),  # 2611.00126v1 vs 2611.03956v1
    ("quant-ph", "ext_22", "ext_28"),  # 2611.00144v1 vs 2611.04568v1
    ("math.CO",  "ext_24", "ext_23"),  # 2611.00145v1 vs 2611.21657v1
    ("quant-ph", "ext_26", "ext_30"),  # 2611.00201v1 vs 2611.15431v1
]

def exact_perm_p(xs, ys):
    comb = list(xs) + list(ys)
    n, m = len(xs), len(ys)
    total = sum(comb)
    obs = abs(sum(xs) / n - sum(ys) / m)
    eps = 1e-12
    ge = cnt = 0
    for idxs in itertools.combinations(range(n + m), n):
        s1 = sum(comb[i] for i in idxs)
        if abs(s1 / n - (total - s1) / m) >= obs - eps:
            ge += 1
        cnt += 1
    return ge / cnt, cnt

def pairwise_wins(xs, ys):
    w = sum(1 for x in xs for y in ys if x > y)
    t = sum(1 for x in xs for y in ys if x == y)
    l = sum(1 for x in xs for y in ys if x < y)
    return w, t, l

bids = [f"ext_{i:02d}" for i in range(1, 31)]
jkeys = list(JUDGES.keys())
mat = [rankdata([JUDGES[j]["scores"][b]["overall"] for b in bids]) for j in jkeys]
k, N = len(jkeys), len(bids)
R_i = [sum(mat[j][i] for j in range(k)) for i in range(N)]
R_bar = k * (N + 1) / 2.0
S = sum((r - R_bar) ** 2 for r in R_i)
T_sum = sum((c**3 - c) for j in jkeys for c in Counter(JUDGES[j]["scores"][b]["overall"] for b in bids).values() if c > 1)
kendall_W = (12.0 * S) / (k**2 * (N**3 - N) - k * T_sum)

pair_rho = {}
for i in range(len(jkeys)):
    for j in range(i + 1, len(jkeys)):
        a = [JUDGES[jkeys[i]]["scores"][b]["overall"] for b in bids]
        b = [JUDGES[jkeys[j]]["scores"][b]["overall"] for b in bids]
        rho, pval = spearmanr(a, b)
        pair_rho[f"{jkeys[i]}__vs__{jkeys[j]}"] = {"rho": round(float(rho), 4), "p": float(pval)}

summary = {
    "n_total": 30,
    "n_per_cohort": 10,
    "total_evaluations": 90,
    "structural": structural,
    "agreement": {
        "pairwise_spearman": pair_rho,
        "kendall_W_3families_N30": round(float(kendall_W), 4),
    },
    "judges": {},
    "matched_pairs_10": [],
    "sensitivity_excl_fatal_human": {},
}

for cat, h_id, c_id in MATCHED_PAIRS:
    summary["matched_pairs_10"].append({
        "category": cat,
        "human_blind_id": h_id,
        "human_source_id": gt_by_id[h_id]["source_id"],
        "hitl_blind_id": c_id,
        "hitl_source_id": gt_by_id[c_id]["source_id"],
        "scores": {
            jk: {
                "human": JUDGES[jk]["scores"][h_id]["overall"],
                "hitl": JUDGES[jk]["scores"][c_id]["overall"],
            }
            for jk in jkeys
        },
    })

print("\n=== Category-Matched 10-Pair Head-to-Head (H+AI vs Human-only) ===")
for jk in jkeys:
    w = sum(1 for _, h, c in MATCHED_PAIRS if JUDGES[jk]["scores"][c]["overall"] > JUDGES[jk]["scores"][h]["overall"])
    t = sum(1 for _, h, c in MATCHED_PAIRS if JUDGES[jk]["scores"][c]["overall"] == JUDGES[jk]["scores"][h]["overall"])
    l = 10 - w - t
    print(f"  {jk:16s}: {w} wins, {t} ties, {l} losses")

for jk, jdata in JUDGES.items():
    by_cohort = {}
    for c in COHORTS:
        c_ids = [r["blind_id"] for r in gt30 if r["cohort"] == c]
        by_cohort[c] = {}
        for ax in AXES:
            vals = [jdata["scores"][b][ax] for b in c_ids]
            by_cohort[c][ax] = {
                "mean": round(statistics.mean(vals), 4),
                "sd": round(statistics.stdev(vals), 4),
                "median": round(statistics.median(vals), 4),
                "min": min(vals),
                "max": max(vals),
            }
    per_paper = [{
        "blind_id": r["blind_id"],
        "cohort": r["cohort"],
        "source_id": r["source_id"],
        "category": r.get("category", r.get("domain")),
        "scores": {ax: jdata["scores"][r["blind_id"]][ax] for ax in AXES},
        "rationale": jdata["scores"][r["blind_id"]].get("rationale", ""),
    } for r in gt30]
    hitl = [jdata["scores"][r["blind_id"]]["overall"] for r in gt30 if r["cohort"] == "human_in_the_loop"]
    ai = [jdata["scores"][r["blind_id"]]["overall"] for r in gt30 if r["cohort"] == "autonomous_ai"]
    hum = [jdata["scores"][r["blind_id"]]["overall"] for r in gt30 if r["cohort"] == "human_only_arxiv"]
    hum_clean = [jdata["scores"][r["blind_id"]]["overall"] for r in gt30 if r["cohort"] == "human_only_arxiv" and r["blind_id"] not in {"ext_02", "ext_24"}]
    p_ai, n_splits = exact_perm_p(hitl, ai)
    p_hum, _ = exact_perm_p(hitl, hum)
    w_ai, t_ai, l_ai = pairwise_wins(hitl, ai)
    w_hum, t_hum, l_hum = pairwise_wins(hitl, hum)
    sd_ratio = round(statistics.stdev(hum) / statistics.stdev(hitl), 2)
    print(f"  [{jk}] SD compression ratio (Human/H+AI) = {sd_ratio:.2f}x ({statistics.stdev(hum):.2f} vs {statistics.stdev(hitl):.2f})")

    summary["judges"][jk] = {
        "label": jdata["label"],
        "short": jdata["short"],
        "by_cohort": by_cohort,
        "per_paper": per_paper,
        "comparisons": {
            "hitl_vs_ai": {"mean_diff": round(statistics.mean(hitl)-statistics.mean(ai), 4), "wins": w_ai, "ties": t_ai, "losses": l_ai, "total_pairs": 100, "exact_perm_p": round(p_ai, 6), "perm_splits": n_splits},
            "hitl_vs_human": {"mean_diff": round(statistics.mean(hitl)-statistics.mean(hum), 4), "wins": w_hum, "ties": t_hum, "losses": l_hum, "total_pairs": 100, "exact_perm_p": round(p_hum, 6), "perm_splits": n_splits, "sd_compression_ratio": sd_ratio},
        },
    }
    summary["sensitivity_excl_fatal_human"][jk] = {
        "human_clean_n8_mean": round(statistics.mean(hum_clean), 4),
        "human_clean_n8_sd": round(statistics.stdev(hum_clean), 4),
        "hitl_n10_mean": round(statistics.mean(hitl), 4),
        "hitl_n10_sd": round(statistics.stdev(hitl), 4),
    }

(N30 / "ext_n30_summary.json").write_text(json.dumps(summary, indent=2))
(N30 / "ext_n30_ground_truth.json").write_text(json.dumps(gt30, indent=2))
(N30 / "judge_codex_ext30.json").write_text(json.dumps(codex30, indent=2))
(N30 / "judge_claude_opus55_ext30.json").write_text(json.dumps(claude30, indent=2))
(N30 / "judge_gemini_ext30.json").write_text(json.dumps(gemini30, indent=2))
print("Saved complete N=30 artifacts cleanly.")
