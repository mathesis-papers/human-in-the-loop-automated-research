#!/usr/bin/env python3
"""Assemble a 15-paper 3-cohort external benchmark:
  Cohort 1 (n=5): Autonomous AI-Only papers from alphaXiv/AgentAlphaXiv (in_paper_cohort==True, top math/theory/formal studies across distinct labs)
  Cohort 2 (n=5): Matched Contemporaneous Human-Only arXiv preprints (Oct 2026, exact 5 subject classes: quant-ph, math.CO, math.NT, cs.IT, math.GR)
  Cohort 3 (n=5): Human-in-the-Loop Collaborative arXiv preprints (our 5 matched Oct 2026 preprints across those exact 5 subject classes)
Also verifies full abstracts of arXiv:2606.19749v1 & 2604.19502v2 and searches for paperreview.ai citations.
"""
import hashlib
import json
import random
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path("data/benchmark/ext_bench")
RAW = BASE / "raw"
BLIND = BASE / "blinded"
RAW.mkdir(parents=True, exist_ok=True)
BLIND.mkdir(parents=True, exist_ok=True)

def fetch_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "research-benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_json(url, timeout=40):
    return json.loads(fetch_bytes(url, timeout=timeout).decode("utf-8", errors="replace"))

print("=== 0. Verify review-benchmark abstracts & Stanford Agentic Reviewer citations ===")
ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
xml_rev = fetch_bytes("https://export.arxiv.org/api/query?id_list=2606.19749,2604.19502&max_results=5").decode("utf-8", errors="replace")
rev_meta = []
for e in ET.fromstring(xml_rev).findall("a:entry", ns):
    aid = e.findtext("a:id", "", ns).split("/abs/")[-1]
    rev_meta.append({
        "id": aid,
        "title": " ".join(e.findtext("a:title", "", ns).split()),
        "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
        "published": e.findtext("a:published", "", ns)[:10],
        "abstract": " ".join(e.findtext("a:summary", "", ns).split()),
    })
(BASE / "review_papers_verified.json").write_text(json.dumps(rev_meta, indent=2))
for m in rev_meta:
    print(f"  {m['id']} ({m['published']}): {m['title']}\n    {m['abstract']}\n")

print("=== 1. Fetch all AgentAlphaXiv studies via Hugging Face Datasets Server ===")
all_studies = []
for offset in range(0, 1000, 100):
    url = f"https://datasets-server.huggingface.co/rows?dataset=alphaXiv/AgentAlphaXiv&config=studies&split=train&offset={offset}&length=100"
    try:
        j = fetch_json(url)
        rows = [r["row"] for r in j.get("rows", [])]
        if not rows:
            break
        all_studies.extend(rows)
        if len(rows) < 100:
            break
    except Exception as ex:
        print(f"  offset {offset} error:", ex)
        break
print(f"Loaded {len(all_studies)} AgentAlphaXiv studies.")
if all_studies:
    print("Sample keys:", list(all_studies[0].keys()))

# Deterministic selection of 5 distinct-lab math/theory/formal-adjacent studies from in_paper_cohort==True
math_pat = re.compile(
    r"\b(theorem|proof|lemma|proves|proved|bound|bounds|inequality|combinator\w*|graph|quantum|number theory|prime|conjecture|formal|lean|algorithm|complexity|entropy|algebra|topology|geometry|spectral|matrix|eigenvalue|operator)\b",
    re.I,
)
in_cohort = [s for s in all_studies if s.get("in_paper_cohort")]
print("in_paper_cohort count:", len(in_cohort))
candidates = []
for s in in_cohort:
    txt = f"{s.get('title','')} {s.get('abstract','')}"
    hits = sorted(set(m.group(0).lower() for m in math_pat.finditer(txt)))
    pid = s.get("project_id") or s.get("id")
    lab = s.get("lab") or s.get("lab_id") or "unknown"
    vnum = s.get("latest_version_number") or s.get("version_count") or 1
    candidates.append((len(hits), int(vnum or 1), str(pid), str(lab), s.get("title", ""), hits))
candidates.sort(key=lambda x: (-x[0], -x[1], x[2]))

selected_agent = []
used_labs = set()
for c in candidates:
    if len(selected_agent) >= 5:
        break
    # Ensure distinct labs so we don't over-sample Lab 1!
    if c[3] in used_labs:
        continue
    used_labs.add(c[3])
    selected_agent.append({
        "cohort": "autonomous_ai",
        "source_id": f"AgentAlphaXiv:{c[2][:12]}",
        "project_id": c[2],
        "lab": c[3],
        "domain": "Autonomous AI (Math/Theory)",
        "title": c[4],
        "pdf_url": f"https://huggingface.co/datasets/alphaXiv/AgentAlphaXiv/resolve/main/papers/{c[2]}.pdf",
        "math_term_hits": c[0],
        "versions": c[1],
    })
