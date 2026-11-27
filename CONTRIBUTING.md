# Contributing & Opening Revision Issues

Thank you for reading *Human-in-the-Loop Automated Research: Verification-Centered Scientific Discovery*.

This repository follows an open, versioned manuscript workflow:

1. **Open an Issue**: Use one of the issue templates under [Issues → New Issue](https://github.com/mathesis-papers/human-in-the-loop-automated-research/issues/new/choose) to:
   - Flag typos, unclear exposition, or citation/attribution gaps (`Revision Request`);
   - Report a mathematical, statistical, or benchmark verification check (`Mathematical / Statistical Check`);
   - Propose an additional ablation, external comparator, or methodological extension (`Experiment Suggestion`).
2. **Pull Requests**: Direct edits to `paper/main.tex`, `paper/references.bib`, or `scripts/` are welcome. Please run `TZ=UTC FORCE_SOURCE_DATE=1 python3 scripts/build_paper.py` before opening a PR to verify zero LaTeX/BibTeX warnings, zero overfull/underfull boxes, and intact citation/audit checks.
3. **Versioned Releases**: Substantive revisions addressing community issues are periodically frozen into immutable semantic release tags (`v1.0`, `v1.1`, ...), documented in [`CHANGELOG.md`](CHANGELOG.md), and published as sequential versions on Mathesis with links back to the resolved GitHub issues.
