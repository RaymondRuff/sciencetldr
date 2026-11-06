"""Actions stages each paper where the writer routine can read it.

The routines cannot reach any paper source, so the sweep and the pickers
fetch what is open and put it in the private papers repository. These tests
cover the fetch, the staging, and what the sweep does about the rest: ask for
a PDF once, and never when asking could not help.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import requests  # noqa: E402

import generate_episode as ge  # noqa: E402
import paper_bundle  # noqa: E402
import paper_text  # noqa: E402

BODY = "Methods. We measured things carefully and at length. " * 400  # ~21k chars
ABSTRACT_PAGE = (
    "Abstract. Background: a question. Methods: a cohort. Results: a finding.\n"
    "References\n" + "Smith J. A paper. J Stuff. 2020;1:1-2.\n" * 400
)


class FakeResponse:
    def __init__(self, *, status=200, content=b"", payload=None, text=""):
        self.status_code = status
        self.content = content
        self.text = text or content.decode("latin-1")
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self._payload


def route(table):
    """A requests.get that answers by URL prefix; anything unlisted is a 404."""

    def get(url, **kwargs):
        for prefix, answer in table.items():
            if url.startswith(prefix):
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return FakeResponse(status=404)

    return get


def pmc_record(*, open_access: bool):
    return FakeResponse(
        payload={
            "resultList": {
                "result": [
                    {
                        "pmcid": "PMC123",
                        "inPMC": "Y",
                        "isOpenAccess": "Y" if open_access else "N",
                    }
                ]
            }
        }
    )


class FetchOpenTextTests(unittest.TestCase):
    def setUp(self):
        # Turning bytes into text is pypdf's job and tested elsewhere.
        patcher = mock.patch.object(
            paper_text,
            "pdf_bytes_to_text",
            lambda data: BODY if data.startswith(b"%PDF") else None,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, table, **kwargs):
        with mock.patch.object(paper_text.requests, "get", route(table)):
            return paper_text.fetch_open_text(**kwargs)

    def test_an_open_pdf_is_kept_as_a_pdf_for_its_figures(self):
        found = self.fetch(
            {"https://oa.example/paper.pdf": FakeResponse(content=b"%PDF-1.7 ...")},
            doi="10.1/x",
            pdf_url="https://oa.example/paper.pdf",
        )
        self.assertEqual(found.provenance, "pdf-url")
        self.assertTrue(found.pdf.startswith(b"%PDF"))

    def test_a_publisher_answering_html_for_a_pdf_link_is_not_a_pdf(self):
        found = self.fetch(
            {"https://oa.example/paper.pdf": FakeResponse(content=b"<html>login</html>")},
            pdf_url="https://oa.example/paper.pdf",
        )
        self.assertIsNone(found)

    def test_europe_pmc_open_access_pdf_comes_before_its_xml(self):
        found = self.fetch(
            {
                paper_text.EUROPEPMC + "/search": pmc_record(open_access=True),
                paper_text.EUROPEPMC_PDF: FakeResponse(content=b"%PDF-1.5"),
            },
            doi="10.1/x",
        )
        self.assertEqual(found.provenance, "europepmc-pdf:PMC123")
        self.assertIsNotNone(found.pdf)

    def test_europe_pmc_xml_when_there_is_no_pdf(self):
        xml = f"<article><body><p>{BODY}</p></body></article>".encode()
        found = self.fetch(
            {
                paper_text.EUROPEPMC + "/search": pmc_record(open_access=False),
                paper_text.EUROPEPMC + "/PMC123/fullTextXML": FakeResponse(content=xml),
            },
            doi="10.1/x",
        )
        self.assertEqual(found.provenance, "europepmc:PMC123")
        self.assertIsNone(found.pdf)

    def test_an_abstract_and_its_references_is_refused(self):
        # A paywalled landing page clears the old length check easily; staging
        # it would have the writer build an episode on the abstract.
        page = f"<html><body><article>{ABSTRACT_PAGE}</article></body></html>"
        found = self.fetch(
            {
                paper_text.EUROPEPMC + "/search": FakeResponse(payload={"resultList": {}}),
                "https://doi.org/": FakeResponse(text=page, content=page.encode()),
            },
            doi="10.1/x",
        )
        self.assertIsNone(found)
        self.assertGreater(len(ABSTRACT_PAGE), paper_text.MIN_USEFUL_CHARS)

    def test_a_source_that_is_down_is_not_a_missing_paper(self):
        with self.assertRaises(paper_text.TransientFetchError):
            self.fetch(
                {
                    paper_text.EUROPEPMC: requests.ConnectionError("reset"),
                    "https://doi.org/": requests.ConnectionError("reset"),
                },
                doi="10.1/x",
            )


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class StagingTests(unittest.TestCase):
    """Against a throwaway papers repository, never the real one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.remote = tmp / "papers.git"
        seed = tmp / "seed"
        git("init", "-q", "--bare", "-b", "main", str(self.remote), cwd=tmp)
        git("clone", "-q", str(self.remote), str(seed), cwd=tmp)
        (seed / "README.md").write_text("staging\n")
        git("add", "README.md", cwd=seed)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)

        remote, real = str(self.remote), paper_bundle.PapersRepo
        patcher = mock.patch.object(paper_bundle, "PapersRepo", lambda repo=remote: real(repo))
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(
            os.environ,
            {"PAPER_BUNDLE_DIR": str(tmp / "cache"), "PAPERS_DIR": str(tmp / "nowhere")},
        )
        env.start()
        self.addCleanup(env.stop)

    def published(self) -> list[str]:
        out = subprocess.run(
            ["git", "--git-dir", str(self.remote), "ls-tree", "-r", "--name-only", "main"],
            capture_output=True, text=True, check=True,
        ).stdout
        return out.split()

    def test_text_becomes_a_bundle_without_figures(self):
        fetched = paper_text.Fetched(BODY, "europepmc:PMC123")
        meta = paper_bundle.stage(41, fetched, doi="10.1/x", title="A paper")
        self.assertEqual(meta["figures"], [])
        self.assertEqual(meta["provenance"], "fetched:europepmc:PMC123")
        self.assertIn("papers/issue-41/paper.txt", self.published())
        self.assertIn("papers/issue-41/meta.json", self.published())
        self.assertEqual(paper_bundle.bundled_issues(), {41})

    def test_a_supplied_bundle_is_never_replaced_by_a_fetched_one(self):
        paper_bundle.stage(41, paper_text.Fetched(BODY, "first"))
        again = paper_bundle.stage(41, paper_text.Fetched("other " * 3000, "second"))
        self.assertIsNone(again)
        out = tempfile.mkdtemp(dir=self._tmp.name)
        meta = paper_bundle.fetch(41, Path(out))
        self.assertEqual(meta["provenance"], "fetched:first")

    def test_nothing_to_stage_touches_nothing(self):
        self.assertEqual(paper_bundle.stage_many([]), {})
        self.assertEqual(self.published(), ["README.md"])


