#!/usr/bin/env python3
"""Build the canonical LaTeX paper; intermediate files stay under tmp/."""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tmp/pdfs/latex"
OUTPUT = ROOT / "output/pdf/research-lifecycle.pdf"


def executable(name):
    result = shutil.which(name)
    if result:
        return result
    candidate = Path("/Library/TeX/texbin") / name
    if candidate.exists():
        return str(candidate)
    raise SystemExit(f"Missing LaTeX dependency: {name}")


def run(args, env, cwd=None):
    result = subprocess.run(args, cwd=cwd or ROOT / "paper", env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (BUILD / "build-command.log").write_text(result.stdout)
    if result.returncode:
        print(result.stdout[-10000:])
        raise SystemExit(result.returncode)


# Match distinctive internal product names and paths directly; word boundaries keep
# short names from matching ordinary English. ChronoAI Pte Ltd is an approved author
# affiliation; chrono-ai URLs and internal platforms remain strictly forbidden.
FORBIDDEN = re.compile(
    r"Mathesis|NyxID|\bheca\b|Ornn|\bCMA\b|AgentSeal"
    r"|trureturing-live|live-harness|trureturing-outreach|trureturing-books"
    r"|trureturing-requests|chrono-ai|live\.trureturing"
    r"|books\.trureturing|nyx-assistant-sdk|D5/|Golden/Frozen"
    r"|outreach-control\.yml|hosted-cma-review|ai-org\.live|Atom-SHA"
    r"|Observed outcome|Unit and scope|scorecard"
    r"|reconciled researcher-level records|escape-audit PR|artifact accumulation"
    r"|deployment scorecard|coded records"
    r"|RAIRO|zeckendorf|MATH-AI|crossengine|AI-Native"
    r"|frontier language-model|architectural inflection point"
    r"|great science is no longer bounded|five-product production operating stack"
    r"|The Omega Institute|(?<!the-)Omega Institute|\+08",
    re.IGNORECASE,
)

LOCKED_AI_STATEMENT = (
    "In preparing this manuscript, the authors used AI tools "
    "(ChatGPT Pro, Codex, Claude and Gemini) for literature search, "
    "computation, checking and formal verification in Lean. "
    "All proofs can be checked by hand, and the computations can be "
    "reproduced from the accompanying verification package. "
    "The authors take full responsibility for the content."
)


def sources():
    """Read only the manuscript's actual TeX include graph."""
    found = {}

    def visit(path):
        if path in found:
            return
        content = path.read_text()
        found[path] = content
        for child in re.findall(r"\\(?:input|include)\{([^}]+)\}", content):
            target = path.parent / child
            if not target.suffix:
                target = target.with_suffix(".tex")
            visit(target)

    visit(ROOT / "paper/main.tex")
    return found


def audit_sources():
    texts = sources()
    source = "\n".join(texts.values())
    main_source = texts[ROOT / "paper/main.tex"]
    bibliography = (ROOT / "paper/references.bib").read_text()
    authorblock = re.search(r"\\newcommand\{\\authorblock\}\{%.*?\n\n", main_source, re.S)
    if (not authorblock
            or "ChronoAI Pte Ltd" not in authorblock.group()
            or "National University of Singapore" not in authorblock.group()
            or "Wenlin Zhang$^{1,2}$" not in authorblock.group()
            or "alphabetical order" not in authorblock.group().lower()):
        raise SystemExit("Author block must list all authors with ChronoAI Pte Ltd (1), Wenlin Zhang with (1,2) NUS, and alphabetical order.")
    normalized_main = " ".join(main_source.split())
    if LOCKED_AI_STATEMENT not in normalized_main:
        raise SystemExit("Preserve the exact standard Statement on the use of AI (with Gemini added).")
    appendix = main_source.split(r"\appendix", 1)
    if len(appendix) != 2 or len(re.findall(r"\\section\{", appendix[1])) != 3:
        raise SystemExit("Expected exactly three appendices.")
    keys = re.findall(r"(?m)^@\w+\{([^,]+),", bibliography)
    cited = set()
    for group in re.findall(r"\\cite[pt]?\*?(?:\[[^\]]*\])*\{([^}]+)\}", source):
        cited.update(key.strip() for key in group.split(","))
    if len(keys) != 78 or len(set(keys)) != 78:
        raise SystemExit("Expected exactly 78 unique external bibliography entries.")
    if re.search(r"(?:Zhang,\s*Wenlin|Ma,\s*Haobo|Wenlin\s+Zhang|Haobo\s+Ma)", bibliography, re.I):
        raise SystemExit("Self-citation in the external bibliography.")
    identities = re.findall(r"(?mi)^\s*(?:doi|url)\s*=\s*\{([^}]+)\}", bibliography)
    if len(identities) != len(set(identities)):
        raise SystemExit("Duplicate external reference identity.")
    missing, unused = cited - set(keys), set(keys) - cited
    if missing or unused:
        raise SystemExit(f"Citation mismatch: missing={sorted(missing)}, unused={sorted(unused)}")
    if re.findall(r"\\bibliography\{([^}]+)\}", main_source) != ["references"]:
        raise SystemExit("The manuscript must use only bibliography{references}.")
    if re.search(r"\\nocite\b", source):
        raise SystemExit("Cite references substantively; nocite is not allowed.")
    if FORBIDDEN.search(source + bibliography):
        raise SystemExit(f"Forbidden source string: {FORBIDDEN.search(source + bibliography).group()}")
    if re.search(r"---|—", source):
        raise SystemExit("Remove em-dashes from manuscript prose.")
    if re.search(r"\\code\{[^}]*\\_", source):
        raise SystemExit("Escaped underscore inside code macro.")
    figure_labels = re.findall(r"\\label\{(fig:[^}]+)\}", source)
    if (source.count(r"\begin{tikzpicture}") != 4
            or set(figure_labels) != {"fig:model", "fig:loop", "fig:benchmark", "fig:timeline"}
            or len(figure_labels) != 4):
        raise SystemExit("Expected exactly four TikZ figures with the prescribed labels.")
    if r"\label{tab:scorecard}" in source or r"\label{sec:infrastructure}" in source:
        raise SystemExit("Remove the introductory operational table and infrastructure subsection.")
    results = main_source.split(r"\label{sec:results}", 1)[1]
    first_result = re.search(r"\\subsection\{[^}]+\}\s*\\label\{([^}]+)\}", results)
    if not first_result or first_result.group(1) != "sec:benchmark":
        raise SystemExit("The external benchmark must be Section 4.1.")
    if re.search(r"\\cite[pt]?", texts.get(ROOT / "paper/corpus-table.tex", "")):
        raise SystemExit("The collaborative inventory must use inline links, not bibliography citations.")
    labels = re.findall(r"\\label\{([^}]+)\}", source)
    for label in labels:
        if not re.search(r"\\ref\{" + re.escape(label) + r"\}", main_source):
            raise SystemExit(f"Missing prose reference in main manuscript: {label}")
    boxes = source.count(r"\begin{protocol}")
    wrapped = len(re.findall(
        r"\\noindent\\begin\{minipage\}\{\\linewidth\}\s*"
        r"\\begin\{protocol\}.*?\\end\{protocol\}\s*\\end\{minipage\}",
        source, re.S))
    if boxes != 3 or wrapped != boxes:
        raise SystemExit("Each of the three Boxes must have its own minipage wrapper.")
    print(f"Source audit: {len(keys)} external references; 0 missing; 0 unused; "
          f"4 TikZ figures; {boxes} wrapped Boxes; 3 appendices; 0 self-citations; all {len(labels)} labels referenced.")


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/render_corpus.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/render_benchmark.py")], check=True)
    audit_sources()
    BUILD.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["TZ"] = "UTC"
    env["FORCE_SOURCE_DATE"] = "1"
    env.setdefault("SOURCE_DATE_EPOCH", str(int(
        datetime(2026, 11, 27, tzinfo=timezone.utc).timestamp())))
    env["BIBINPUTS"] = str(ROOT / "paper") + os.pathsep + env.get("BIBINPUTS", "")
    latex = [executable("xelatex"), "-interaction=nonstopmode", "-halt-on-error",
             "-file-line-error", "-output-driver=xdvipdfmx -z 0",
             f"-output-directory={BUILD}", "main.tex"]
    run(latex, env)
    run([executable("bibtex"), "main"], env, cwd=BUILD)
    run(latex, env)
    run(latex, env)
    log = (BUILD / "main.log").read_text(errors="replace")
    biblog = (BUILD / "main.blg").read_text(errors="replace")
    problems = re.findall(
        r"(?mi)^(?:(?:LaTeX(?: Font)?|Package [^:]+|Class [^:]+) Warning:.*"
        r"|Overfull.*|Underfull.*|Missing character.*|.*Infinite glue.*|!.*)$", log)
    bibproblems = re.findall(r"(?mi)^(?:Warning--.*|.*error message.*|I couldn.t open.*|I found no.*)$", biblog)
    if problems or bibproblems:
        raise SystemExit("Resolve all build diagnostics:\n" + "\n".join(problems + bibproblems))
    if "undefined" in log.lower() or "multiply-defined" in log.lower():
        raise SystemExit("Resolve references before delivery; see tmp/pdfs/latex/main.log")
    aux = (BUILD / "main.aux").read_text()
    expected_numbers = {
        "tab:position": "1", "tab:legend": "2", "tab:benchmark": "3",
        "tab:ablation": "4", "tab:caught": "5", "tab:principles": "6",
        "tab:ops": "7", "tab:repro": "8", "tab:corpus": "9",
        "fig:model": "1", "fig:loop": "2", "fig:benchmark": "3", "fig:timeline": "4",
        "box:model": "1", "box:antiinflation": "2", "box:delegate": "3",
        "sec:benchmark": "4.1",
    }
    for label, number in expected_numbers.items():
        if not re.search(r"\\newlabel\{" + re.escape(label) + r"\}\{\{" + re.escape(number) + r"\}", aux):
            raise SystemExit(f"Expected {label} to have number {number}.")
    pdf = BUILD / "main.pdf"
    raw_plus_08 = b"+08" in pdf.read_bytes()
    info = subprocess.check_output([executable("pdfinfo"), str(pdf)], env=env, text=True)
    extracted = subprocess.check_output([executable("pdftotext"), "-layout", str(pdf), "-"],
                                        env=env, text=True)
    if raw_plus_08 or FORBIDDEN.search(info + extracted):
        raise SystemExit("Forbidden PDF text or metadata.")
    if "—" in extracted:
        raise SystemExit("Remove em-dashes from rendered PDF text.")
    pages = extracted.split("\f")
    if ("Keywords:" not in pages[0] or re.search(r"\b1\s+Introduction\b", pages[0])
            or not re.search(r"\b1\s+Introduction\b", pages[1])):
        raise SystemExit("Keep title, abstract and keywords on page 1; begin Introduction on page 2.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, OUTPUT)
    count = re.search(r"(?m)^Pages:\s+(\d+)", info).group(1)
    print("Build audit: 0 BibTeX warnings/errors; 0 LaTeX warnings; "
          "0 underfull/overfull boxes; 0 forbidden strings; 0 em-dashes.")
    print(f"Contains raw '+08': {raw_plus_08}")
    print(f"Built {OUTPUT} ({count} pages; {OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
