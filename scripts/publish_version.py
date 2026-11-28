#!/usr/bin/env python3
"""Deterministic Zenodo + Mathesis versioned publisher (stdlib only).

Packages one immutable (paper.pdf, source-vN.zip) pair, publishes it to Zenodo
first (or verifies an already-published Zenodo exact-version DOI), waits for
Zenodo's public API record to expose matching files, and delivers the exact
same bytes and verified archive_doi to Mathesis's pre-reviewed collection API.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime, timezone
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

MAX_FILE = 30 * 1024 * 1024
MAX_ZIP_FILES = 2000
SCHEMA = "mathesis.pre-reviewed-delivery.v1"
DEFAULT_MATHESIS_URL = "https://mathesis-omega-research.apps.chrono-ai.fun"
DEFAULT_ZENODO_API = "https://zenodo.org/api"
ZENODO_ALLOWED_BASES = ("https://zenodo.org/api", "https://sandbox.zenodo.org/api")
ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.([1-9][0-9]*)$")

INCLUDE_FILES = (
    "README.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "mathesis.json",
)
INCLUDE_DIRS = ("paper", "data", "scripts", "LICENSES")
EXCLUDED_PARTS = frozenset({".git", ".env", "__pycache__", "node_modules"})
EXCLUDED_NAMES = frozenset({".DS_Store"})
EXCLUDED_SUFFIXES = frozenset(
    {".pyc", ".pyo", ".aux", ".log", ".out", ".bbl", ".blg", ".fls", ".fdb_latexmk"}
)
ZENODO_KEYWORDS = [
    "human-in-the-loop automated research",
    "scientific discovery",
    "scientific slop",
    "Lean 4",
    "formal verification",
    "executable peer review",
    "scholarly collaboration",
    "Mathesis",
]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Refusing to follow HTTP redirect on authenticated request")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_token(raw: str | None, name: str) -> str:
    token = (raw or "").strip()
    if not token or not token.isascii() or any(ord(c) < 33 or ord(c) == 127 for c in token):
        raise ValueError(f"{name} must be a single non-empty ASCII token without whitespace")
    return token


def normalize_mathesis_base(raw: str) -> str:
    parsed = urlsplit(raw.strip())
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        (parsed.scheme != "https" and not (parsed.scheme == "http" and local))
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("MATHESIS_URL must be a clean HTTPS URL (HTTP allowed on loopback only)")
    base = raw.strip().rstrip("/")
    return base if base.endswith("/api/v1") else base + "/api/v1"


def normalize_zenodo_base(raw: str) -> str:
    base = raw.strip().rstrip("/")
    parsed = urlsplit(base)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if base in ZENODO_ALLOWED_BASES or (parsed.scheme == "http" and local and parsed.path.rstrip("/").endswith("/api")):
        return base
    raise ValueError("ZENODO_API must be https://zenodo.org/api or https://sandbox.zenodo.org/api")


def inside_repo(repo: Path, relative: str) -> Path:
    path = repo / relative
    if path.is_symlink() or not path.resolve().is_relative_to(repo):
        raise ValueError(f"Path escapes repository or is a symlink: {relative}")
    return path


def build_source_zip(repo: Path) -> bytes:
    """Build deterministic source ZIP covering manuscript, data, scripts and licenses."""
    repo = repo.resolve(strict=True)
    selected: list[tuple[str, Path]] = []

    for rel in INCLUDE_FILES:
        path = repo / rel
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Invalid source file: {rel}")
            selected.append((rel, path))

    for directory in INCLUDE_DIRS:
        root = repo / directory
        if not root.exists():
            continue
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"Invalid source directory: {directory}")
        for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(repo).as_posix()):
            rel_path = path.relative_to(repo)
            if any(part in EXCLUDED_PARTS for part in rel_path.parts):
                continue
            if path.is_dir():
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Source archive refuses symlinks/special files: {rel_path.as_posix()}")
            if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if path.name.endswith(".synctex.gz"):
                continue
            name = rel_path.as_posix()
            if "\\" in name or any(ord(c) < 32 for c in name):
                raise ValueError(f"Unsafe archive path: {name}")
            selected.append((name, path))

    selected.sort(key=lambda item: item[0])
    if not selected or len(selected) > MAX_ZIP_FILES:
        raise ValueError(f"Source archive must contain 1..{MAX_ZIP_FILES} files")

    out = io.BytesIO()
    total_unpacked = 0
    has_tex = False
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, path in selected:
            raw = path.read_bytes()
            total_unpacked += len(raw)
            if total_unpacked > 64 * 1024 * 1024:
                raise ValueError("Source archive exceeds 64 MiB uncompressed limit")
            if name.endswith(".tex"):
                has_tex = True
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, raw)

    data = out.getvalue()
    if not has_tex:
        raise ValueError("Source archive must contain LaTeX manuscript sources (.tex)")
    if len(data) > MAX_FILE:
        raise ValueError("Source ZIP exceeds 30 MiB upload limit")
    with zipfile.ZipFile(io.BytesIO(data), "r") as check_zf:
        if check_zf.testzip() is not None:
            raise ValueError("Generated source ZIP failed integrity check")
    return data


def read_pdf(repo: Path, relative: str = "paper.pdf") -> bytes:
    path = inside_repo(repo, relative)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE:
        raise ValueError(f"PDF must exist and be at most 30 MiB: {relative}")
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-"):
        raise ValueError(f"File lacks %PDF- header: {relative}")
    return raw


def extract_changelog_section(repo: Path, version_label: str) -> str | None:
    path = repo / "CHANGELOG.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^##\s+{re.escape(version_label)}\b[^\n]*\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match:
        body = match.group(1).strip()
        if body:
            return body[:10000]
    return None


def zenodo_name(name: str) -> str:
    if "," in name:
        return name.strip()
    parts = name.split()
    if len(parts) < 2:
        return name.strip()
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def build_zenodo_metadata(
    envelope: dict,
    *,
    publication_date: str | None = None,
) -> dict:
    paper = envelope["paper"]
    creators = []
    for author in paper["authors"]:
        entry = {"name": zenodo_name(author["name"])}
        if author.get("affiliation"):
            entry["affiliation"] = author["affiliation"]
        if author.get("orcid"):
            entry["orcid"] = author["orcid"]
        creators.append(entry)

    repo_url = paper.get("repository_url", "")
    issues_url = paper.get("issues_url", "")
    description_parts = [f"<p>{html.escape(paper['abstract'])}</p>"]
    if repo_url:
        link_line = (
            f'<p>Public source repository, benchmark records, and reproducibility scripts: '
            f'<a href="{html.escape(repo_url)}">{html.escape(repo_url)}</a>'
        )
        if issues_url:
            link_line += f' (feedback &amp; issues: <a href="{html.escape(issues_url)}">{html.escape(issues_url)}</a>)'
        link_line += ".</p>"
        description_parts.append(link_line)

    meta = {
        "title": paper["title"],
        "upload_type": "publication",
        "publication_type": "preprint",
        "creators": creators,
        "description": "\n".join(description_parts),
        "access_right": "open",
        "license": paper["license"].lower(),
        "version": paper.get("version_label") or f"v{envelope['version']}",
        "publication_date": publication_date or date.today().isoformat(),
        "keywords": list(ZENODO_KEYWORDS),
        "prereserve_doi": True,
    }
    if repo_url:
        meta["related_identifiers"] = [
            {"relation": "isDerivedFrom", "identifier": repo_url}
        ]
    return meta


def validate_github_url(url: str, *, issues: bool = False) -> str:
    owner = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
    repo = r"[A-Za-z0-9_.-]{1,100}"
    match = re.fullmatch(
        rf"https://github\.com/({owner})/({repo})" + ("/issues" if issues else ""),
        url,
    )
    if not match or match[2] in (".", "..") or "--" in match[1]:
        raise ValueError("Require a public HTTPS GitHub repository or /issues URL")
    return url.removesuffix("/issues") if issues else url


def validate_envelope(envelope: dict) -> None:
    if envelope.get("schema") != SCHEMA or envelope.get("authorize_publication") is not True:
        raise ValueError("Require mathesis.pre-reviewed-delivery.v1 and authorize_publication: true")
    allowed_top = {
        "schema",
        "producer",
        "work_id",
        "version",
        "previous_version",
        "authorize_publication",
        "paper",
        "review",
    }
    if set(envelope) - allowed_top or allowed_top - set(envelope):
        raise ValueError("Unexpected or missing top-level envelope fields")
    for key in ("producer", "work_id"):
        if not isinstance(envelope.get(key), str) or not re.fullmatch(r"[a-z0-9-]{1,160}", envelope[key]):
            raise ValueError(f"{key} requires a lowercase ASCII slug")
    version, previous = envelope.get("version"), envelope.get("previous_version")
    if type(version) is not int or not 1 <= version <= 4294967295:
        raise ValueError("version must be a positive 32-bit integer")
    if previous is not None and (type(previous) is not int or not 0 < previous < version):
        raise ValueError("previous_version must be null or a smaller positive integer")

    paper = envelope["paper"]
    allowed_paper = {
        "title",
        "abstract",
        "authors",
        "license",
        "archive_doi",
        "plain_language",
        "msc",
        "problems",
        "lean",
        "kind",
        "repository_url",
        "issues_url",
        "version_label",
        "changelog",
    }
    if not isinstance(paper, dict) or (set(paper) - allowed_paper):
        raise ValueError("Unknown paper field in envelope")
    for key, limit in (("title", 1000), ("abstract", 20000)):
        val = paper.get(key)
        if not isinstance(val, str) or not val.strip() or len(val.strip()) > limit:
            raise ValueError(f"paper.{key} must be nonempty and at most {limit} chars")
    if paper.get("license") != "CC-BY-4.0":
        raise ValueError("paper.license must be CC-BY-4.0")
    if paper.get("kind", "note") not in ("paper", "note", "methodology"):
        raise ValueError("paper.kind must be paper, note, or methodology")
    authors = paper.get("authors")
    if not isinstance(authors, list) or not authors or len(authors) > 50:
        raise ValueError("paper.authors must be a nonempty list")
    for author in authors:
        if not isinstance(author, dict) or not isinstance(author.get("name"), str) or not author["name"].strip():
            raise ValueError("Each author needs a nonempty name")
        if author.get("person") is not None:
            raise ValueError("Do not assert Mathesis account ownership in paper.authors")
    if paper.get("repository_url") is not None:
        validate_github_url(paper["repository_url"])
    if paper.get("issues_url") is not None:
        issues_repo = validate_github_url(paper["issues_url"], issues=True)
        if paper.get("repository_url") and paper["repository_url"] != issues_repo:
            raise ValueError("issues_url must belong to repository_url")
    if paper.get("archive_doi") is not None:
        if not isinstance(paper["archive_doi"], str) or not ZENODO_DOI_RE.fullmatch(paper["archive_doi"]):
            raise ValueError("paper.archive_doi must be a published exact-version Zenodo DOI (10.5281/zenodo.<id>)")
    for key, limit in (("version_label", 64), ("changelog", 10000)):
        if paper.get(key) is not None:
            val = paper[key]
            if not isinstance(val, str) or not val.strip() or len(val) > limit:
                raise ValueError(f"paper.{key} must be nonempty and at most {limit} chars")

    review = envelope["review"]
    if set(review) != {"verdict", "pdf_sha256", "source_sha256", "record"}:
        raise ValueError("Invalid review keys")
    if review.get("verdict") not in ("PASS", "INTERNAL_EDITORIAL"):
        raise ValueError("review.verdict must be PASS or INTERNAL_EDITORIAL")
    if not isinstance(review.get("record"), dict) or not review["record"]:
        raise ValueError("review.record must be a nonempty JSON object")
    for key in ("pdf_sha256", "source_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", review.get(key, "")):
            raise ValueError(f"review.{key} must be a 64-char lowercase SHA-256 hex digest")
    if len(json.dumps(envelope, ensure_ascii=False).encode("utf-8")) > 128 * 1024:
        raise ValueError("Delivery envelope exceeds 128 KiB")


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 90,
    allow_404: bool = False,
) -> tuple[int, bytes]:
    req = Request(url, data=data, method=method, headers=headers or {})
    try:
        with build_opener(NoRedirect()).open(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except HTTPError as exc:
        code = exc.code
        detail = ""
        try:
            body = exc.read(4096).decode("utf-8", errors="replace").strip()
            if body:
                detail = " " + " ".join(body.split())[:300]
        except Exception:
            pass
        exc.close()
        if allow_404 and code == 404:
            return 404, b""
        raise RuntimeError(f"HTTP {code} from {method} {urlsplit(url).path}:{detail}") from None
    except URLError as exc:
        raise RuntimeError(f"Network error on {method} {urlsplit(url).path}: {exc.reason}") from None


class ZenodoClient:
    def __init__(self, token: str, base: str = DEFAULT_ZENODO_API):
        self.token = clean_token(token, "ZENODO_TOKEN")
        self.base = normalize_zenodo_base(base)

    def api(self, method: str, path_or_url: str, data=None) -> dict | None:
        target = path_or_url if path_or_url.startswith(("https://", "http://")) else self.base + path_or_url
        if not target.startswith(self.base + "/"):
            raise ValueError("Refusing Zenodo request outside configured API origin")
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
            "User-Agent": "hitl-automated-research-publisher/1",
        }
        payload: bytes | None = None
        if isinstance(data, (dict, list)):
            payload = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif data is not None:
            payload = data
            headers["Content-Type"] = "application/octet-stream"
        _, raw = http_request(method, target, headers=headers, data=payload, timeout=120)
        return json.loads(raw) if raw else None

    def public_record(self, record_id: int) -> dict | None:
        status, raw = http_request(
            "GET",
            f"{self.base}/records/{record_id}",
            headers={"Accept": "application/json", "User-Agent": "hitl-automated-research-publisher/1"},
            timeout=60,
            allow_404=True,
        )
        if status == 404:
            return None
        return json.loads(raw)


def verify_public_zenodo_record(
    base: str,
    doi: str,
    pdf_bytes: bytes,
    source_bytes: bytes,
    *,
    download_verify: bool = True,
    max_attempts: int = 12,
    sleep_fn=time.sleep,
) -> dict:
    """Wait for and verify that the public Zenodo record exposes exact PDF and ZIP bytes."""
    match = ZENODO_DOI_RE.fullmatch(doi)
    if not match:
        raise ValueError(f"Expected exact-version Zenodo DOI, got: {doi}")
    record_id = int(match.group(1))
    base = normalize_zenodo_base(base)
    expected = {
        ".pdf": (len(pdf_bytes), hashlib.sha256(pdf_bytes).hexdigest()),
        ".zip": (len(source_bytes), hashlib.sha256(source_bytes).hexdigest()),
    }
    headers = {"Accept": "application/json", "User-Agent": "hitl-automated-research-publisher/1"}
    last_reason = "record not yet visible"

    for attempt in range(max_attempts):
        try:
            status, raw = http_request(
                "GET", f"{base}/records/{record_id}", headers=headers, timeout=60, allow_404=True
            )
        except RuntimeError as exc:
            if any(code in str(exc) for code in ("HTTP 502", "HTTP 503", "HTTP 504")) and attempt < max_attempts - 1:
                last_reason = str(exc)
                sleep_fn(min(2 * (attempt + 1), 10))
                continue
            raise
        if status == 200 and raw:
            record = json.loads(raw)
            if (
                record.get("id") == record_id
                and record.get("doi") == doi
                and record.get("submitted") is True
                and record.get("state") == "done"
            ):
                files = record.get("files") or []
                matched_keys = {}
                ok = True
                for ext, (size, _) in expected.items():
                    cands = [
                        f for f in files
                        if f.get("size") == size and str(f.get("key", "")).lower().endswith(ext)
                    ]
                    if len(cands) != 1:
                        last_reason = f"expected 1 {ext} file of size {size}, found {len(cands)}"
                        ok = False
                        break
                    matched_keys[ext] = cands[0]["key"]
                if ok:
                    if download_verify:
                        for ext, (size, sha) in expected.items():
                            key = matched_keys[ext]
                            _, content = http_request(
                                "GET",
                                f"{base}/records/{record_id}/files/{quote(key, safe='')}/content",
                                headers={"User-Agent": "hitl-automated-research-publisher/1"},
                                timeout=120,
                            )
                            if len(content) != size or hashlib.sha256(content).hexdigest() != sha:
                                raise ValueError(f"Public Zenodo file {key} differs in SHA-256 from local package")
                    return {
                        "record_id": record_id,
                        "doi": record["doi"],
                        "doi_url": "https://doi.org/" + record["doi"],
                        "concept_doi": record.get("conceptdoi"),
                        "concept_doi_url": (
                            "https://doi.org/" + record["conceptdoi"] if record.get("conceptdoi") else None
                        ),
                        "record_url": f"https://zenodo.org/records/{record_id}",
                        "files": matched_keys,
                    }
            else:
                last_reason = (
                    f"state={record.get('state')!r} submitted={record.get('submitted')!r} doi={record.get('doi')!r}"
                )
        if attempt < max_attempts - 1:
            sleep_fn(min(2 * (attempt + 1), 10))

    raise RuntimeError(f"Public Zenodo record {doi} did not become ready: {last_reason}")


def publish_to_zenodo(
    client: ZenodoClient,
    zenodo_meta: dict,
    pdf_name: str,
    pdf_bytes: bytes,
    source_name: str,
    source_bytes: bytes,
    *,
    previous_record_id: int | None = None,
    reserve_only: bool = False,
    sleep_fn=time.sleep,
) -> dict:
    if previous_record_id is not None:
        resp = client.api("POST", f"/deposit/depositions/{previous_record_id}/actions/newversion")
        draft_url = resp["links"]["latest_draft"]
        record = client.api("GET", draft_url)
        record_id = int(record["id"])
        print(f"Created Zenodo new-version draft ID: {record_id} (from {previous_record_id})", flush=True)
        record = client.api("PUT", f"/deposit/depositions/{record_id}", {"metadata": zenodo_meta})
        for old in record.get("files") or []:
            client.api("DELETE", f"/deposit/depositions/{record_id}/files/{quote(str(old['id']), safe='')}")
    else:
        record = client.api("POST", "/deposit/depositions", {"metadata": zenodo_meta})
        record_id = int(record["id"])
        print(f"Created Zenodo deposition ID: {record_id}", flush=True)

    bucket = record["links"]["bucket"]
    files_to_upload = {pdf_name: pdf_bytes, source_name: source_bytes}
    for filename, content in files_to_upload.items():
        client.api("PUT", f"{bucket}/{quote(filename, safe='')}", content)

    record = client.api("GET", f"/deposit/depositions/{record_id}")
    remote_files = {f["filename"]: f for f in record.get("files") or []}
    if set(remote_files) != set(files_to_upload):
        raise ValueError(f"Zenodo draft file inventory mismatch: {sorted(remote_files)}")
    for filename, content in files_to_upload.items():
        local_md5 = hashlib.md5(content).hexdigest()
        remote_md5 = str(remote_files[filename].get("checksum", "")).removeprefix("md5:")
        if remote_md5 != local_md5:
            raise ValueError(f"Zenodo MD5 mismatch for {filename}: expected {local_md5}, got {remote_md5}")

    if reserve_only:
        reserved = (record.get("metadata") or {}).get("prereserve_doi") or {}
        if not reserved.get("doi"):
            raise ValueError("Zenodo did not return a reserved DOI")
        return {
            "record_id": record_id,
            "reserved_doi": reserved["doi"],
            "submitted": False,
        }

    client.api("POST", f"/deposit/depositions/{record_id}/actions/publish")
    record = client.api("GET", f"/deposit/depositions/{record_id}")
    doi = record.get("doi")
    if not record.get("submitted") or not doi or not ZENODO_DOI_RE.fullmatch(doi):
        raise ValueError("Zenodo publish did not return a valid exact-version DOI")
    print(f"Published Zenodo exact-version DOI: {doi} (concept: {record.get('conceptdoi')})", flush=True)

    return verify_public_zenodo_record(
        client.base,
        doi,
        pdf_bytes,
        source_bytes,
        download_verify=True,
        sleep_fn=sleep_fn,
    )


def resolve_previous_version(api_base: str, work_id: str, version: int) -> int | None:
    status, raw = http_request(
        "GET",
        f"{api_base}/collected-papers/{quote(work_id, safe='')}",
        headers={"Accept": "application/json", "User-Agent": "hitl-automated-research-publisher/1"},
        timeout=60,
        allow_404=True,
    )
    if status == 404 or not raw:
        return None
    latest = json.loads(raw)
    current = int(latest["revision"])
    if current > version:
        raise ValueError(f"Delivery version {version} is older than current Mathesis version {current}")
    if current == version:
        return int(latest["previous_version"]) if latest.get("previous_version") else None
    return current


def build_multipart(envelope: dict, pdf_name: str, pdf_bytes: bytes, source_name: str, source_bytes: bytes) -> tuple[bytes, str]:
    meta_bytes = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    boundary = "mathesis-" + hashlib.sha256(meta_bytes + pdf_bytes + source_bytes).hexdigest()
    fields = [
        ("metadata", None, "application/json", meta_bytes),
        ("pdf", pdf_name, "application/pdf", pdf_bytes),
        ("source", source_name, "application/zip", source_bytes),
    ]
    body = bytearray()
    for name, filename, content_type, data in fields:
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'.encode("utf-8"))
        if filename:
            body.extend(f'; filename="{filename}"'.encode("utf-8"))
        body.extend(f"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def deliver_to_mathesis(
    api_base: str,
    token: str,
    envelope: dict,
    pdf_name: str,
    pdf_bytes: bytes,
    source_name: str,
    source_bytes: bytes,
) -> dict:
    token = clean_token(token, "MATHESIS_TOKEN")
    validate_envelope(envelope)
    body, content_type = build_multipart(envelope, pdf_name, pdf_bytes, source_name, source_bytes)
    _, raw = http_request(
        "POST",
        f"{api_base}/pre-reviewed-deliveries",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": content_type,
            "User-Agent": "hitl-automated-research-publisher/1",
        },
        data=body,
        timeout=120,
    )
    return json.loads(raw)


def verify_mathesis_readback(api_base: str, envelope: dict) -> dict:
    work_id = envelope["work_id"]
    version = envelope["version"]
    _, raw = http_request(
        "GET",
        f"{api_base}/collected-papers/{quote(work_id, safe='')}?version={version}",
        headers={"Accept": "application/json", "User-Agent": "hitl-automated-research-publisher/1"},
        timeout=60,
    )
    public = json.loads(raw)
    if public.get("id") != work_id or str(public.get("revision")) != str(version):
        raise ValueError("Mathesis public readback identity/version mismatch")
    expected_kind = envelope["paper"].get("kind", "note")
    if public.get("kind") != expected_kind:
        raise ValueError(f"Mathesis public readback kind mismatch: expected {expected_kind}, got {public.get('kind')}")
    expected_doi = envelope["paper"].get("archive_doi")
    if expected_doi and (public.get("archive") or {}).get("doi") != expected_doi:
        raise ValueError("Mathesis public readback does not display the verified archive DOI")
    if envelope["paper"].get("repository_url") and public.get("repository_url") != envelope["paper"]["repository_url"]:
        raise ValueError("Mathesis public readback repository_url mismatch")
    if not (public.get("pdf") or {}).get("url") or not (public.get("source") or {}).get("url"):
        raise ValueError("Mathesis public readback missing PDF or source file URLs")
    return public


def prepare_envelope(
    repo: Path,
    *,
    metadata_path: str = "mathesis.json",
    pdf_path: str = "paper.pdf",
    version: int | None = None,
    previous_version: int | None = None,
    version_label: str | None = None,
    changelog: str | None = None,
    commit_sha: str | None = None,
    archive_doi: str | None = None,
    concept_doi: str | None = None,
) -> tuple[dict, bytes, bytes, str]:
    repo = repo.resolve(strict=True)
    envelope = copy.deepcopy(json.loads(inside_repo(repo, metadata_path).read_text(encoding="utf-8")))
    if version is not None:
        envelope["version"] = version
    if previous_version is not None:
        envelope["previous_version"] = previous_version
    elif version == 1:
        envelope["previous_version"] = None

    effective_label = (version_label or "").strip() or envelope["paper"].get("version_label") or f"v{envelope['version']}"
    envelope["paper"]["version_label"] = effective_label

    effective_changelog = (changelog or "").strip()
    if not effective_changelog:
        effective_changelog = extract_changelog_section(repo, effective_label) or envelope["paper"].get("changelog", "")
    envelope["paper"]["changelog"] = effective_changelog

    if archive_doi:
        envelope["paper"]["archive_doi"] = archive_doi

    pdf_bytes = read_pdf(repo, pdf_path)
    source_bytes = build_source_zip(repo)
    source_name = f"source-v{envelope['version']}.zip"

    envelope["review"]["pdf_sha256"] = hashlib.sha256(pdf_bytes).hexdigest()
    envelope["review"]["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    record = dict(envelope["review"].get("record") or {})
    record["version_label"] = effective_label
    if commit_sha:
        record["commit"] = commit_sha
    if archive_doi:
        record["zenodo_doi"] = archive_doi
    if concept_doi:
        record["zenodo_concept_doi"] = concept_doi
    envelope["review"]["record"] = record

    validate_envelope(envelope)
    return envelope, pdf_bytes, source_bytes, source_name


def write_step_summary(summary_path: str | None, receipt: dict) -> None:
    if not summary_path:
        return
    lines = [
        f"## Publication Receipt (`{receipt['version_label']}` / Mathesis v{receipt['version']})",
        "",
        f"- **Mode**: `{receipt['mode']}`",
        f"- **PDF**: `paper.pdf` ({receipt['pdf_bytes']:,} bytes, SHA-256 `{receipt['pdf_sha256']}`)",
        f"- **Source ZIP**: `{receipt['source_filename']}` ({receipt['source_bytes']:,} bytes, SHA-256 `{receipt['source_sha256']}`)",
    ]
    zenodo = receipt.get("zenodo")
    if zenodo:
        if zenodo.get("doi"):
            lines.append(f"- **Zenodo Version DOI**: [{zenodo['doi']}]({zenodo['doi_url']})")
        if zenodo.get("concept_doi"):
            lines.append(f"- **Zenodo Concept DOI**: [{zenodo['concept_doi']}]({zenodo['concept_doi_url']})")
        if zenodo.get("record_url"):
            lines.append(f"- **Zenodo Record**: {zenodo['record_url']}")
    mathesis = receipt.get("mathesis")
    if mathesis and mathesis.get("public_url"):
        lines.append(f"- **Mathesis Public Page**: {mathesis['public_url']}")
    lines.append("")
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--metadata", default="mathesis.json")
    parser.add_argument("--pdf", default="paper.pdf")
    parser.add_argument("--out-dir", type=Path, default=Path("dist-publish"))
    parser.add_argument("--version", type=int)
    parser.add_argument("--previous-version", type=int)
    parser.add_argument("--auto-previous-version", action="store_true")
    parser.add_argument("--version-label")
    parser.add_argument("--changelog")
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--publication-date")
    parser.add_argument("--previous-zenodo-record-id", type=int)
    parser.add_argument("--existing-zenodo-doi")
    parser.add_argument("--zenodo-api", default=os.environ.get("ZENODO_API", DEFAULT_ZENODO_API))
    parser.add_argument("--mathesis-url", default=os.environ.get("MATHESIS_URL", DEFAULT_MATHESIS_URL))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reserve-only", action="store_true")
    parser.add_argument("--allow-no-doi", action="store_true")
    args = parser.parse_args(argv)

    try:
        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        existing_doi = (args.existing_zenodo_doi or "").strip() or None
        if existing_doi and args.previous_zenodo_record_id is not None:
            raise ValueError("Specify at most one of --existing-zenodo-doi and --previous-zenodo-record-id")

        envelope, pdf_bytes, source_bytes, source_name = prepare_envelope(
            args.repo,
            metadata_path=args.metadata,
            pdf_path=args.pdf,
            version=args.version,
            previous_version=args.previous_version,
            version_label=args.version_label,
            changelog=args.changelog,
            commit_sha=args.commit_sha.strip() or None,
            archive_doi=existing_doi,
        )
        zenodo_meta = build_zenodo_metadata(envelope, publication_date=args.publication_date)

        (out_dir / "paper.pdf").write_bytes(pdf_bytes)
        (out_dir / source_name).write_bytes(source_bytes)
        (out_dir / f"zenodo-metadata-v{envelope['version']}.json").write_text(
            json.dumps(zenodo_meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        receipt = {
            "schema": "hitl-publication-receipt.v1",
            "mode": "dry-run" if args.dry_run else ("reserve-only" if args.reserve_only else "live"),
            "timestamp": now_utc(),
            "work_id": envelope["work_id"],
            "version": envelope["version"],
            "version_label": envelope["paper"]["version_label"],
            "commit": envelope["review"]["record"].get("commit"),
            "pdf_filename": "paper.pdf",
            "pdf_bytes": len(pdf_bytes),
            "pdf_sha256": envelope["review"]["pdf_sha256"],
            "source_filename": source_name,
            "source_bytes": len(source_bytes),
            "source_sha256": envelope["review"]["source_sha256"],
            "zenodo": None,
            "mathesis": None,
        }

        if args.dry_run:
            (out_dir / f"publication-receipt-v{envelope['version']}.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            write_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), receipt)
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 0

        zenodo_base = normalize_zenodo_base(args.zenodo_api)
        if existing_doi:
            zenodo_receipt = verify_public_zenodo_record(
                zenodo_base,
                existing_doi,
                pdf_bytes,
                source_bytes,
                download_verify=True,
                max_attempts=3,
            )
        else:
            zenodo_client = ZenodoClient(os.environ.get("ZENODO_TOKEN", ""), base=zenodo_base)
            zenodo_receipt = publish_to_zenodo(
                zenodo_client,
                zenodo_meta,
                "paper.pdf",
                pdf_bytes,
                source_name,
                source_bytes,
                previous_record_id=args.previous_zenodo_record_id,
                reserve_only=args.reserve_only,
            )

        receipt["zenodo"] = zenodo_receipt
        receipt_path = out_dir / f"publication-receipt-v{envelope['version']}.json"
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.reserve_only:
            write_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), receipt)
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 0

        if zenodo_base != DEFAULT_ZENODO_API and not args.allow_no_doi:
            raise ValueError("Refusing to attach a non-production Zenodo DOI to live Mathesis")

        doi = zenodo_receipt.get("doi")
        if not doi and not args.allow_no_doi:
            raise ValueError("Published production Zenodo DOI is required before Mathesis delivery")

        api_base = normalize_mathesis_base(args.mathesis_url)
        prev = args.previous_version
        if args.auto_previous_version and prev is None:
            prev = resolve_previous_version(api_base, envelope["work_id"], envelope["version"])

        envelope, pdf_bytes, source_bytes, source_name = prepare_envelope(
            args.repo,
            metadata_path=args.metadata,
            pdf_path=args.pdf,
            version=envelope["version"],
            previous_version=prev,
            version_label=envelope["paper"]["version_label"],
            changelog=envelope["paper"]["changelog"],
            commit_sha=args.commit_sha.strip() or None,
            archive_doi=doi if zenodo_base == DEFAULT_ZENODO_API else None,
            concept_doi=zenodo_receipt.get("concept_doi"),
        )

        try:
            mathesis_receipt = deliver_to_mathesis(
                api_base,
                os.environ.get("MATHESIS_TOKEN", ""),
                envelope,
                "paper.pdf",
                pdf_bytes,
                source_name,
                source_bytes,
            )
            public_readback = verify_mathesis_readback(api_base, envelope)
        except Exception:
            write_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), receipt)
            raise

        site_root = api_base.removesuffix("/api/v1")
        receipt["mathesis"] = {
            "work_id": envelope["work_id"],
            "version": envelope["version"],
            "public_url": f"{site_root}/papers/{envelope['work_id']}?version={envelope['version']}",
            "receipt": mathesis_receipt,
            "verified_archive_doi": (public_readback.get("archive") or {}).get("doi"),
        }

        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(f"Publication failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
