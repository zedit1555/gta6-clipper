"""Find the best 12-30 s moments in a video.

    python scripts/moments.py jobs/<id> --top 8
    python scripts/moments.py "D:/captures/session1.mp4" --top 5      # creates the job first
    python scripts/moments.py jobs/<id> --no-transcribe                # loudness only, fast

Signals combined into one score:
  - loudness spikes (shouting, explosions) relative to the surrounding 30 s
  - hype words in the transcript (faster-whisper, word timestamps)
  - YouTube "most replayed" heatmap, when the source is a YouTube link
Writes jobs/<id>/moments.json and transcript.json.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from common import (die, fmt_t, is_url, job_path, load_json, load_rules, need, run,
                    save_json)

HOP = 0.5  # seconds per analysis bin


# ---------------------------------------------------------------- signals
def extract_audio(src: str, wav: Path) -> None:
    if wav.exists():
        return
    need("ffmpeg")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(wav)])


def loudness_curve(wav: Path, n_bins: int) -> np.ndarray:
    raw = wav.read_bytes()
    data_at = raw.find(b"data")
    pcm = np.frombuffer(raw[data_at + 8:], dtype="<i2").astype(np.float32) / 32768.0
    per = int(16000 * HOP)
    usable = (len(pcm) // per) * per
    if usable == 0:
        return np.zeros(n_bins)
    frames = pcm[:usable].reshape(-1, per)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-6)
    db = _fit(db, n_bins)
    # spike = loudness above the local (30 s) median
    k = int(30 / HOP)
    pad = np.pad(db, (k // 2, k // 2), mode="edge")
    local = np.array([np.median(pad[i:i + k]) for i in range(len(db))])
    spike = np.clip(db - local, 0, None)
    spike[db < -50] = 0  # silence is never a moment
    return spike


def transcribe(wav: Path, out: Path, model_name: str, language: str | None) -> dict | None:
    cached = load_json(out)
    if cached:
        return cached
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  (faster-whisper absent: pas de transcription)", file=sys.stderr)
        return None
    device, compute = "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            device, compute = "cuda", "float16"
    except Exception:
        pass
    print(f"  Transcription ({model_name}, {device})... ça peut prendre quelques minutes")
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute)
        segs, info = model.transcribe(str(wav), language=language, word_timestamps=True,
                                      vad_filter=True)
        result = {"language": info.language, "segments": []}
        for s in segs:
            result["segments"].append({
                "start": s.start, "end": s.end, "text": s.text.strip(),
                "words": [{"start": w.start, "end": w.end, "word": w.word.strip()}
                          for w in (s.words or [])],
            })
    except Exception as e:  # model download blocked, no disk, etc.
        print(f"  (transcription impossible: {e})", file=sys.stderr)
        return None
    save_json(out, result)
    return result


def hype_curve(transcript: dict | None, n_bins: int, hype_words: list[str]) -> np.ndarray:
    curve = np.zeros(n_bins)
    if not transcript:
        return curve
    pats = [re.compile(r"(?<!\w)" + re.escape(w.lower()) + r"(?!\w)") for w in hype_words]
    for seg in transcript["segments"]:
        text = seg["text"].lower()
        hits = sum(len(p.findall(text)) for p in pats)
        hits += text.count("!") * 0.5
        words = seg.get("words") or []
        dur = max(seg["end"] - seg["start"], 0.5)
        rate = len(words) / dur  # fast talking = excitement
        val = hits + max(0.0, rate - 3.0) * 0.5
        if val <= 0:
            continue
        a, b = int(seg["start"] / HOP), int(seg["end"] / HOP) + 1
        curve[max(a, 0):min(b, n_bins)] += val
    return curve


def heat_curve(heatmap: list[dict], n_bins: int) -> np.ndarray:
    curve = np.zeros(n_bins)
    for h in heatmap or []:
        if h.get("start") is None or h.get("value") is None:
            continue
        a, b = int(h["start"] / HOP), int((h["end"] or h["start"]) / HOP) + 1
        curve[max(a, 0):min(b, n_bins)] = max(h["value"], 0)
    return curve


# ---------------------------------------------------------------- picking
def _fit(arr: np.ndarray, n: int) -> np.ndarray:
    if len(arr) >= n:
        return arr[:n]
    return np.pad(arr, (0, n - len(arr)), mode="edge" if len(arr) else "constant")


def _norm(x: np.ndarray) -> np.ndarray:
    hi = np.percentile(x, 99) if x.any() else 0
    return np.clip(x / hi, 0, 1) if hi > 0 else np.zeros_like(x)


def _smooth(x: np.ndarray, sec: float) -> np.ndarray:
    k = max(1, int(sec / HOP))
    return np.convolve(x, np.ones(k) / k, mode="same")


def snap(t: float, transcript: dict | None, kind: str, tol: float = 2.5) -> float:
    """Move a cut to a sentence boundary if one is close, so we don't cut mid-word."""
    if not transcript:
        return t
    if kind == "start":
        edges = [s["start"] for s in transcript["segments"] if t - tol <= s["start"] <= t + 0.5]
    else:
        edges = [s["end"] + 0.3 for s in transcript["segments"] if t - 0.5 <= s["end"] <= t + tol]
    return min(edges, key=lambda e: abs(e - t)) if edges else t


def text_between(transcript: dict | None, a: float, b: float) -> str:
    if not transcript:
        return ""
    return " ".join(s["text"] for s in transcript["segments"] if s["end"] > a and s["start"] < b)


