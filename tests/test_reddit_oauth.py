"""Getting into r/science from a server, which Reddit does not allow for free.

Reddit 403s datacenter IPs — every GitHub runner — on the public JSON
endpoint whatever User-Agent you send. On 2026-11-19 that cost the Friday
episode its strand: the crawl was blocked, the RSS fallback answered 404, and
the slot fell through to PubMed trending.

The fallback had never worked. `/r/science/top.rss?t=week` returns Reddit's
"Not Found" feed for every client, a browser included, because sorted RSS
listings no longer exist — so it burned a request to produce a guaranteed
404 while logging "trying RSS" as though it might succeed. It is gone, and
application-only OAuth is the way in.

Nothing here touches the network.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import reddit_source  # noqa: E402

LISTING = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "A paper about engagers",
                    "author": "someone",
                    "url": "https://doi.org/10.1038/s41586-026-00001-0",
                    "permalink": "/r/science/comments/abc/",
                    "score": 4321,
                    "num_comments": 210,
                    "created_utc": 0,  # old enough to pass the age filter
                    "link_flair_text": "Biology",
                }
            }
        ]
    }
}

CREDENTIALS = {"REDDIT_CLIENT_ID": "id-123", "REDDIT_CLIENT_SECRET": "secret-456"}


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def raise_for_status(self):
        if self.status >= 400:
            raise reddit_source.requests.HTTPError(f"{self.status} Client Error")

    def json(self):
        return self.payload


class TokenTests(unittest.TestCase):
    def test_the_token_call_is_a_client_credentials_grant(self):
        seen = {}

        def post(url, **kwargs):
            seen.update(url=url, **kwargs)
            return Response({"access_token": "tok", "token_type": "bearer"})

        with mock.patch.dict("os.environ", CREDENTIALS), \
                mock.patch.object(reddit_source.requests, "post", post):
            self.assertEqual(reddit_source._app_only_token(), "tok")
        self.assertEqual(seen["url"], "https://www.reddit.com/api/v1/access_token")
        self.assertEqual(seen["auth"], ("id-123", "secret-456"))
        self.assertEqual(seen["data"], {"grant_type": "client_credentials"})
        # Reddit refuses a request with no descriptive User-Agent.
        self.assertIn("ScienceTLDR", seen["headers"]["User-Agent"])

    def test_missing_credentials_say_which_ones(self):
        with mock.patch.dict("os.environ", {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}):
            with self.assertRaises(RuntimeError) as caught:
                reddit_source._app_only_token()
        self.assertIn("REDDIT_CLIENT_ID", str(caught.exception))

    def test_a_token_response_without_a_token_is_an_error(self):
        with mock.patch.dict("os.environ", CREDENTIALS), \
                mock.patch.object(reddit_source.requests, "post", lambda *a, **k: Response({})):
            with self.assertRaises(RuntimeError):
                reddit_source._app_only_token()

    def test_a_refused_token_is_not_swallowed(self):
        # If the app type or secret is wrong, the run must say so rather than
        # quietly producing no posts, which would read as "reddit had nothing".
        with mock.patch.dict("os.environ", CREDENTIALS), \
                mock.patch.object(
                    reddit_source.requests, "post", lambda *a, **k: Response({}, status=401)
                ):
            with self.assertRaises(reddit_source.requests.HTTPError):
                reddit_source.fetch_top_week()


class RouteTests(unittest.TestCase):
    def test_with_credentials_it_uses_oauth_and_bearer_auth(self):
        seen = {}

        def get(url, **kwargs):
            seen.update(url=url, **kwargs)
            return Response(LISTING)

        with mock.patch.dict("os.environ", CREDENTIALS), \
                mock.patch.object(reddit_source, "_app_only_token", lambda: "tok"), \
                mock.patch.object(reddit_source.requests, "get", get):
            posts = reddit_source.fetch_top_week(limit=50)
        self.assertEqual(seen["url"], "https://oauth.reddit.com/r/science/top")
        self.assertEqual(seen["params"], {"t": "week", "limit": 50})
        self.assertEqual(seen["headers"]["Authorization"], "bearer tok")
        self.assertEqual([p.title for p in posts], ["A paper about engagers"])
        self.assertEqual(posts[0].score, 4321, "OAuth keeps the metadata RSS lost")

    def test_without_credentials_it_uses_the_public_endpoint(self):
        # Which is what a laptop has, and it works there.
        seen = {}

        def get(url, **kwargs):
            seen.update(url=url)
            return Response(LISTING)

        with mock.patch.dict("os.environ", {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}), \
                mock.patch.object(reddit_source.requests, "get", get):
            posts = reddit_source.fetch_top_week()
        self.assertEqual(seen["url"], "https://www.reddit.com/r/science/top.json")
        self.assertEqual(len(posts), 1)

    def test_both_routes_filter_identically(self):
        # One parser, so a post dropped by one route is dropped by the other.
        hidden = {"data": {"children": [
            {"data": dict(LISTING["data"]["children"][0]["data"], stickied=True)},
            {"data": dict(LISTING["data"]["children"][0]["data"], is_self=True)},
            {"data": dict(LISTING["data"]["children"][0]["data"], author="[deleted]")},
        ]}}
        self.assertEqual(reddit_source._posts_from_listing(hidden), [])
        self.assertEqual(len(reddit_source._posts_from_listing(LISTING)), 1)

    def test_an_empty_listing_is_not_a_crash(self):
        self.assertEqual(reddit_source._posts_from_listing({}), [])


class NoDeadFallbackTests(unittest.TestCase):
    def test_the_rss_route_is_gone(self):
        # It answered "Not Found" for every client, browsers included.
        self.assertFalse(hasattr(reddit_source, "_fetch_top_week_rss"))
        self.assertFalse(hasattr(reddit_source, "REDDIT_RSS_URL"))
        # No *request* to an rss URL; the comments still explain why not.
        source = Path(reddit_source.__file__).read_text(encoding="utf-8")
        self.assertNotRegex(source, r'^[A-Z_]+ = "https://\S+\.rss"', )

    def test_the_workflow_passes_the_credentials(self):
        workflow = (
            Path(__file__).resolve().parent.parent
            / ".github" / "workflows" / "friday-podcast.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}", workflow)
        self.assertIn("REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}", workflow)


if __name__ == "__main__":
    unittest.main()
