# Human-in-the-Loop Automated Research: Verification-Centered Scientific Discovery

**Working manuscript (Methodology)** — open for community feedback, verification checks, and iterative revision.

- **Latest PDF**: [`paper.pdf`](paper.pdf) (24 pages A4; also mirrored at [`main.pdf`](main.pdf) and [`output/pdf/research-lifecycle.pdf`](output/pdf/research-lifecycle.pdf))
- **LaTeX Source**: [`paper/main.tex`](paper/main.tex) and [`paper/references.bib`](paper/references.bib) (78 external references)
- **License**: Creative Commons Attribution 4.0 International ([`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt))
- **Suggest a Revision or Check**: [Open a GitHub Issue](https://github.com/mathesis-papers/human-in-the-loop-automated-research/issues/new/choose)

## Authors

Chloe Chew<sup>1</sup>, Abigail Deng<sup>1</sup>, Zongzhe Huang<sup>1</sup>, Louis Li<sup>1</sup>, Rona Liang<sup>1</sup>, Kai Huei Lim<sup>1</sup>, Kai Wei Lim<sup>1</sup>, Yitian Liu<sup>1</sup>, Haobo Ma<sup>1</sup>, Wen Niu<sup>1</sup>, Jianwei Su<sup>1</sup>, Calvin Tan<sup>1</sup>, Haylee Wang<sup>1</sup>, Jason Wang<sup>1</sup>, Shining Wang<sup>1</sup>, Wenlin Zhang<sup>1,2</sup>

<sup>1</sup>ChronoAI Pte Ltd, Singapore &nbsp;&nbsp; <sup>2</sup>National University of Singapore, Singapore  
*Authors are listed in alphabetical order by surname.*

## Overview

Scientific discovery is defined by the ability to recognize the boundaries of existing knowledge, decide which questions matter, and establish new truths that a scholarly community can inspect and build upon. As foundation models and neural theorem provers shift theoretical research from proof scarcity toward automated abundance, unguided autonomy breaks down from two opposite directions: locally plausible "scientific slop" on the informal side and opaque formal code ("proof indigestion") on the formal side.

This manuscript introduces a **verification-centered, human-in-the-loop methodology** for automated scientific discovery and evaluates it across mathematics, quantum information, mathematical physics, and theoretical computer science:

1. **Three-Family External Blinded Benchmark ($N=30$, 90 evaluations)**: Ten autonomous AI-only studies from ten distinct laboratories, ten contemporaneous specialist human-only arXiv preprints, and ten category-matched collaborative preprints scored blindly by **OpenAI Codex (`gpt-6.1-sol`)**, **Anthropic Claude (`claude-opus-5-5`)**, and **Google Gemini** (Kendall concordance $W = 0.828$). Collaborative preprints rank highest under every judge (260/300 cross-cohort wins over autonomous AI; exact permutation $p = 0.0012$, $0.0149$, and $3.2 \times 10^{-5}$), compress dispersion 2.3- to 4.2-fold against unverified human preprints, and include formal or certified checks in 10/10 papers versus 1/10 human preprints and 0/10 autonomous studies.
2. **Controlled 20-Claim Mechanistic Ablation**: On 10 real mathematical flaws and 10 matched valid theorems from the collaborative arXiv corpus, prose-only review produces 20%–30% false-positive "review slop" (including 20% correlated cross-family intersection false positives on newly solved open problems). Enforcing an independently executed counterexample verification gate reduces false positives from 30% to **0.0%** (precision **100.0%**, F1 **94.7%**, accuracy **95.0%**, Fisher exact $p = 0.000119$).
3. **Large-Scale Public Admission-Gate Audit**: Across **24,925** completed public Lean 4 pull requests (`the-omega-institute/trureturing`), 1,995 (8.0%) closed unmerged before admission, and across the most recent 1,000 consecutive PRs, **59.6%** of merged units required multi-commit repair under automated gates.
4. **Live Programme & 33-Hour Instrumented Trace**: 17 collaborative arXiv preprints (16 with external academic coauthors), 177 proof-checking living scholars, and a 33-hour trace recording 31 brief human directives guiding six kernel-verified Lean 4 units and 52 early refutations.

## Repository Layout

- `paper/` — Canonical LaTeX manuscript (`main.tex`, `references.bib`, generated tables and TikZ figures).
- `data/benchmark/` — Archived JSON records for all 90 three-family blind evaluations (`judge_codex_ext30.json`, `judge_claude_opus55_ext30.json`, `judge_gemini_ext30.json`, `ext_n30_summary.json`), longitudinal revisions (`benchmark_summary.json`), the 20-claim mechanistic ablation (`ablation_obligation_threshold.json` and 20 executable verification scripts in `arm4_scripts/`), and the 24,925-PR public gate audit (`exp3_trureturing_audit.json`).
- `data/collaborative-arxiv.json` — Version-pinned manifest of all 17 collaborative arXiv preprints.
- `scripts/` — Deterministic manuscript build and audit pipeline (`build_paper.py`, `render_benchmark.py`, `render_corpus.py`) plus archived selection, blinding, and scoring scripts (`scripts/benchmark/`).

## Reproducing the Manuscript and Checks

```bash
# Rebuild all tables, figures, and the audited 24-page PDF (requires XeLaTeX + BibTeX + Python 3)
TZ=UTC FORCE_SOURCE_DATE=1 python3 scripts/build_paper.py

# Re-run any individual executable counterexample witness from the 20-claim ablation
python3 data/benchmark/arm4_scripts/verify_ab_01.py
```

## Community Revisions and Versioned Publishing

This repository is the living collaborative source for the manuscript. Readers, referees, and collaborators are warmly invited to [open an Issue](https://github.com/mathesis-papers/human-in-the-loop-automated-research/issues/new/choose) to report typos, check proofs or statistics, suggest missing references, or propose follow-up ablations. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CHANGELOG.md`](CHANGELOG.md) for how accepted revisions are bundled into immutable tagged releases (`v1.0`, `v1.1`, ...) and published to Mathesis.

---

### 中文简介

本仓库为方法学工作稿《人在回路的自动化科研：以验证为中心的科学发现》的公开源码、实验数据与可复现脚本仓库。欢迎各界学者和合作者直接通过 [GitHub Issues](https://github.com/mathesis-papers/human-in-the-loop-automated-research/issues) 提出修改意见、数学/统计复核意见或补充实验建议；每次阶段性修订将以不可变版本标签（`v1.0`、`v1.1` 等）冻结发布并同步展示至 Mathesis 平台。
