"""Check a clip (and its post text) against the rules before you post it.

    python scripts/check.py jobs/<id>/edits/clip_2.mp4
    python scripts/check.py jobs/<id>/edits/clip_2.mp4 --campaign campaigns/example.json \
        --caption "Il a volé un tank à Vice City #gta6 #gtavi @streamer"

Rules come from rules/default.json, overridden by the campaign file.
Exit code 0 = OK to post (warnings allowed), 1 = at least one FAIL.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import die, load_json, load_rules, need, probe, run

EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF]")


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, what: str, detail: str = "") -> None:
        self.rows.append((level, what, detail))

    def ok(self, what, detail=""):
        self.add("OK", what, detail)

    def warn(self, what, detail=""):
        self.add("WARN", what, detail)

    def fail(self, what, detail=""):
        self.add("FAIL", what, detail)

    @property
    def failed(self) -> bool:
        return any(r[0] == "FAIL" for r in self.rows)


def measure_lufs(clip: Path) -> float | None:
    proc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(clip), "-map", "0:a:0",
                "-af", "ebur128", "-f", "null", "-"])
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", proc.stderr)
    return float(found[-1]) if found else None


def find_banned(text: str, banned: list[str]) -> list[str]:
    low = text.lower()
    return [b for b in banned if re.search(r"(?<!\w)" + re.escape(b.lower()) + r"(?!\w)", low)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--campaign", help="fichier JSON de règles de campagne")
    ap.add_argument("--caption", help="texte du post (description + hashtags)")
    ap.add_argument("--caption-file", help="texte du post dans un fichier")
    args = ap.parse_args()

    need("ffmpeg")
    clip = Path(args.clip)
    if not clip.is_file():
        die(f"clip introuvable: {clip}")
    rules = load_rules(args.campaign)
    side = load_json(clip.with_suffix(".json"), {})
    caption = args.caption or (Path(args.caption_file).read_text(encoding="utf-8") if args.caption_file else None)
    r = Report()

    # ---- file
    info = probe(clip)
    if (info["width"], info["height"]) == (rules["width"], rules["height"]):
        r.ok("format", f"{info['width']}x{info['height']}")
    else:
        r.fail("format", f"{info['width']}x{info['height']} au lieu de {rules['width']}x{rules['height']}")
    d = info["duration"]
    if rules["min_seconds"] <= d <= rules["max_seconds"]:
        r.ok("durée", f"{d:.1f}s")
    else:
        r.fail("durée", f"{d:.1f}s hors limites {rules['min_seconds']}-{rules['max_seconds']}s")
    if info["fps"] and info["fps"] < rules["min_fps"]:
        r.warn("images/s", f"{info['fps']} fps")
    if not info["has_audio"]:
        (r.fail if rules["require_audio"] else r.warn)("audio", "pas de piste audio")
    else:
        lufs = measure_lufs(clip)
        if lufs is None:
            r.warn("volume", "mesure impossible")
        elif abs(lufs - rules["target_lufs"]) <= rules["lufs_tolerance"]:
            r.ok("volume", f"{lufs:.1f} LUFS")
        else:
            r.warn("volume", f"{lufs:.1f} LUFS (cible {rules['target_lufs']})")

    # ---- overlay (from cut.py sidecar)
    hook, credit = side.get("hook"), side.get("credit")
    if not side:
        r.warn("métadonnées", "pas de .json à côté du clip (pas fait avec cut.py?): accroche/crédit non vérifiés")
    else:
        if hook:
            r.ok("accroche", hook)
            if len(hook) > rules["max_hook_chars"]:
                r.warn("accroche longue", f"{len(hook)} caractères (max conseillé {rules['max_hook_chars']})")
            if EMOJI.search(hook):
                r.warn("emoji dans l'accroche", "souvent rendu en carré vide: mets l'emoji dans la description")
        elif rules["require_hook"]:
            r.fail("accroche", "aucune accroche dans la première seconde")
        if credit:
            r.ok("crédit", credit)
        elif rules["require_credit"]:
            r.fail("crédit", "aucun crédit au créateur")
        if rules.get("creator") and (not credit or rules["creator"].lower() not in credit.lower()):
            r.fail("créateur de la campagne", f"le crédit doit mentionner {rules['creator']}")
        if not side.get("captions"):
            r.warn("sous-titres", "aucun sous-titre (transcription absente?)")
        if side.get("layout") == "fill" and not side.get("captions") and not hook:
            r.warn("transformation", "simple recadrage sans texte = risque de 're-upload' refusé")

    # ---- post text
    texts = [t for t in (hook, caption) if t]
    banned = find_banned(" ".join(texts), rules.get("banned_phrases", []))
    if banned:
        r.fail("contenu interdit", ", ".join(banned) + "  (leaks/piratage/triche/faux officiel)")
    if caption:
        tags = re.findall(r"#\w+", caption)
        if len(tags) > rules["max_hashtags"]:
            r.warn("hashtags", f"{len(tags)} (max {rules['max_hashtags']})")
        else:
            r.ok("hashtags", " ".join(tags) or "aucun")
        low = caption.lower()
        for t in rules.get("required_hashtags", []):
            if t.lower() not in low:
                r.fail("hashtag obligatoire", t)
        for m in rules.get("required_mentions", []):
            if m.lower() not in low:
                r.fail("mention obligatoire", m)
    elif rules.get("required_hashtags") or rules.get("required_mentions"):
        r.warn("description", "pas de --caption: hashtags/mentions obligatoires non vérifiés")

    # ---- print
    icon = {"OK": "  OK ", "WARN": " WARN", "FAIL": " FAIL"}
    for level, what, detail in r.rows:
        print(f"{icon[level]}  {what:<24} {detail}")
    print("\nRésultat:", "À CORRIGER" if r.failed else "PRÊT À POSTER (après ta relecture)")
    sys.exit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