def pick(score: np.ndarray, duration: float, top: int, lo: float, hi: float,
         transcript: dict | None) -> list[dict]:
    chosen: list[tuple[float, float]] = []
    out = []
    order = np.argsort(score)[::-1]
    floor = float(score.max()) * 0.15  # ignore flat parts once the real peaks are taken
    for idx in order:
        if len(out) >= top or score[idx] <= floor:
            break
        peak = idx * HOP
        if any(a - 3 <= peak <= b + 3 for a, b in chosen):
            continue
        # grow around the peak while score stays above 40% of it
        thr = score[idx] * 0.4
        l = r = idx
        while l > 0 and score[l - 1] >= thr and (idx - l) * HOP < hi * 0.6:
            l -= 1
        while r < len(score) - 1 and score[r + 1] >= thr and (r - idx) * HOP < hi * 0.6:
            r += 1
        start = min(l * HOP, peak - 6)  # a little set-up before the payoff
        end = max(r * HOP + 2, peak + 4)
        if end - start < lo:
            grow = lo - (end - start)
            start -= grow * 0.5
            end += grow * 0.5
        if end - start > hi:
            start = max(start, peak - hi * 0.6)
            end = start + hi
        start, end = max(0.0, start), min(duration, end)
        if end - start < lo:  # near the edges of the video
            start, end = (0.0, min(duration, lo)) if start == 0 else (max(0.0, duration - lo), duration)
        start = snap(start, transcript, "start")
        end = min(duration, snap(end, transcript, "end"))
        if any(not (end <= a or start >= b) for a, b in chosen):
            continue
        chosen.append((start, end))
        out.append({"start": round(start, 2), "end": round(end, 2),
                    "duration": round(end - start, 2), "peak": round(peak, 2),
                    "score": round(float(score[idx]), 3)})
    for i, m in enumerate(out, 1):
        m["rank"] = i
        m["text"] = text_between(transcript, m["start"], m["end"])[:400]
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", help="dossier de job, ou fichier/lien (le job est alors créé)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min", type=float, default=12, help="durée min d'un moment (s)")
    ap.add_argument("--max", type=float, default=30, help="durée max d'un moment (s)")
    ap.add_argument("--no-transcribe", action="store_true", help="volume seul (rapide, pas de sous-titres)")
    ap.add_argument("--model", default="small", help="modèle Whisper: tiny, base, small, medium, large-v3")
    ap.add_argument("--lang", default=None, help="langue parlée (fr, en, ...). Auto si absent")
    ap.add_argument("--creator", help="crédit, si le job est créé ici")
    args = ap.parse_args()

    if is_url(args.job) or (Path(args.job).is_file()):
        cmd = [sys.executable, str(Path(__file__).with_name("fetch.py")), args.job]
        if args.creator:
            cmd += ["--creator", args.creator]
        out = subprocess.run(cmd, capture_output=True, text=True)
        print(out.stdout, end="")
        if out.returncode != 0:
            die(out.stderr.strip())
        line = next((l for l in out.stdout.splitlines() if l.startswith("Job prêt: ")), None)
        job = Path(line.split(": ", 1)[1])
    else:
        job = job_path(args.job)

    meta = load_json(job / "meta.json")
    rules = load_rules(None)
    duration = meta["duration"]
    n = max(1, int(duration / HOP))
    print(f"Analyse de {job.name} ({fmt_t(duration)})")

    signals = {}
    transcript = None
    if meta.get("has_audio"):
        wav = job / "audio.wav"
        extract_audio(meta["source"], wav)
        signals["loud"] = (_norm(_smooth(loudness_curve(wav, n), 2)), 0.5)
        if not args.no_transcribe:
            transcript = transcribe(wav, job / "transcript.json", args.model, args.lang)
            if transcript:
                signals["hype"] = (_norm(_smooth(hype_curve(transcript, n, rules.get("hype_words", [])), 3)), 0.3)
    if meta.get("heatmap"):
        signals["heat"] = (_norm(heat_curve(meta["heatmap"], n)), 0.2)
    if not signals:
        die("ni audio ni heatmap: impossible de détecter des moments. Choisis-les à la main avec cut.py --start/--end")

    total_w = sum(w for _, w in signals.values())
    score = sum(c * (w / total_w) for c, w in signals.values())
    score = _smooth(score, 3)

    moments = pick(score, duration, args.top, args.min, args.max, transcript)
    for m in moments:
        a, b = int(m["start"] / HOP), max(int(m["end"] / HOP), int(m["start"] / HOP) + 1)
        m["signals"] = {k: round(float(c[a:b].max()), 2) for k, (c, _) in signals.items()}
    save_json(job / "moments.json", {"signals": list(signals), "moments": moments})

    print(f"\nSignaux: {', '.join(signals)}{'' if transcript else '  (sans transcription -> pas de sous-titres)'}")
    print(f"{'#':>2}  {'début':>7}  {'fin':>7}  {'durée':>5}  {'score':>5}  extrait")
    for m in moments:
        print(f"{m['rank']:>2}  {fmt_t(m['start']):>7}  {fmt_t(m['end']):>7}  {m['duration']:>4.0f}s  "
              f"{m['score']:>5.2f}  {m['text'][:70]}")
    print(f"\nSuite: python scripts/cut.py {job} --pick 1 --layout blur --hook \"...\"")


if __name__ == "__main__":
    main()
