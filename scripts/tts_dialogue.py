"""Synthesize an episode from speaker turns with Gemini multi-speaker TTS.

Each chunk is sent as a single multi-speaker request, so the two voices respond
to each other within the chunk instead of each line being read in isolation —
that turn-awareness is what keeps the result sounding like a conversation.
Google warns that quality drifts after a few minutes of continuous audio, so a
chunk is kept to roughly two minutes and the PCM is concatenated afterwards.

Requires GEMINI_API_KEY.
"""
from __future__ import annotations

import base64
import os
import subprocess
import time
import wave
from pathlib import Path

from google import genai

# Fixed per host so the show stays recognisable episode to episode.
# Kore reads firm and measured (Nadia, who explains); Achird reads friendly and
# conversational (Theo, who questions).
VOICES = {"Nadia": "Kore", "Theo": "Achird"}

MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
MAX_CHUNK_CHARS = 2200
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
CHANNELS = 1
MAX_ATTEMPTS = 4

DIRECTION = """TTS the following conversation between Nadia and Theo, two hosts \
of a podcast for working scientists. Nadia explains the paper: measured, \
precise, unhurried. Theo asks the questions a skeptical colleague would ask: \
curious, direct, a little dry. This is a real conversation between peers, not \
an announcer reading a script. Natural pacing, natural reactions.

"""


def chunk_turns(turns: list[dict], max_chars: int = MAX_CHUNK_CHARS) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for turn in turns:
        length = len(turn["text"])
        if current and size + length > max_chars:
            chunks.append(current)
            current, size = [], 0
        current.append(turn)
        size += length
    if current:
        chunks.append(current)
    return chunks


def render_prompt(chunk: list[dict]) -> str:
    return DIRECTION + "\n".join(f"{t['speaker']}: {t['text']}" for t in chunk)


def synthesize_chunk(client: genai.Client, prompt: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            interaction = client.interactions.create(
                model=MODEL,
                input=prompt,
                response_format={"type": "audio"},
                generation_config={
                    "speech_config": [
                        {"speaker": name, "voice": voice}
                        for name, voice in VOICES.items()
                    ]
                },
            )
            return base64.b64decode(interaction.output_audio.data)
        except Exception as exc:  # noqa: BLE001 - the API 500s occasionally
            last_error = exc
            print(f"    [tts] attempt {attempt + 1} failed: {type(exc).__name__}: {exc}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"chunk failed after {MAX_ATTEMPTS} attempts: {last_error}")


def write_wave(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


def synthesize(turns: list[dict], wav_path: Path) -> float:
    """Render all turns to a wav. Returns duration in seconds."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set")
    chunks = chunk_turns(turns)
    print(f"  [tts] {len(turns)} turns -> {len(chunks)} chunks [{MODEL}]")
    client = genai.Client()
    audio = bytearray()
    for i, chunk in enumerate(chunks, 1):
        chars = sum(len(t["text"]) for t in chunk)
        print(f"    [{i}/{len(chunks)}] {chars} chars")
        audio.extend(synthesize_chunk(client, render_prompt(chunk)))
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    write_wave(wav_path, bytes(audio))
    seconds = len(audio) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
    print(f"  [tts] wrote {wav_path.name} — {seconds / 60:.1f} min")
    return seconds


def to_mp3(wav_path: Path, mp3_path: Path, *, doi: str = "", title: str = "") -> None:
    """Encode to mp3, stamping the DOI in the comment tag.

    publish_episode.py reads that comment to pair the audio with its Issue and
    to pull canonical metadata from CrossRef, so the tag is what links this
    episode back to its paper.
    """
    comment = f"DOI: {doi}" if doi else ""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path)]
    if title:
        cmd += ["-metadata", f"title={title}"]
    if comment:
        cmd += ["-metadata", f"comment={comment}"]
    cmd += ["-b:a", "128k", "-ac", "1", str(mp3_path)]
    subprocess.run(cmd, check=True)
    print(f"  [tts] encoded {mp3_path.name} ({mp3_path.stat().st_size / 1e6:.1f} MB)")