class DeniedTests(unittest.TestCase):
    def test_a_token_without_the_repository_is_named_as_such(self):
        refused = subprocess.CompletedProcess(
            [], 128, "",
            "remote: Write access to repository not granted.\n"
            "fatal: unable to access '...': The requested URL returned error: 403",
        )
        with mock.patch.object(paper_bundle.subprocess, "run", return_value=refused):
            with self.assertRaises(paper_bundle.PapersRepoDenied):
                with paper_bundle.PapersRepo("RaymondRuff/sciencetldr-papers"):
                    pass

    def test_other_git_failures_stay_ordinary(self):
        broken = subprocess.CompletedProcess([], 1, "", "fatal: not a git repository")
        with mock.patch.object(paper_bundle.subprocess, "run", return_value=broken):
            with self.assertRaises(RuntimeError) as caught:
                with paper_bundle.PapersRepo("RaymondRuff/sciencetldr-papers"):
                    pass
        self.assertNotIsInstance(caught.exception, paper_bundle.PapersRepoDenied)


def an_issue(number, *labels, doi=""):
    meta = {"title": f"Paper {number}", "doi": doi or f"10.1/{number}", "pdf_url": None}
    body = (
        "<!-- METADATA -->\n```json\n" + json.dumps(meta) + "\n```\n<!-- /METADATA -->"
    )
    return {
        "number": number,
        "title": f"Paper {number}",
        "labels": [{"name": n} for n in ("podcast-pending", *labels)],
        "body": body,
    }


