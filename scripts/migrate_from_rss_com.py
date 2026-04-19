"""One-shot migration: pull all episodes off rss.com into this repo.

Run locally (not in Actions). Downloads every MP3 from the source rss.com feed,
writes per-episode JSON sidecars with GUIDs preserved byte-for-byte, captures
channel metadata to channel.json, and downloads the cover image. After this
finishes, run feed_builder.py to produce feed.xml.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from lxml import etree
from slugify import slugify

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "episodes"
CHANNEL_PATH = ROOT / "channel.json"
COVER_PATH = ROOT / "cover.jpg"

SOURCE_FEED = "https://media.rss.com/sciencetldr/feed.xml"
NEW_BASE_URL = "https://raymondruff.github.io/sciencetldr/"

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "podcast": "https://podcastindex.org/namespace/1.0",
    "atom": "http://www.w3.org/2005/Atom",
}


def _t(el, xpath: str, default: str = "") -> str:
    found = el.find(xpath, namespaces=NS)
    if found is None:
        return default
    return (found.text or "").strip()


def _attr(el, xpath: str, attr: str, default: str = "") -> str:
    found = el.find(xpath, namespaces=NS)
    if found is None:
        return default
    return found.get(attr, default)


def parse_duration_seconds(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    if ":" in value:
        parts = [int(p) for p in value.split(":")]
        seconds = 0
        for p in parts:
            seconds = seconds * 60 + p
        return seconds
    return int(value)


def download(url: str, dest: Path) -> int:
    print(f"  ↓ {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
    return dest.stat().st_size


def safe_slug(text: str, max_length: int = 60) -> str:
    return slugify(text, max_length=max_length, word_boundary=True, save_order=True)


def main() -> None:
    print(f"Fetching feed: {SOURCE_FEED}")
    resp = requests.get(SOURCE_FEED, timeout=60)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)
    channel = root.find("channel")
    if channel is None:
        sys.exit("No <channel> in feed")

    owner = channel.find("itunes:owner", namespaces=NS)
    owner_name = _t(owner, "itunes:name") if owner is not None else ""
    owner_email = _t(owner, "itunes:email") if owner is not None else ""

    channel_meta = {
        "title": _t(channel, "title"),
        "description": _t(channel, "description"),
        "link": NEW_BASE_URL,
        "language": _t(channel, "language", "en"),
        "copyright": _t(channel, "copyright"),
        "author": _t(channel, "itunes:author"),
        "itunes_type": _t(channel, "itunes:type", "episodic"),
        "explicit": _t(channel, "itunes:explicit", "false"),
        "owner_name": owner_name,
        "owner_email": owner_email,
        "category": _attr(channel, "itunes:category", "text"),
        "podcast_guid": _t(channel, "podcast:guid"),
        "podcast_locked": _t(channel, "podcast:locked", "yes"),
        "podcast_license": _t(channel, "podcast:license"),
        "base_url": NEW_BASE_URL,
    }
    CHANNEL_PATH.write_text(
        json.dumps(channel_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {CHANNEL_PATH}")

    cover_url = _attr(channel, "itunes:image", "href")
    if cover_url and not COVER_PATH.exists():
        download(cover_url, COVER_PATH)
        print(f"Wrote {COVER_PATH}")

    items = channel.findall("item")
    print(f"\nFound {len(items)} episodes\n")
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)

    for i, item in enumerate(items, 1):
        title = _t(item, "title")
        episode_num_str = _t(item, "itunes:episode") or str(len(items) - i + 1)
        episode_num = int(episode_num_str)
        slug = safe_slug(title) or f"episode-{episode_num:03d}"
        base_name = f"{episode_num:03d}-{slug}"
        mp3_path = EPISODES_DIR / f"{base_name}.mp3"
        json_path = EPISODES_DIR / f"{base_name}.json"

        print(f"[{i}/{len(items)}] Episode {episode_num}: {title[:60]}")

        enclosure = item.find("enclosure")
        if enclosure is None:
            print("  ! no enclosure, skipping")
            continue
        mp3_url = enclosure.get("url")

        if mp3_path.exists():
            length_bytes = mp3_path.stat().st_size
            print(f"  ✓ already downloaded ({length_bytes} bytes)")
        else:
            length_bytes = download(mp3_url, mp3_path)
            time.sleep(0.5)

        meta = {
            "guid": _t(item, "guid"),
            "title": title,
            "itunes_title": _t(item, "itunes:title") or title,
            "description": _t(item, "description"),
            "pub_date": _t(item, "pubDate"),
            "duration_seconds": parse_duration_seconds(_t(item, "itunes:duration")),
            "episode_number": episode_num,
            "episode_type": _t(item, "itunes:episodeType", "full"),
            "explicit": _t(item, "itunes:explicit", "false"),
            "enclosure_filename": mp3_path.name,
            "enclosure_length_bytes": length_bytes,
            "source": "migrated_from_rss.com",
        }
        json_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(f"\nDone. Now run: uv run python scripts/feed_builder.py")


if __name__ == "__main__":
    main()
