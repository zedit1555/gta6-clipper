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