class SweepTests(unittest.TestCase):
    """What the sweep stages, and what it asks Ray for."""

    def setUp(self):
        self.calls: list[tuple] = []
        patches = [
            mock.patch.object(ge, "routine_script", lambda n: "script" if n == 90 else None),
            mock.patch.object(ge, "remove_label", lambda n, l: self.calls.append(("unlabel", n, l))),
            mock.patch.object(ge, "request_pdf", lambda issue, meta: self.calls.append(("ask", issue["number"]))),
            mock.patch.object(ge.github_issue, "comment", lambda n, body: self.calls.append(("comment", n))),
            mock.patch.object(ge.pdf_mailbox, "mark_processed", lambda n: self.calls.append(("consume", n))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def sweep(self, issues, *, synced=None, fetched=None, denied=False):
        fetched = fetched or {}

        def sync_all(items):
            if denied:
                raise paper_bundle.PapersRepoDenied("403")
            return synced or {}

        def fetch_open_text(*, doi, pdf_url):
            answer = fetched.get(doi)
            if isinstance(answer, Exception):
                raise answer
            return answer

        def stage_many(items):
            self.staged = [i["issue"] for i in items]
            return {i["issue"]: {"provenance": "fetched"} for i in items}

        with mock.patch.object(paper_bundle, "sync_all", sync_all), \
             mock.patch.object(paper_bundle, "stage_many", stage_many), \
             mock.patch.object(ge.paper_text, "fetch_open_text", fetch_open_text):
            return ge.bundle_waiting_papers(issues)

    def test_open_papers_are_staged_and_a_scripted_one_is_left_alone(self):
        issues = [an_issue(40), an_issue(41), an_issue(90)]
        bundled = self.sweep(issues, fetched={"10.1/41": paper_text.Fetched(BODY, "x")})
        self.assertEqual(set(bundled), {41})
        self.assertEqual(self.staged, [41])
        self.assertTrue(ge.PapersState.reached)

    def test_a_paper_that_turns_up_clears_its_pdf_request_once(self):
        issues = [an_issue(58, "needs-pdf", "pdf-requested")]
        self.sweep(issues, fetched={"10.1/58": paper_text.Fetched(BODY, "x")})
        self.assertIn(("unlabel", 58, "needs-pdf"), self.calls)
        self.assertIn(("unlabel", 58, "pdf-requested"), self.calls)
        self.assertEqual(self.calls.count(("comment", 58)), 1)

    def test_each_missing_paper_is_asked_for_once(self):
        issues = [
            an_issue(40),                      # nothing open: ask
            an_issue(43, "pdf-requested"),     # already asked: the label is the memory
            an_issue(44),                      # a source was down: ask later, not now
            an_issue(41),                      # staged: nothing to ask
            an_issue(90, "needs-pdf"),         # checked script waiting: needs no paper
        ]
        bundled = self.sweep(
            issues,
            fetched={
                "10.1/41": paper_text.Fetched(BODY, "x"),
                "10.1/44": paper_text.TransientFetchError("timeout"),
            },
        )
        ge.request_missing_pdfs(issues, bundled)
        self.assertEqual([c for c in self.calls if c[0] == "ask"], [("ask", 40)])

    def test_a_pdf_arriving_in_its_window_closes_the_window(self):
        issues = [an_issue(43, "needs-pdf", "pdf-requested", "awaiting-pdf")]
        self.sweep(issues, synced={43: {"provenance": "emailed-pdf"}})
        for label in ("needs-pdf", "pdf-requested", "awaiting-pdf"):
            self.assertIn(("unlabel", 43, label), self.calls)

    def test_an_open_window_is_never_asked_about_a_second_time(self):
        # The picker sent the one request, with its deadline; even if that
        # email failed, the sweep does not send another while the window runs.
        issues = [an_issue(43, "needs-pdf", "awaiting-pdf")]
        bundled = self.sweep(issues)
        ge.request_missing_pdfs(issues, bundled)
        self.assertEqual([c for c in self.calls if c[0] == "ask"], [])

    def test_no_pdf_is_asked_for_while_the_papers_repository_is_shut(self):
        # A supplied PDF could not reach the routine either, so the one useful
        # message is the token fix, which the run's exit carries.
        issues = [an_issue(40), an_issue(41)]
        bundled = self.sweep(issues, denied=True)
        ge.request_missing_pdfs(issues, bundled)
        self.assertEqual(bundled, {})
        self.assertFalse(ge.PapersState.reached)
        self.assertTrue(ge.PapersState.denied)
        self.assertEqual([c for c in self.calls if c[0] == "ask"], [])

    def test_an_emailed_pdf_is_only_consumed_once_it_cannot_be_lost(self):
        ge.PapersState.reached = False
        ge.consume_replies({40: {}, 41: {}, 77: {}}, {40, 41}, {41: {}})
        # 41 is staged; 77's Issue is gone; 40 must wait for a reachable repo.
        self.assertEqual(
            sorted(c for c in self.calls if c[0] == "consume"),
            [("consume", 41), ("consume", 77)],
        )

    def test_a_pdf_that_will_not_bundle_is_consumed_and_said_so(self):
        ge.PapersState.reached = True
        ge.consume_replies({40: {}}, {40}, {})
        self.assertIn(("consume", 40), self.calls)
        self.assertIn(("comment", 40), self.calls)


if __name__ == "__main__":
    unittest.main()
