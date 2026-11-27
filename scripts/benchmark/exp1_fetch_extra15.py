#!/usr/bin/env python3
"""Track 1B: Deterministically fetch 15 additional real public manuscripts (5 more distinct-lab
AgentAlphaXiv studies + 5 more collaborative arXiv preprints + 5 exact primary-category-matched
Oct/Nov 2026 human-only arXiv preprints via arxiv.org HTML pages to avoid export.arxiv.org 429),
apply airtight de-identification, and combine with the original 15 into N=30 (n=10 per cohort)."""
import hashlib
import json
import random
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ORIG_BASE = Path("data/benchmark/ext_bench")
BASE30 = Path("data/benchmark/ext_bench_n30")
RAW = BASE30 / "raw"
BLIND = BASE30 / "blinded"
RAW.mkdir(parents=True, exist_ok=True)
BLIND.mkdir(parents=True, exist_ok=True)

def fetch_bytes(url, timeout=60, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (academic-benchmark/1.0)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as ex:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))

def fetch_json(url, timeout=45):
    return json.loads(fetch_bytes(url, timeout=timeout).decode("utf-8", errors="replace"))

def fetch_arxiv_meta_html(aid):
    """Fetch exact primary category, title, authors from https://arxiv.org/abs/<aid>."""
    html = fetch_bytes(f"https://arxiv.org/abs/{aid}").decode("utf-8", errors="replace")
    m_title = re.search(r'<meta name="citation_title" content="([^"]+)"', html)
    title = m_title.group(1) if m_title else aid
    authors = re.findall(r'<meta name="citation_author" content="([^"]+)"', html)
    m_cat = re.search(r'<span class="primary-subject">[^<]*\(([a-zA-Z\-]+\.[A-Z\-]+|[a-zA-Z\-]+)\)</span>', html)
    pcat = m_cat.group(1) if m_cat else ""
    time.sleep(0.8)
    return {"title": title, "authors": authors, "primary_category": pcat}

orig_gt = json.loads((ORIG_BASE / "ext_ground_truth.json").read_text())
orig_agent_ids = {r["project_id"] for r in orig_gt if r["cohort"] == "autonomous_ai"}
orig_agent_labs = {r["lab"] for r in orig_gt if r["cohort"] == "autonomous_ai"}
orig_human_ids = {r["arxiv_id"].split("v")[0] for r in orig_gt if r["cohort"] == "human_only_arxiv"}
orig_hitl_ids = {r["arxiv_id"].split("v")[0] for r in orig_gt if r["cohort"] == "human_in_the_loop"}
our_all_ids = {
    p["arxiv_id"]
    for p in json.loads(Path("./data/collaborative-arxiv.json").read_text())["papers"]
}

print("=== 1. Select 5 additional distinct-lab AgentAlphaXiv studies (Labs #6-#10) ===", flush=True)
all_studies = []
for offset in range(0, 1000, 100):
    url = f"https://datasets-server.huggingface.co/rows?dataset=alphaXiv/AgentAlphaXiv&config=studies&split=train&offset={offset}&length=100"
    j = fetch_json(url)
    rows = [r["row"] for r in j.get("rows", [])]
    if not rows:
        break
    all_studies.extend(rows)
    if len(rows) < 100:
        break

math_pat = re.compile(
    r"\b(theorem|proof|lemma|proves|proved|bound|bounds|inequality|combinator\w*|graph|quantum|number theory|prime|conjecture|formal|lean|algorithm|complexity|entropy|algebra|topology|geometry|spectral|matrix|eigenvalue|operator)\b",
    re.I,
)
in_cohort = [s for s in all_studies if s.get("in_paper_cohort")]
candidates = []
for s in in_cohort:
    txt = f"{s.get('title','')} {s.get('abstract','')}"
    hits = sorted(set(m.group(0).lower() for m in math_pat.finditer(txt)))
    pid = str(s.get("project_id") or s.get("id"))
    lab = str(s.get("lab") or s.get("lab_id") or "unknown")
    vnum = int(s.get("latest_version_number") or s.get("version_count") or 1)
    candidates.append((len(hits), vnum, pid, lab, s.get("title", ""), hits))
candidates.sort(key=lambda x: (-x[0], -x[1], x[2]))