print("\nSelected 5 Autonomous AI (AgentAlphaXiv) papers (distinct labs, deterministic math-keyword rank):")
for item in selected_agent:
    print(f"  {item['source_id']} | lab={item['lab']} | hits={item['math_term_hits']} | {item['title'][:72]}")

print("\n=== 2. Select 5 Matched Human-in-the-Loop Collaborative arXiv Preprints ===")
hitl_targets = [
    ("2610.05623v2", "quant-ph", "Quantum Information"),
    ("2610.24059v1", "math.CO", "Graph Theory & Combinatorics"),
    ("2610.29608v1", "math.NT", "Number Theory"),
    ("2611.01064v1", "cs.IT", "Information Theory"),
    ("2610.20329v1", "math.GR", "Group Theory & Cellular Automata"),
]
selected_hitl = []
for aid, cat, dom in hitl_targets:
    xml_h = fetch_bytes(f"https://export.arxiv.org/api/query?id_list={aid}").decode("utf-8", errors="replace")
    e = ET.fromstring(xml_h).find("a:entry", ns)
    title = " ".join(e.findtext("a:title", "", ns).split()) if e is not None else aid
    selected_hitl.append({
        "cohort": "human_in_the_loop",
        "source_id": f"arXiv:{aid}",
        "arxiv_id": aid,
        "category": cat,
        "domain": dom,
        "title": title,
        "pdf_url": f"https://arxiv.org/pdf/{aid}.pdf",
    })
    print(f"  HITL {aid} ({cat}): {title[:70]}")

print("\n=== 3. Deterministically Select 5 Matched Contemporaneous Human-Only arXiv Preprints ===")
# Load our 17 arXiv IDs to guarantee zero overlap
our_ids = set(p["arxiv_id"] for p in json.loads(Path("./data/collaborative-arxiv.json").read_text())["papers"])
selected_human = []
for aid, cat, dom in hitl_targets:
    # Deterministic query: Oct 2026 submissions in exact same primary category, submittedDate ascending from 2026-10-15 to 2026-10-31
    q = urllib.parse.quote(f"cat:{cat} AND submittedDate:[202610150000 TO 202610312359]")
    url = f"https://export.arxiv.org/api/query?search_query={q}&start=0&max_results=20&sortBy=submittedDate&sortOrder=ascending"
    xml_c = fetch_bytes(url).decode("utf-8", errors="replace")
    picked = None
    for e in ET.fromstring(xml_c).findall("a:entry", ns):
        full_id = e.findtext("a:id", "", ns).split("/abs/")[-1]
        base_id = full_id.split("v")[0]
        if base_id in our_ids:
            continue
        pcat_el = e.find("arxiv:primary_category", ns)
        pcat = pcat_el.attrib.get("term", "") if pcat_el is not None else ""
        if pcat != cat:
            continue
        title = " ".join(e.findtext("a:title", "", ns).split())
        # Skip errata / comments / surveys
        if re.search(r"\b(erratum|corrigendum|comment on|reply to|survey|review of)\b", title, re.I):
            continue
        auths = [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)]
        if any("Ma" in a and "Haobo" in a for a in auths) or any("Zhang" in a and "Wenlin" in a for a in auths):
            continue
        picked = {
            "cohort": "human_only_arxiv",
            "source_id": f"arXiv:{full_id}",
            "arxiv_id": full_id,
            "category": cat,
            "domain": dom,
            "title": title,
            "authors": auths,
            "pdf_url": f"https://arxiv.org/pdf/{full_id}.pdf",
        }
        break
    if not picked:
        raise RuntimeError(f"No matched human arXiv paper found for {cat}")
    selected_human.append(picked)
    print(f"  HUMAN {picked['arxiv_id']} ({cat}): {picked['title'][:70]}")
    time.sleep(0.5)

all_15 = selected_agent + selected_human + selected_hitl
print(f"\n=== 4. Downloading all {len(all_15)} PDFs, extracting text, computing deterministic structural metrics ===")

def struct_metrics(txt, pages):
    words = len(re.findall(r"\b\w+\b", txt))
    stmts = len(re.findall(r"(?im)^\s*(?:Theorem|Lemma|Proposition|Corollary)\s+\d+", txt))
    proofs = len(re.findall(r"(?im)^\s*Proof[\.\s:]", txt))
    cex = len(re.findall(r"\b(?:counterexample|refut\w*|disprov\w*)\b", txt, re.I))
    formal = len(re.findall(r"\b(?:Lean\s*4?|Mathlib|DRAT|Coq|Isabelle|machine-checked|formaliz\w*|Arb\s+enclos\w*|interval\s+arithmetic|certified)\b", txt, re.I))
    # Estimate reference count from References / Bibliography section
    ref_m = re.search(r"(?im)^\s*(?:\d+\.?\s+)?(?:References|Bibliography)\s*$", txt)
    refs_est = 0
    if ref_m:
        tail = txt[ref_m.end():]
        bracket_refs = len(re.findall(r"(?m)^\s*\[\d+\]", tail))
        num_refs = len(re.findall(r"(?m)^\s*\d+\.\s+[A-Z]", tail))
        refs_est = max(bracket_refs, num_refs)
        if refs_est == 0:
            # fallback author-year lines
            refs_est = len(re.findall(r"(?m)^[A-Z][a-zA-Z\-]+,\s+[A-Z]\.", tail))
    return {
        "pages": pages,
        "words": words,
        "formal_statements": stmts,
        "proof_blocks": proofs,
        "counterexample_mentions": cex,
        "formal_verif_mentions": formal,
        "references_est": refs_est,
    }

