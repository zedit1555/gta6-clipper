"""Create a job from a local video file or a link.

    python scripts/fetch.py "D:/captures/session1.mp4" --creator "@moi"
    python scripts/fetch.py "https://www.youtube.com/watch?v=..." --creator "@streamer"

Local files are not copied: the job just points to them.
Links are downloaded with yt-dlp (max 1080p). Only clip creators who allow it
(their own clipping campaign, or written permission).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import JOBS_DIR, die, is_url, new_job_id, probe, save_json


def fetch_url(url: str, job: Path) -> dict:
    try:
        import yt_dlp
    except ImportError:
        die("yt-dlp n'est pas installé: pip install -r requirements.txt")
    opts = {
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(job / "source.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    files = sorted(job.glob("source.*"))
    if not files:
        die("téléchargement terminé mais aucun fichier trouvé")
    heat = [
        {"start": h.get("start_time"), "end": h.get("end_time"), "value": h.get("value")}
        for h in (info.get("heatmap") or [])
    ]
    return {
        "source": str(files[0].resolve()),
        "url": url,
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "uploader_url": info.get("uploader_url") or info.get("channel_url"),
        "heatmap": heat,  # YouTube "most replayed", if available
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="chemin d'un fichier vidéo ou lien")
    ap.add_argument("--creator", help="crédit à afficher, ex: @streamer (sinon: nom de la chaîne)")
    ap.add_argument("--id", help="nom du job (sinon généré)")
    args = ap.parse_args()

    if is_url(args.source):
        job = JOBS_DIR / (args.id or new_job_id(args.source.split("/")[-1]))
        job.mkdir(parents=True, exist_ok=True)
        print("Téléchargement...")
        meta = fetch_url(args.source, job)
    else:
        src = Path(args.source).expanduser().resolve()
        if not src.is_file():
            die(f"fichier introuvable: {src}")
        job = JOBS_DIR / (args.id or new_job_id(src.stem))
        job.mkdir(parents=True, exist_ok=True)
        meta = {"source": str(src), "url": None, "title": src.stem,
                "uploader": None, "uploader_url": None, "heatmap": []}

    info = probe(Path(meta["source"]))
    if not info["width"]:
        die("aucune piste vidéo dans ce fichier")
    meta.update(info)
    meta["creator"] = args.creator or (f"@{meta['uploader']}" if meta.get("uploader") else None)
    save_json(job / "meta.json", meta)
    (job / "edits").mkdir(exist_ok=True)

    print(f"Job prêt: {job}")
    print(f"  {meta['width']}x{meta['height']}  {meta['duration']:.0f}s  "
          f"audio={'oui' if meta['has_audio'] else 'non'}  crédit={meta['creator'] or '(à définir)'}")
    if meta["heatmap"]:
        print(f"  'most replayed' YouTube: {len(meta['heatmap'])} points")
    print(f"Suite: python scripts/moments.py {job}")


if __name__ == "__main__":
    main()