new_agent = []
used_labs = set(orig_agent_labs)
for c in candidates:
    if len(new_agent) >= 5:
        break
    if c[2] in orig_agent_ids or c[3] in used_labs:
        continue
    used_labs.add(c[3])
    new_agent.append({
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
    print(f"  NEW AI: {c[2][:12]} | lab={c[3]} | hits={c[0]} | {c[4][:68]}", flush=True)

print("\n=== 2. Select 5 additional collaborative arXiv preprints (most recent Oct-Nov 2026 specialist categories, excl. math.GM) ===", flush=True)
# Deterministic: 5 most recent specialist-category collaborative preprints after the initial 5
extra_hitl_ids = [
    "2610.39941v2",  # cs.FL / math.CO (block-exchange descent, revised 10 Nov 2026)
    "2611.03956v1",  # math.CO (well-covered powers, 2 Nov 2026)
    "2611.04568v1",  # quant-ph (two-qutrit, 3 Nov 2026)
    "2611.21657v1",  # math.CO (inversion sequence classes 152 & 207, 4 Nov 2026)
    "2611.15431v1",  # quant-ph (Nichols-Wootters subadditivity, 11 Nov 2026)
]
new_hitl = []
for aid in extra_hitl_ids:
    meta = fetch_arxiv_meta_html(aid)
    rec = {
        "cohort": "human_in_the_loop",
        "source_id": f"arXiv:{aid}",
        "arxiv_id": aid,
        "category": meta["primary_category"],
        "domain": meta["primary_category"],
        "title": meta["title"],
        "authors": meta["authors"],
        "pdf_url": f"https://arxiv.org/pdf/{aid}.pdf",
    }
    new_hitl.append(rec)
    print(f"  NEW HITL: {aid} | primary={meta['primary_category']} | {meta['title'][:64]}", flush=True)

print("\n=== 3. Deterministically select 5 matched Nov 2026 human-only arXiv preprints ===", flush=True)
# Fetch from https://arxiv.org/list/<cat>/2026-11?skip=0&show=100 (deterministic ascending order)
cat_pool_cache = {}
used_human_base = set(orig_human_ids) | set(our_all_ids)
new_human = []

for hrec in new_hitl:
    cat = hrec["category"]
    if cat not in cat_pool_cache:
        list_url = f"https://arxiv.org/list/{cat}/2026-11?skip=0&show=100"
        html = fetch_bytes(list_url).decode("utf-8", errors="replace")
        time.sleep(0.8)
        # Extract arXiv IDs in order from /abs/2611.xxxxx (note arXiv HTML uses `href ="/abs/..."`)
        aids = re.findall(r'href\s*=\s*"/abs/(\d{4}\.\d{5})"', html)
        # Deduplicate preserving order
        seen = set()
        ordered = []
        for x in aids:
            if x not in seen:
                seen.add(x)
                ordered.append(x)
        cat_pool_cache[cat] = ordered
        print(f"  Fetched {len(ordered)} Nov 2026 listings for {cat}", flush=True)

    picked = None
    for cand_base in cat_pool_cache[cat]:
        if cand_base in used_human_base:
            continue
        meta = fetch_arxiv_meta_html(f"{cand_base}v1")
        if meta["primary_category"] != cat:
            continue
        if re.search(r"\b(erratum|corrigendum|comment on|reply to|survey|review of)\b", meta["title"], re.I):
            continue
        if any("Ma" in a and "Haobo" in a for a in meta["authors"]) or any("Zhang" in a and "Wenlin" in a for a in meta["authors"]):
            continue
        used_human_base.add(cand_base)
        picked = {
            "cohort": "human_only_arxiv",
            "source_id": f"arXiv:{cand_base}v1",
            "arxiv_id": f"{cand_base}v1",
            "category": cat,
            "domain": cat,
            "title": meta["title"],
            "authors": meta["authors"],
            "pdf_url": f"https://arxiv.org/pdf/{cand_base}v1.pdf",
        }
        print(f"  NEW HUMAN ({cat}): {cand_base}v1 | {meta['title'][:64]}", flush=True)
        break
    if not picked:
        raise RuntimeError(f"Could not find human comparator for {cat}")
    new_human.append(picked)

# Download PDFs, extract text via pdftotext, compute structural stats, and airtight-sanitize!
def extract_and_sanitize(rec, slug):
    pdf_path = RAW / f"{slug}.pdf"
    txt_path = RAW / f"{slug}.txt"
    if not pdf_path.exists():
        pdf_bytes = fetch_bytes(rec["pdf_url"], timeout=90)
        pdf_path.write_bytes(pdf_bytes)
        time.sleep(0.6)
    else:
        pdf_bytes = pdf_path.read_bytes()
    sha16 = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    if not txt_path.exists():
        subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
    raw_txt = txt_path.read_text(encoding="utf-8", errors="replace")
    info = subprocess.check_output(["pdfinfo", str(pdf_path)], text=True)
    m_p = re.search(r"(?m)^Pages:\s+(\d+)", info)
    pages = int(m_p.group(1)) if m_p else 0
    words = len(raw_txt.split())
    stmts = len(re.findall(r"(?m)^\s*(?:Theorem|Lemma|Proposition|Corollary)\s+\d+", raw_txt))
    proofs = len(re.findall(r"(?m)^\s*Proof\b", raw_txt))
    fver = len(re.findall(r"\b(Lean\s*4|Lean|Mathlib|DRAT|Coq|Isabelle|Arb|ball arithmetic|formally verified|machine-checked)\b", raw_txt))
    refs = len(re.findall(r"(?m)^\s*\[\d+\]\s+", raw_txt))
    rec["raw_slug"] = slug
    rec["pdf_sha256_16"] = sha16
    rec["struct"] = {
        "pages": pages,
        "words": words,
        "formal_statements": stmts,
        "proof_blocks": proofs,
        "formal_verif_mentions": fver,
        "references_est": refs,
    }

    # Airtight de-identification sanitizer
    s = raw_txt
    # Strip arXiv stamps
    s = re.sub(r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?(?:\s*\[[^\]]+\])?(?:\s+\d+\s+\w+\s+\d{4})?", "[PREPRINT-ID]", s)
    # Strip URLs & emails
    s = re.sub(r"https?://\S+", "[URL]", s)
    s = re.sub(r"[\w.\-+]+@[\w.\-]+\.\w+", "[EMAIL]", s)
    # Strip UUIDs & platform/agent tags
    s = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "[ID]", s, flags=re.I)
    s = re.sub(r"\b(AgentAlphaXiv|alphaXiv|trureturing|the-omega-institute|ChronoAI|Mathesis|autonomous research agent|AI Scientist)\b", "[REDACTED]", s, flags=re.I)
    # Strip explicit author names
    for auth in rec.get("authors", []):
        for part in re.split(r"[,;\s]+", auth):
            if len(part) >= 4:
                s = re.sub(r"\b" + re.escape(part) + r"\b", "[AUTHOR]", s)
    # Strip common affiliations/emails in header region (first 2500 chars)
    lines = s.splitlines()
    clean_lines = []
    for idx, line in enumerate(lines):
        if idx < 45 and re.search(r"\b(University|Institute|Department|Laboratory|College|School of|Pte Ltd|ORCID|MSC|Keywords:.*@|Email)\b", line, re.I):
            continue
        if re.match(r"^\s*(Date:|Address:|E-mail|Current address)", line, re.I):
            continue
        clean_lines.append(line)
    s = "\n".join(clean_lines)
    # Save BOTH full sanitized text AND 36k-capped version matching original protocol
    rec["full_sanitized_len"] = len(s)
    capped = s if len(s) <= 36000 else s[:36000] + f"\n\n[TRUNCATED AT 36,000 CHARS OF {len(s)} TOTAL CHARS]\n"
    rec["sanitized_len"] = len(capped)
    return capped, s

new_records = new_agent + new_human + new_hitl
rng = random.Random(2026112702)
rng.shuffle(new_records)
for idx, rec in enumerate(new_records, start=16):
    bid = f"ext_{idx:02d}"
    rec["blind_id"] = bid
    slug = f"{rec['cohort']}_{idx:02d}"
    print(f"Processing {bid} ({rec['cohort']}): {rec['source_id']}...", flush=True)
    capped, full = extract_and_sanitize(rec, slug)
    (BLIND / f"{bid}.txt").write_text(capped, encoding="utf-8")
    (BLIND / f"{bid}_full.txt").write_text(full, encoding="utf-8")

(BASE30 / "new15_ground_truth.json").write_text(json.dumps(new_records, indent=2))
print(f"\nAssembled & airtight-blinded 15 new manuscripts ext_16..ext_30 -> {BASE30}", flush=True)
