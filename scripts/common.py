"""Shared helpers for gta6-clipper scripts."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = Path.cwd() / "jobs"
RULES_DIR = ROOT / "rules"

W, H = 1080, 1920  # vertical output


def die(msg: str, code: int = 1) -> None:
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(code)


def need(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        die(f"'{binary}' introuvable. Lance d'abord: python scripts/doctor.py")
    return path


def run(cmd: list[str], cwd: Path | None = None, quiet: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        die(f"commande échouée: {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    if not quiet and proc.stdout:
        print(proc.stdout)
    return proc


def probe(path: Path) -> dict:
    need("ffprobe")
    out = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]).stdout
    data = json.loads(out)
    info = {"duration": float(data.get("format", {}).get("duration", 0) or 0),
            "width": None, "height": None, "fps": None, "has_audio": False}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["width"] is None:
            info["width"], info["height"] = s.get("width"), s.get("height")
            num, _, den = (s.get("avg_frame_rate") or "0/1").partition("/")
            try:
                info["fps"] = round(float(num) / float(den or 1), 2)
            except ZeroDivisionError:
                info["fps"] = None
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s.strip(), re.I))


def new_job_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "video"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}"


def job_path(arg: str) -> Path:
    p = Path(arg)
    if not p.exists():
        alt = JOBS_DIR / arg
        if alt.exists():
            p = alt
    if not (p / "meta.json").exists():
        die(f"'{arg}' n'est pas un dossier de job (meta.json manquant). "
            "Crée-le avec: python scripts/fetch.py <fichier-ou-lien>")
    return p


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_t(sec: float) -> str:
    sec = max(0.0, sec)
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def load_rules(campaign: str | None) -> dict:
    rules = load_json(RULES_DIR / "default.json", {})
    if campaign:
        cp = Path(campaign)
        if not cp.exists():
            die(f"fichier de campagne introuvable: {campaign}")
        override = json.loads(cp.read_text(encoding="utf-8"))
        for k, v in override.items():
            if isinstance(v, list) and isinstance(rules.get(k), list) and k.startswith("banned"):
                rules[k] = rules[k] + v  # banned lists add up, never shrink
            else:
                rules[k] = v
    return rules


# ---------------------------------------------------------------- permissions
CREATORS_FILE = Path.cwd() / "creators.json"


def load_creators() -> list[dict]:
    """creators.json in the working folder: creators who allowed you to clip them."""
    data = load_json(CREATORS_FILE, [])
    return data.get("creators", []) if isinstance(data, dict) else data


def _norm_handle(s: str | None) -> str:
    s = (s or "").strip().lower().rstrip("/")
    s = re.sub(r"^https?://(www\.|m\.)?(youtube\.com|twitch\.tv)/", "", s)
    s = re.sub(r"^(channel/|c/|user/)", "", s)
    return s.lstrip("@")


def permission_for(info: dict, creators: list[dict] | None = None) -> tuple[str | None, str]:
    """Return (kind, detail). kind = 'cc' | 'allowed' | None.

    'cc'      : YouTube video under Creative Commons Attribution (reuse allowed, credit required)
    'allowed' : channel listed in creators.json (clipping campaign or written permission)
    """
    lic = (info.get("license") or "").lower()
    if "creative commons" in lic:
        return "cc", "Creative Commons (CC BY)"
    ids = {_norm_handle(info.get(k)) for k in
           ("channel_id", "uploader_id", "channel_url", "uploader_url", "channel", "uploader")}
    ids.discard("")
    for c in creators if creators is not None else load_creators():
        for ch in c.get("channels", []):
            if _norm_handle(ch) in ids:
                return "allowed", c.get("name") or ch
    return None, "ni Creative Commons, ni dans creators.json"