def sanitize_blind(txt):
    # Strip identifying headers, arXiv stamps, emails, URLs, platform names, acks, author blocks before Abstract
    lines = txt.splitlines()
    # Keep title (first non-empty chunk) + start cleanly from Abstract if found within first 120 lines
    abs_idx = None
    for i, l in enumerate(lines[:140]):
        if re.match(r"^\s*abstract\b", l, re.I):
            abs_idx = i
            break
    if abs_idx is not None and abs_idx > 2:
        # Preserve only likely title lines (before authors/affiliations) -> actually safer: start AT Abstract or keep clean title?
        # Even cleaner: keep title line(s) only if no email/university/Lab/Agent, else start at Abstract!
        head = []
        for l in lines[:min(abs_idx, 5)]:
            if re.search(r"(@|university|institute|lab\s*\d|agent|alphaxiv|arxiv|orcid|department|preprint|november|october|september|2026)", l, re.I):
                break
            if l.strip():
                head.append(l.strip())
        body = "\n".join(head + [""] + lines[abs_idx:])
    else:
        body = txt
    # Scrub arXiv stamps, AgentAlphaXiv, JAR, Mathesis, trureturing, github links, emails, dates
    body = re.sub(r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?(?:\s*\[[^\]]+\])?", "[ARCHIVE-ID]", body, flags=re.I)
    body = re.sub(r"https?://\S+", "[URL]", body)
    body = re.sub(r"\S+@\S+\.\S+", "[EMAIL]", body)
    body = re.sub(r"\b(?:AgentAlphaXiv|alphaXiv|Journal of Agent Research|Mathesis|trureturing|OpenResearch|Omega Institute)\b", "[PLATFORM]", body, flags=re.I)
    body = re.sub(r"\bLab\s+\d+\b", "[LAB]", body)
    # Strip Acknowledgments section if present before References
    body = re.sub(r"(?is)\n\s*(?:\d+\.?\s+)?Acknowledgm?ents?\b.*?(?=\n\s*(?:\d+\.?\s+)?(?:References|Bibliography|Appendix)\b|\Z)", "\n", body)
    # Match 36,000-char window
    body = body.strip()
    if len(body) > 36000:
        body = body[:36000] + "\n\n[TRUNCATED AT 36,000 CHARS FOR MATCHED BLIND EVALUATION WINDOW]"
    return body

records = []
for idx, item in enumerate(all_15, 1):
    slug = f"{item['cohort']}_{idx:02d}"
    pdf_path = RAW / f"{slug}.pdf"
    if not pdf_path.exists() or pdf_path.stat().st_size < 5000:
        print(f"  Downloading {item['source_id']} ...")
        pdf_path.write_bytes(fetch_bytes(item["pdf_url"], timeout=60))
        time.sleep(0.4)
    # Page count via pdfinfo
    pinfo = subprocess.check_output(["pdfinfo", str(pdf_path)], text=True, errors="replace")
    m_pg = re.search(r"Pages:\s+(\d+)", pinfo)
    pages = int(m_pg.group(1)) if m_pg else None
    txt = subprocess.check_output(["pdftotext", str(pdf_path), "-"], text=True, errors="replace")
    (RAW / f"{slug}.txt").write_text(txt)
    sm = struct_metrics(txt, pages)
    sanitized = sanitize_blind(txt)
    rec = dict(item)
    rec["raw_slug"] = slug
    rec["pdf_sha256_16"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:16]
    rec["struct"] = sm
    rec["sanitized_len"] = len(sanitized)
    records.append((rec, sanitized))
    print(f"  [{item['cohort']:18s}] {item['source_id']:24s} | pp={pages} w={sm['words']} thm={sm['formal_statements']} pf={sm['proof_blocks']} refs={sm['references_est']} formal={sm['formal_verif_mentions']} blind_chars={len(sanitized)}")

# Deterministically shuffle into blind IDs ext_01 .. ext_15 (seed 20261127)
rng = random.Random(20261127)
order = list(range(len(records)))
rng.shuffle(order)

ground_truth = []
for blind_num, orig_idx in enumerate(order, 1):
    rec, sanitized = records[orig_idx]
    bid = f"ext_{blind_num:02d}"
    (BLIND / f"{bid}.txt").write_text(sanitized)
    rec["blind_id"] = bid
    ground_truth.append(rec)

(BASE / "ext_ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
print(f"\nWrote {len(ground_truth)} blinded external manuscripts to {BLIND} and ground truth to {BASE / 'ext_ground_truth.json'}")
