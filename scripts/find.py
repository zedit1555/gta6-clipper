"""Search YouTube for GTA 6 videos you are ALLOWED to clip, ranked by views per hour.

    python scripts/find.py                                  # "gta 6", last 72 h
    python scripts/find.py --query "gta 6 police chase" --hours 24 --limit 40
    python scripts/find.py --cc-only                        # Creative Commons only
    python scripts/find.py --auto 2                         # + run moments.py on the 2 best

A video is kept only if:
  - it is under Creative Commons Attribution (CC BY) -> reuse allowed, credit required, or
  - its channel is in creators.json (clipping campaign or written permission).
Everything else is listed as "non autorisé" (with --show-all) and never downloaded.
Results are saved to found.json in the working folder. No API key needed (yt-dlp).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

from common import die, fmt_t, load_creators, permission_for, save_json

CC_FILTER = "EgIwAQ%3D%3D"  # YouTube search filter "Creative Commons"


def search(query: str, limit: int, cc_only: bool) -> list[str]:
    import yt_dlp
    if cc_only:
        target = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={CC_FILTER}"
    else:
        target = f"ytsearchdate{limit}:{query}"  # newest first
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.extract_info(target, download=False)
    urls = []
    for e in res.get("entries") or []:
        vid = e.get("id")
        if vid and (e.get("ie_key") in (None, "Youtube")) and "/shorts/" not in (e.get("url") or ""):
            urls.append(f"https://www.youtube.com/watch?v={vid}")
    return urls[:limit]


def details(url: str) -> dict | None:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"  (ignoré {url}: {str(e).splitlines()[0][:80]})", file=sys.stderr)
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", default="gta 6")
    ap.add_argument("--hours", type=float, default=72, help="âge max des vidéos")
    ap.add_argument("--limit", type=int, default=30, help="nombre de vidéos examinées")
    ap.add_argument("--min-minutes", type=float, default=3, help="durée min (les longues vidéos donnent plus de moments)")
    ap.add_argument("--cc-only", action="store_true", help="chercher seulement en Creative Commons")
    ap.add_argument("--show-all", action="store_true", help="afficher aussi les vidéos non autorisées")
    ap.add_argument("--auto", type=int, default=0, help="lancer moments.py sur les N meilleures autorisées")
    ap.add_argument("--model", default="small", help="modèle Whisper pour --auto")
    args = ap.parse_args()

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        die("yt-dlp n'est pas installé: pip install -r requirements.txt")

    creators = load_creators()
    print(f"Recherche « {args.query} »{' (Creative Commons)' if args.cc_only else ''}, "
          f"{len(creators)} créateur(s) autorisé(s) dans creators.json")
    urls = search(args.query, args.limit, args.cc_only)
    if not urls:
        die("aucun résultat")

    now = time.time()
    rows = []
    for i, url in enumerate(urls, 1):
        print(f"\r  analyse {i}/{len(urls)}", end="", flush=True)
        info = details(url)
        if not info or info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            continue
        ts = info.get("timestamp") or (time.mktime(time.strptime(info["upload_date"], "%Y%m%d"))
                                       if info.get("upload_date") else None)
        age_h = (now - ts) / 3600 if ts else None
        if age_h is not None and age_h > args.hours:
            continue
        dur = info.get("duration") or 0
        if dur < args.min_minutes * 60:
            continue
        kind, detail = permission_for(info, creators)
        views = info.get("view_count") or 0
        rows.append({
            "url": url, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
            "handle": info.get("uploader_id"), "duration": dur, "views": views,
            "age_hours": round(age_h, 1) if age_h is not None else None,
            "views_per_hour": round(views / max(age_h or 1, 1), 1),
            "allowed": bool(kind), "permission": kind, "reason": detail,
            "has_heatmap": bool(info.get("heatmap")),
        })
    print()
    rows.sort(key=lambda r: (not r["allowed"], -r["views_per_hour"]))
    save_json(Path.cwd() / "found.json", {"query": args.query, "searched_at": time.strftime("%Y-%m-%d %H:%M"),
                                          "videos": rows})

    allowed = [r for r in rows if r["allowed"]]
    shown = rows if args.show_all else allowed
    print(f"\n{len(allowed)} autorisée(s) sur {len(rows)} vidéo(s) récente(s)\n")
    if shown:
        print(f"{'#':>2}  {'vues/h':>7}  {'durée':>6}  {'droit':<8}  chaîne / titre")
        for i, r in enumerate(shown, 1):
            droit = {"cc": "CC BY", "allowed": "accord"}.get(r["permission"], "NON")
            print(f"{i:>2}  {r['views_per_hour']:>7.0f}  {fmt_t(r['duration']):>6}  {droit:<8}  "
                  f"{(r['channel'] or '')[:20]} — {(r['title'] or '')[:55]}")
            print(f"    {r['url']}")
    if not allowed:
        print("Aucune vidéo autorisée. Pistes:\n"
              "  - --cc-only et une recherche plus large (\"gta 6 gameplay\", \"gta vi\")\n"
              "  - rejoins une campagne de clipping et ajoute le créateur dans creators.json")
        return

    for r in allowed[:args.auto]:
        print(f"\n=== moments: {r['title']}")
        cmd = [sys.executable, str(Path(__file__).with_name("moments.py")), r["url"], "--top", "5",
               "--model", args.model, "--creator", f"@{(r['handle'] or r['channel'] or '').lstrip('@')}"]
        subprocess.run(cmd)


if __name__ == "__main__":
    main()
