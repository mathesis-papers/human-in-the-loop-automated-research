"""End-to-end offline tests for scripts/publish_version.py (no sockets required)."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import publish_version as pv


class MockTransport:
    """In-memory mock for Zenodo (/api/...) and Mathesis (/api/v1/...) APIs."""

    def __init__(self):
        self.next_record_id = 25000001
        self.concept_id = 25000000
        self.depositions: dict[int, dict] = {}
        self.files: dict[int, dict[str, bytes]] = {}
        self.mathesis_works: dict[str, dict[int, dict]] = {}
        self.zenodo_calls: list[tuple[str, str]] = []
        self.mathesis_calls: list[tuple[str, str]] = []
        self.expected_zenodo_token = "test-zenodo-token"
        self.expected_mathesis_token = "test-mathesis-token"
        self.public_delay_polls = 1
        self._public_polls: dict[int, int] = {}
        self.fail_mathesis_once = False

    def __call__(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        timeout: int = 90,
        allow_404: bool = False,
    ) -> tuple[int, bytes]:
        headers = headers or {}
        parsed = urlsplit(url)
        host = parsed.hostname
        path = parsed.path
        query = parse_qs(parsed.query)

        if host == "zenodo.org":
            return self._handle_zenodo(method, path, headers, data, allow_404)
        if host == "mathesis-omega-research.apps.chrono-ai.fun":
            return self._handle_mathesis(method, path, query, headers, data, allow_404)
        raise RuntimeError(f"Unexpected test host: {host}")

    def _require_bearer(self, headers: dict[str, str], expected: str, method: str, path: str) -> None:
        if headers.get("Authorization") != f"Bearer {expected}":
            raise RuntimeError(f"HTTP 401 from {method} {path}: unauthorized")

    def _handle_zenodo(
        self, method: str, path: str, headers: dict[str, str], data: bytes | None, allow_404: bool
    ) -> tuple[int, bytes]:
        self.zenodo_calls.append((method, path))
        if path == "/api/deposit/depositions" and method == "POST":
            self._require_bearer(headers, self.expected_zenodo_token, method, path)
            payload = json.loads(data.decode("utf-8"))
            rec_id = self.next_record_id
            self.next_record_id += 1
            meta = dict(payload["metadata"])
            meta["prereserve_doi"] = {"doi": f"10.5281/zenodo.{rec_id}", "recid": rec_id}
            dep = {
                "id": rec_id,
                "submitted": False,
                "metadata": meta,
                "files": [],
                "links": {
                    "bucket": f"https://zenodo.org/api/files/{rec_id}",
                    "latest_draft": f"https://zenodo.org/api/deposit/depositions/{rec_id}",
                },
            }
            self.depositions[rec_id] = dep
            self.files[rec_id] = {}
            return 201, json.dumps(dep).encode("utf-8")

        if path.startswith("/api/files/") and method == "PUT":
            self._require_bearer(headers, self.expected_zenodo_token, method, path)
            _, _, rec_str, raw_name = path.strip("/").split("/", 3)
            rec_id = int(rec_str)
            name = unquote(raw_name)
            self.files[rec_id][name] = data or b""
            md5 = hashlib.md5(data or b"").hexdigest()
            dep = self.depositions[rec_id]
            dep["files"] = [f for f in dep["files"] if f["filename"] != name] + [
                {"id": name, "filename": name, "checksum": md5, "filesize": len(data or b"")}
            ]
            return 200, json.dumps({"filename": name, "checksum": f"md5:{md5}"}).encode("utf-8")

        if path.startswith("/api/deposit/depositions/") and path.endswith("/actions/newversion") and method == "POST":
            self._require_bearer(headers, self.expected_zenodo_token, method, path)
            prev_id = int(path.strip("/").split("/")[3])
            prev = self.depositions[prev_id]
            new_id = self.next_record_id
            self.next_record_id += 1
            new_dep = {
                "id": new_id,
                "submitted": False,
                "metadata": json.loads(json.dumps(prev["metadata"])),
                "files": json.loads(json.dumps(prev["files"])),
                "links": {
                    "bucket": f"https://zenodo.org/api/files/{new_id}",
                    "latest_draft": f"https://zenodo.org/api/deposit/depositions/{new_id}",
                },
            }
            self.depositions[new_id] = new_dep
            self.files[new_id] = dict(self.files[prev_id])
            prev["links"]["latest_draft"] = new_dep["links"]["latest_draft"]
            return 201, json.dumps(prev).encode("utf-8")

        if path.startswith("/api/deposit/depositions/") and path.endswith("/actions/publish") and method == "POST":
            self._require_bearer(headers, self.expected_zenodo_token, method, path)
            rec_id = int(path.strip("/").split("/")[3])
            dep = self.depositions[rec_id]
            dep["submitted"] = True
            dep["doi"] = f"10.5281/zenodo.{rec_id}"
            dep["conceptdoi"] = f"10.5281/zenodo.{self.concept_id}"
            return 202, json.dumps(dep).encode("utf-8")

        if path.startswith("/api/deposit/depositions/") and "/files/" in path and method == "DELETE":
            self._require_bearer(headers, self.expected_zenodo_token, method, path)
            parts = path.strip("/").split("/")
            rec_id = int(parts[3])
            file_id = unquote(parts[5])
            self.files[rec_id].pop(file_id, None)
            dep = self.depositions[rec_id]
            dep["files"] = [f for f in dep["files"] if f["id"] != file_id]
            return 204, b""

        if path.startswith("/api/deposit/depositions/"):
            self._require_bearer(headers, self.expected_zenodo_token, method, path)
            rec_id = int(path.rsplit("/", 1)[-1])
            dep = self.depositions[rec_id]
            if method == "PUT":
                reserved = dep["metadata"].get("prereserve_doi")
                dep["metadata"] = json.loads(data.decode("utf-8"))["metadata"]
                dep["metadata"]["prereserve_doi"] = reserved
            return 200, json.dumps(dep).encode("utf-8")

        if path.startswith("/api/records/") and method == "GET":
            parts = path.strip("/").split("/")
            rec_id = int(parts[2])
            dep = self.depositions.get(rec_id)
            if not dep or not dep.get("submitted"):
                if allow_404:
                    return 404, b""
                raise RuntimeError(f"HTTP 404 from GET {path}")
            if len(parts) == 3:
                polls = self._public_polls.get(rec_id, 0)
                self._public_polls[rec_id] = polls + 1
                if polls < self.public_delay_polls:
                    return 404, b""
                pub_files = [
                    {"key": fname, "size": len(blob)}
                    for fname, blob in sorted(self.files.get(rec_id, {}).items())
                ]
                return 200, json.dumps(
                    {
                        "id": rec_id,
                        "doi": dep["doi"],
                        "conceptdoi": dep["conceptdoi"],
                        "submitted": True,
                        "state": "done",
                        "files": pub_files,
                    }
                ).encode("utf-8")
            if len(parts) == 6 and parts[3] == "files" and parts[5] == "content":
                key = unquote(parts[4])
                blob = self.files.get(rec_id, {}).get(key)
                if blob is None:
                    raise RuntimeError(f"HTTP 404 from GET {path}")
                return 200, blob

        raise RuntimeError(f"Unhandled Zenodo route: {method} {path}")

    def _handle_mathesis(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        headers: dict[str, str],
        data: bytes | None,
        allow_404: bool,
    ) -> tuple[int, bytes]:
        self.mathesis_calls.append((method, path))
        if path.startswith("/api/v1/collected-papers/") and method == "GET":
            work_id = unquote(path.removeprefix("/api/v1/collected-papers/"))
            versions = self.mathesis_works.get(work_id)
            if not versions:
                if allow_404:
                    return 404, b""
                raise RuntimeError(f"HTTP 404 from GET {path}")
            ver = int(query["version"][0]) if "version" in query else max(versions)
            entry = versions.get(ver)
            if not entry:
                if allow_404:
                    return 404, b""
                raise RuntimeError(f"HTTP 404 from GET {path}")
            return 200, json.dumps(entry).encode("utf-8")

        if path == "/api/v1/pre-reviewed-deliveries" and method == "POST":
            self._require_bearer(headers, self.expected_mathesis_token, method, path)
            if self.fail_mathesis_once:
                self.fail_mathesis_once = False
                raise RuntimeError("HTTP 503 from POST /api/v1/pre-reviewed-deliveries: transient")
            ctype = headers.get("Content-Type", "")
            boundary = ctype.split("boundary=", 1)[1].encode("utf-8")
            parts = (data or b"").split(b"--" + boundary)
            parsed_parts: dict[str, bytes] = {}
            for part in parts[1:-1]:
                head, content = part.split(b"\r\n\r\n", 1)
                content = content[:-2]
                head_str = head.decode("utf-8")
                for name in ("metadata", "pdf", "source"):
                    if f'name="{name}"' in head_str:
                        parsed_parts[name] = content
            envelope = json.loads(parsed_parts["metadata"].decode("utf-8"))
            pdf_sha = hashlib.sha256(parsed_parts["pdf"]).hexdigest()
            src_sha = hashlib.sha256(parsed_parts["source"]).hexdigest()
            if envelope["review"]["pdf_sha256"] != pdf_sha or envelope["review"]["source_sha256"] != src_sha:
                raise RuntimeError("HTTP 400 from POST /api/v1/pre-reviewed-deliveries: sha mismatch")
            doi = envelope["paper"].get("archive_doi")
            if doi:
                rec_id = int(doi.rsplit(".", 1)[-1])
                dep = self.depositions.get(rec_id)
                if not dep or not dep.get("submitted"):
                    raise RuntimeError("HTTP 400 from POST /api/v1/pre-reviewed-deliveries: unpublished doi")
                zfiles = self.files[rec_id]
                z_pdfs = [b for k, b in zfiles.items() if k.endswith(".pdf")]
                z_zips = [b for k, b in zfiles.items() if k.endswith(".zip")]
                if len(z_pdfs) != 1 or len(z_zips) != 1:
                    raise RuntimeError("HTTP 400 from POST /api/v1/pre-reviewed-deliveries: missing zenodo files")
                if hashlib.sha256(z_pdfs[0]).hexdigest() != pdf_sha or hashlib.sha256(z_zips[0]).hexdigest() != src_sha:
                    raise RuntimeError("HTTP 400 from POST /api/v1/pre-reviewed-deliveries: zenodo bytes differ")

            work_id = envelope["work_id"]
            ver = envelope["version"]
            public = {
                "id": work_id,
                "revision": str(ver),
                "previous_version": envelope["previous_version"],
                "kind": envelope["paper"]["kind"],
                "title": envelope["paper"]["title"],
                "repository_url": envelope["paper"].get("repository_url"),
                "issues_url": envelope["paper"].get("issues_url"),
                "version_label": envelope["paper"].get("version_label"),
                "archive": (
                    {"doi": doi, "concept_doi": f"10.5281/zenodo.{self.concept_id}"} if doi else None
                ),
                "pdf": {"url": f"/api/v1/collected-papers/{work_id}/files/pdf?version={ver}"},
                "source": {"url": f"/api/v1/collected-papers/{work_id}/files/source?version={ver}"},
            }
            self.mathesis_works.setdefault(work_id, {})[ver] = public
            return 201, json.dumps({"work_id": work_id, "version": ver, "status": "collected"}).encode("utf-8")

        raise RuntimeError(f"Unhandled Mathesis route: {method} {path}")


class PublishVersionTests(unittest.TestCase):
    def test_deterministic_zip_and_repo_envelope_valid(self):
        zip1 = pv.build_source_zip(REPO_ROOT)
        zip2 = pv.build_source_zip(REPO_ROOT)
        self.assertEqual(zip1, zip2)
        with zipfile.ZipFile(io.BytesIO(zip1)) as zf:
            names = zf.namelist()
            self.assertIn("paper/main.tex", names)
            self.assertIn("mathesis.json", names)
            self.assertTrue(all("__pycache__" not in n for n in names))
            self.assertTrue(all(not n.startswith(".git") for n in names))

        envelope, pdf, source, source_name = pv.prepare_envelope(REPO_ROOT)
        self.assertEqual(envelope["work_id"], "human-in-the-loop-automated-research")
        self.assertEqual(envelope["paper"]["kind"], "methodology")
        self.assertEqual(envelope["paper"]["license"], "CC-BY-4.0")
        self.assertEqual(len(envelope["paper"]["authors"]), 16)
        self.assertIn("Scientific discovery is defined by the ability", envelope["paper"]["abstract"])
        self.assertEqual(source_name, "source-v1.zip")
        self.assertEqual(envelope["review"]["pdf_sha256"], hashlib.sha256(pdf).hexdigest())
        self.assertEqual(envelope["review"]["source_sha256"], hashlib.sha256(source).hexdigest())

    def test_zenodo_creators_preserve_compound_given_names_and_lowercase_license(self):
        envelope, _, _, _ = pv.prepare_envelope(REPO_ROOT)
        zmeta = pv.build_zenodo_metadata(envelope, publication_date="2026-11-28")
        self.assertEqual(zmeta["license"], "cc-by-4.0")
        self.assertEqual(zmeta["upload_type"], "publication")
        self.assertEqual(zmeta["publication_type"], "preprint")
        names = [c["name"] for c in zmeta["creators"]]
        self.assertIn("Lim, Kai Huei", names)
        self.assertIn("Lim, Kai Wei", names)
        self.assertEqual(names[-1], "Zhang, Wenlin")
        self.assertIn("National University of Singapore", zmeta["creators"][-1]["affiliation"])
        self.assertEqual(
            zmeta["related_identifiers"],
            [
                {
                    "relation": "isDerivedFrom",
                    "identifier": "https://github.com/mathesis-papers/human-in-the-loop-automated-research",
                }
            ],
        )

    def test_dry_run_writes_bundle_without_network_or_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = pv.main([str(REPO_ROOT), "--out-dir", tmp, "--dry-run"])
            self.assertEqual(code, 0)
            receipt = json.loads((Path(tmp) / "publication-receipt-v1.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["mode"], "dry-run")
            self.assertTrue((Path(tmp) / "paper.pdf").is_file())
            self.assertTrue((Path(tmp) / "source-v1.zip").is_file())
            self.assertTrue((Path(tmp) / "zenodo-metadata-v1.json").is_file())

    def test_cli_full_v1_recovery_and_v2_without_leaking_tokens(self):
        mock = MockTransport()
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(pv, "http_request", side_effect=mock),
            patch.object(pv.time, "sleep", return_value=None),
        ):
            summary_file = Path(tmp) / "summary.md"
            env = {
                "ZENODO_TOKEN": mock.expected_zenodo_token,
                "MATHESIS_TOKEN": mock.expected_mathesis_token,
                "GITHUB_STEP_SUMMARY": str(summary_file),
                "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
            }
            # 1) Simulate transient Mathesis failure AFTER Zenodo succeeds -> receipt preserves Zenodo DOI.
            mock.fail_mathesis_once = True
            with patch.dict(os.environ, env, clear=False):
                code = pv.main([str(REPO_ROOT), "--out-dir", tmp, "--version", "1", "--version-label", "v1.0", "--auto-previous-version"])
            self.assertEqual(code, 1)
            partial = json.loads((Path(tmp) / "publication-receipt-v1.json").read_text(encoding="utf-8"))
            self.assertEqual(partial["zenodo"]["doi"], "10.5281/zenodo.25000001")
            self.assertIsNone(partial["mathesis"])

            # 2) Recover with --existing-zenodo-doi -> zero new Zenodo POSTs, delivers to Mathesis cleanly.
            calls_before = len(mock.zenodo_calls)
            with patch.dict(os.environ, env, clear=False):
                code = pv.main(
                    [
                        str(REPO_ROOT),
                        "--out-dir",
                        tmp,
                        "--version",
                        "1",
                        "--version-label",
                        "v1.0",
                        "--auto-previous-version",
                        "--existing-zenodo-doi",
                        "10.5281/zenodo.25000001",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(all(m == "GET" for m, _ in mock.zenodo_calls[calls_before:]))
            receipt1 = json.loads((Path(tmp) / "publication-receipt-v1.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt1["mathesis"]["verified_archive_doi"], "10.5281/zenodo.25000001")
            self.assertEqual(
                receipt1["mathesis"]["public_url"],
                "https://mathesis-omega-research.apps.chrono-ai.fun/papers/human-in-the-loop-automated-research?version=1",
            )

            # 3) Publish v2 under same Concept DOI using --previous-zenodo-record-id.
            with patch.dict(os.environ, env, clear=False):
                code = pv.main(
                    [
                        str(REPO_ROOT),
                        "--out-dir",
                        tmp,
                        "--version",
                        "2",
                        "--version-label",
                        "v1.1",
                        "--changelog",
                        "Revised following community feedback.",
                        "--auto-previous-version",
                        "--previous-zenodo-record-id",
                        "25000001",
                    ]
                )
            self.assertEqual(code, 0)
            receipt2 = json.loads((Path(tmp) / "publication-receipt-v2.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt2["zenodo"]["doi"], "10.5281/zenodo.25000002")
            self.assertEqual(receipt2["zenodo"]["concept_doi"], "10.5281/zenodo.25000000")
            self.assertEqual(receipt2["mathesis"]["version"], 2)
            self.assertEqual(mock.mathesis_works["human-in-the-loop-automated-research"][2]["previous_version"], 1)

            # 4) Verify tokens never appear in receipts or step summary.
            summary_text = summary_file.read_text(encoding="utf-8")
            for secret in (mock.expected_zenodo_token, mock.expected_mathesis_token):
                self.assertNotIn(secret, summary_text)
                self.assertNotIn(secret, json.dumps(receipt1))
                self.assertNotIn(secret, json.dumps(receipt2))

    def test_rejects_invalid_tokens_redirects_and_bad_doi_format(self):
        with self.assertRaises(ValueError):
            pv.clean_token("bad\ntoken", "ZENODO_TOKEN")
        with self.assertRaises(ValueError):
            pv.clean_token("   ", "MATHESIS_TOKEN")
        with self.assertRaises(ValueError):
            pv.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.example")
        envelope, _, _, _ = pv.prepare_envelope(REPO_ROOT)
        envelope["paper"]["archive_doi"] = "https://doi.org/10.5281/zenodo.123"
        with self.assertRaises(ValueError):
            pv.validate_envelope(envelope)


if __name__ == "__main__":
    unittest.main()
