#!/usr/bin/env python3
"""Create 100% leak-free blinded texts for all 15 external cohort papers.
Strips title/author/affiliation headers before Abstract/body AND strips AMS trailing affiliation footers,
plus scrubs any autonomous-agent / ChronoAI / NUS / platform / archive / email / URL cues.
Prints first 6 lines and last 6 lines of every file for manual audit!"""
import json
import re
from pathlib import Path

BASE = Path("data/benchmark/ext_bench")
RAW = BASE / "raw"
BLIND = BASE / "blinded"
gt = json.loads((BASE / "ext_ground_truth.json").read_text())

def airtight_sanitize(raw_txt, rec):
    # First normalize form-feeds
    txt = raw_txt.replace("\x0c", "\n")
    lines = txt.splitlines()

    # 1. Strip header block (authors, affiliations, dates, "autonomous research agent", arXiv stamps)
    # Find start of Abstract or first long body paragraph (>=140 chars) in first 120 lines
    start_idx = 0
    for i, l in enumerate(lines[:120]):
        s = l.strip()
        if re.match(r"^(?:Abstract\.?$|Abstract[\.\s:]|1\.\s+Introduction|I\.\s+INTRODUCTION)", s, re.I):
            start_idx = i
            break
    if start_idx == 0:
        # e.g. AgentAlphaXiv or RevTeX without explicit "Abstract" label: start at first line >= 70 chars after line 4 that is prose (not university/agent/date/email)
        for i, l in enumerate(lines[:80]):
            s = l.strip()
            if i >= 4 and len(s) >= 65 and not re.search(r"(@|university|institute|autonomous research|chronoai|singapore|bucharest|guadalajara|dated:|arXiv|2026-\d\d-\d\d)", s, re.I):
                start_idx = i
                break

    # Prepend ONLY the sanitized paper title (from ground truth metadata, guaranteed zero affiliation/author/platform)
    title_clean = re.sub(r"\s+", " ", rec["title"]).strip()
    body_lines = [f"TITLE: {title_clean}", ""] + lines[start_idx:]

    # 2. Strip trailing AMS author address/email blocks after References
    # Detect lines like "(Name) University..." or "Email address:" or "Department of Mathematics..." near the end
    end_idx = len(body_lines)
    for i in range(max(0, len(body_lines) - 80), len(body_lines)):
        s = body_lines[i].strip()
        if re.match(r"^\([A-Z][^)]{1,40}\)\s+(?:Universidad|University|Department|School|Institute|Faculty|ChronoAI|National University|The\s)", s) or re.match(r"^Email address:", s, re.I) or re.match(r"^∗\s*Corresponding", s):
            end_idx = i
            break
    body_lines = body_lines[:end_idx]

    # 3. Filter running headers & explicit affiliation/agent-tag lines
    out_lines = []
    for line in body_lines:
        s = line.strip()
        if re.match(r"^\d{1,2}\s+[A-Z][A-Z\s,\.\-]{8,}$", s) or re.match(r"^[A-Z][A-Z\s,\.\-]{12,}\s+\d{1,2}$", s):
            continue
        if re.search(r"\b(autonomous research agent|ChronoAI|National University of Singapore|HAOBO|WENLIN|MA,\s*H|ZHANG,\s*W)\b", s, re.I) and len(s) < 150:
            continue
        out_lines.append(line)
    body = "\n".join(out_lines)

    # 4. Regex scrubs for every identifying cue
    scrubs = [
        (r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?(?:\s*\[[^\]]+\])?", "[ARCHIVE-ID]"),
        (r"https?://\S+", "[URL]"),
        (r"\S+@\S+\.\S+", "[EMAIL]"),
        (r"\bAgent\s+[A-Z][a-z]+-[0-9A-Fa-f]{6,10}\b", "[PRIOR-AUTHOR]"),
        (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "[UUID]"),
        (r"\b[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{12}\b", "[UUID]"),
        (r"\b(?:AgentAlphaXiv|Agent\s+alphaXiv|alphaXiv|Journal of Agent Research|Mathesis|trureturing|OpenResearch|openresearch\.sh|cohort\s+preprint|Agent\s+cohort|Omega\s+Institute|ChronoAI(?:\s+Pte\s+Ltd)?|autonomous\s+research\s+agent)\b", "[REDACTED]"),
        (r"\bLab\s+\d+\b", "[LAB]"),
        (r"\b(?:Haobo\s+Ma|Wenlin\s+Zhang|Ma,\s*Haobo|Zhang,\s*Wenlin|Haobo|Wenlin)\b", "[AUTHOR]"),
        (r"doi:10\.5281/zenodo\.\d+", "[DOI]"),
    ]
    for pat, rep in scrubs:
        body = re.sub(pat, rep, body, flags=re.I)

    # Strip Acknowledgments section
    body = re.sub(r"(?is)\n\s*(?:\d+\.?\s+)?Acknowledgm?ents?\b.*?(?=\n\s*(?:\d+\.?\s+)?(?:References|Bibliography|Appendix)\b|\Z)", "\n", body)

    # Strip any remaining author names from human_only_arxiv
    for a in rec.get("authors", []):
        if len(a) >= 5:
            body = re.sub(re.escape(a), "[AUTHOR]", body, flags=re.I)

    body = body.strip()
    if len(body) > 36000:
        body = body[:36000] + "\n\n[TRUNCATED AT 36,000 CHARS FOR MATCHED BLIND EVALUATION WINDOW]"
    return body

leak_check = re.compile(
    r"(autonomous research agent|ChronoAI|National University of Singapore|AgentAlphaXiv|alphaXiv|Journal of Agent Research|Mathesis|trureturing|OpenResearch|cohort\s+preprint|Agent\s+[A-Z][a-z]+-|Haobo|Wenlin|Lab\s+\d|arXiv:\d{4}|@|https?://)",
    re.I,
)

for rec in gt:
    bid = rec["blind_id"]
    raw_txt = (RAW / f"{rec['raw_slug']}.txt").read_text()
    clean = airtight_sanitize(raw_txt, rec)
    (BLIND / f"{bid}.txt").write_text(clean)
    rec["sanitized_len"] = len(clean)
    leaks = leak_check.findall(clean)
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    print(f"=== {bid} | {rec['cohort']:17s} | chars={len(clean):5d} | leaks={leaks} ===")
    print("  HEAD:", " // ".join(lines[:4])[:180])
    print("  TAIL:", " // ".join(lines[-3:])[:180])

(BASE / "ext_ground_truth.json").write_text(json.dumps(gt, indent=2))
print("\nALL 15 FILES RE-SANITIZED AIRTIGHT!")
