"""Regenerate feed.xml from channel.json + episodes/*.json.

Idempotent: running it twice produces byte-identical output (modulo episode order
when disk listing differs). The feed includes both itunes: and podcast: (Podcasting
2.0) namespaces so listening apps and the Podcast Index treat the migrated feed as
the same show as the rss.com original.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from lxml import etree

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "podcast": "https://podcastindex.org/namespace/1.0",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}

ROOT = Path(__file__).resolve().parent.parent
CHANNEL_PATH = ROOT / "channel.json"
EPISODES_DIR = ROOT / "episodes"
OUTPUT_PATH = ROOT / "feed.xml"


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _sub(parent, tag: str, text: str | None = None, attrib: dict | None = None):
    el = etree.SubElement(parent, tag, attrib=attrib or {})
    if text is not None:
        el.text = text
    return el


def _cdata(parent, tag: str, text: str, attrib: dict | None = None):
    el = etree.SubElement(parent, tag, attrib=attrib or {})
    el.text = etree.CDATA(text)
    return el


def build_feed(channel: dict, episodes: list[dict], base_url: str) -> bytes:
    rss = etree.Element(
        "rss",
        nsmap=NS,
        attrib={"version": "2.0"},
    )
    ch = _sub(rss, "channel")

    _sub(ch, _q("atom", "link"), attrib={
        "href": f"{base_url}feed.xml",
        "rel": "self",
        "type": "application/rss+xml",
    })

    _cdata(ch, "title", channel["title"])
    _sub(ch, "link", channel.get("link", base_url))
    _cdata(ch, "description", channel["description"])
    _sub(ch, "language", channel.get("language", "en"))
    _sub(ch, "copyright", channel.get("copyright", f"© {channel.get('author', '')}"))
    _sub(ch, "lastBuildDate", episodes[-1]["pub_date"] if episodes else "")
    _sub(ch, "generator", "sciencetldr/feed_builder.py")

    _sub(ch, _q("itunes", "author"), channel["author"])
    _sub(ch, _q("itunes", "type"), channel.get("itunes_type", "episodic"))
    _sub(ch, _q("itunes", "explicit"), str(channel.get("explicit", "false")).lower())

    owner = _sub(ch, _q("itunes", "owner"))
    _sub(owner, _q("itunes", "name"), channel["owner_name"])
    _sub(owner, _q("itunes", "email"), channel["owner_email"])

    _sub(ch, _q("itunes", "image"), attrib={"href": f"{base_url}cover.jpg"})

    cat_attrib = {"text": channel["category"]}
    _sub(ch, _q("itunes", "category"), attrib=cat_attrib)

    image = _sub(ch, "image")
    _sub(image, "url", f"{base_url}cover.jpg")
    _sub(image, "title", channel["title"])
    _sub(image, "link", channel.get("link", base_url))

    _sub(ch, _q("podcast", "guid"), channel["podcast_guid"])
    _sub(ch, _q("podcast", "locked"),
         channel.get("podcast_locked", "yes"),
         attrib={"owner": channel["owner_email"]})
    _sub(ch, _q("podcast", "medium"), "podcast")
    if channel.get("podcast_license"):
        _sub(ch, _q("podcast", "license"), channel["podcast_license"])

    for ep in sorted(episodes, key=lambda e: e["episode_number"]):
        item = _sub(ch, "item")
        _cdata(item, "title", ep["title"])
        if ep.get("itunes_title"):
            _cdata(item, _q("itunes", "title"), ep["itunes_title"])
        _cdata(item, "description", ep["description"])
        _sub(item, "link", f"{base_url}#episode-{ep['episode_number']:03d}")
        enclosure_url = f"{base_url}episodes/{ep['enclosure_filename']}"
        _sub(item, "enclosure", attrib={
            "url": enclosure_url,
            "length": str(ep["enclosure_length_bytes"]),
            "type": "audio/mpeg",
        })
        _sub(item, "guid", ep["guid"], attrib={"isPermaLink": "false"})
        _sub(item, _q("itunes", "duration"), str(ep["duration_seconds"]))
        _sub(item, _q("itunes", "episodeType"), ep.get("episode_type", "full"))
        _sub(item, _q("itunes", "episode"), str(ep["episode_number"]))
        _sub(item, _q("podcast", "episode"), str(ep["episode_number"]))
        _sub(item, _q("itunes", "explicit"), str(ep.get("explicit", "false")).lower())
        _sub(item, "pubDate", ep["pub_date"])

    return etree.tostring(rss, pretty_print=True, xml_declaration=True, encoding="UTF-8")


def main() -> None:
    channel = json.loads(CHANNEL_PATH.read_text(encoding="utf-8"))
    episodes = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in EPISODES_DIR.glob("*.json")
    ]
    base_url = channel["base_url"]
    if not base_url.endswith("/"):
        base_url += "/"
    xml = build_feed(channel, episodes, base_url)
    OUTPUT_PATH.write_bytes(xml)
    print(f"Wrote {OUTPUT_PATH} with {len(episodes)} episodes")


if __name__ == "__main__":
    main()
