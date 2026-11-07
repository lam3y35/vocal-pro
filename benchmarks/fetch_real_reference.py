#!/usr/bin/env python
"""Download real freely licensed music from Wikimedia Commons and cut 30 s excerpts.

Audio is NOT committed (see .gitignore); only MANIFEST.json (source URL, license, author,
sha256 of the downloaded source file and of the excerpt) is committed.
Usage: python benchmarks/fetch_real_reference.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent / "reference-real"
UA = {"User-Agent": "vocalpro-verification/1.0 (https://github.com/lam3y35/vocal-pro-rebuild)"}
EXCERPT_S = 30.0

TRACKS = [
    ("real_01", "File:David Mumford - 04 - The Shelby Blues.ogg", 20.0, "blues, vocal + guitar band, stereo"),
    ("real_02", "File:The Rope River Blues Band - 02 - The Vistas Missing Views.ogg", 40.0, "blues-rock band with vocals, stereo"),
    ("real_03", "File:Rainy weather blues-Columbia 14037-D-Bessie Smith.mp3", 20.0, "1920s shellac recording, lead vocal, noisy mono-like source"),
    ("real_04", "File:Skyscrapers - Airmen of Note - United States Air Force Band.mp3", 30.0, "big-band jazz, dense brass, mostly instrumental"),
    ("real_05", "File:Friendly Evil Gangsta Synth Hip Hop.ogg", 20.0, "synth hip-hop, strong bass/drums"),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for tid, title, start, desc in TRACKS:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params=dict(action="query", titles=title, prop="imageinfo", iiprop="url|extmetadata|size", format="json"),
            headers=UA, timeout=30,
        ).json()
        page = next(iter(r["query"]["pages"].values()))
        ii = page["imageinfo"][0]
        md = ii["extmetadata"]
        src = OUT / f"{tid}_source{Path(urllib.parse.urlparse(ii['url']).path).suffix}"
        if not src.exists():
            with requests.get(ii["url"], headers=UA, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with src.open("wb") as f:
                    for chunk in resp.iter_content(1 << 20):
                        f.write(chunk)
        wav = OUT / f"{tid}_excerpt30s.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", str(EXCERPT_S), "-i", str(src),
             "-ar", "44100", "-c:a", "pcm_s16le", str(wav)], check=True)
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(src)],
            capture_output=True, text=True, check=True).stdout)["streams"][0]
        manifest.append({
            "id": tid, "description": desc, "commons_title": title,
            "source_url": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "download_url": ii["url"].split("?")[0],
            "license": md.get("LicenseShortName", {}).get("value"),
            "license_url": md.get("LicenseUrl", {}).get("value"),
            "artist": md.get("Artist", {}).get("value"),
            "source_codec": probe.get("codec_name"), "source_sample_rate": probe.get("sample_rate"),
            "source_channels": probe.get("channels"),
            "source_sha256": sha256(src), "excerpt_start_s": start, "excerpt_len_s": EXCERPT_S,
            "excerpt_sha256": sha256(wav),
        })
        print(tid, manifest[-1]["license"], manifest[-1]["source_codec"], manifest[-1]["source_channels"])
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
