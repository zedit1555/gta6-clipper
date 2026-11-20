"""Render a vertical 1080x1920 clip from a moment.

    python scripts/cut.py jobs/<id> --pick 2 --layout blur --hook "IL A VOLÉ UN TANK" --credit "@streamer"
    python scripts/cut.py jobs/<id> --pick 1 --preview                 # saves a frame to locate the webcam
    python scripts/cut.py jobs/<id> --pick 1 --layout facecam --facecam 0.74,0.02,0.24,0.30
    python scripts/cut.py jobs/<id> --start 125 --end 148 --layout fill

Layouts:
  fill     game cropped to fill the whole screen
  blur     whole game frame centred on a blurred copy of itself
  facecam  streamer webcam on top, game below, hook on the seam
           --facecam x,y,w,h  webcam box as fractions of the frame (0-1) or pixels

Adds: word-by-word captions (needs transcript.json), hook box, credit line,
audio normalised to -14 LUFS. Writes jobs/<id>/edits/clip_<n>.mp4 + .json.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from common import H, W, die, fmt_t, job_path, load_json, need, run, save_json

CAM_H = 672                # facecam band height
HIGHLIGHT = "&H0000E5FF&"  # yellow-orange in ASS BGR
WHITE = "&H00FFFFFF&"


# ---------------------------------------------------------------- video filters
def parse_box(spec: str, sw: int, sh: int) -> tuple[int, int, int, int]:
    try:
        vals = [float(v) for v in spec.split(",")]
        assert len(vals) == 4
    except (ValueError, AssertionError):
        die("--facecam attend 4 nombres: x,y,largeur,hauteur (ex: 0.74,0.02,0.24,0.30)")
    if all(v <= 1 for v in vals):
        vals = [vals[0] * sw, vals[1] * sh, vals[2] * sw, vals[3] * sh]
    x, y, w, h = (int(round(v)) // 2 * 2 for v in vals)
    w, h = min(w, sw - x), min(h, sh - y)
    if w < 32 or h < 32:
        die("boîte facecam trop petite ou hors de l'image")
    return x, y, w, h


def video_filter(layout: str, box: tuple[int, int, int, int] | None) -> str:
    cover = "scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if layout == "fill":
        return f"[0:v]{cover.format(w=W, h=H)},setsar=1[base]"
    if layout == "blur":
        return (f"[0:v]split[a][b];"
                f"[a]{cover.format(w=W, h=H)},boxblur=24:2,eq=brightness=-0.10[bg];"
                f"[b]scale={W}:-2[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]")
    if layout == "facecam":
        x, y, w, h = box
        game_h = H - CAM_H
        return (f"[0:v]split[c][g];"
                f"[c]crop={w}:{h}:{x}:{y},{cover.format(w=W, h=CAM_H)}[cam];"
                f"[g]{cover.format(w=W, h=game_h)}[game];"
                f"[cam][game]vstack,setsar=1[base]")
    die(f"layout inconnu: {layout}")


# ---------------------------------------------------------------- ASS overlay
def esc(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def ts(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunk_words(words: list[dict], max_words: int = 3, max_gap: float = 0.6) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[-1]["end"] > max_gap
                    or cur[-1]["word"][-1:] in ".!?,"):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(path: Path, *, layout: str, dur: float, hook: str | None, hook_secs: float,
              credit: str | None, words: list[dict], font: str, caps: bool) -> None:
    hook_y = CAM_H if layout == "facecam" else 330
    cap_y = 1250 if layout != "facecam" else 1380
    credit_y = 1500 if layout != "facecam" else 1590
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # hook: black text on an opaque white box (BorderStyle 3 -> box uses OutlineColour)
        f"Style: Hook,{font},62,&H00000000,&H00000000,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,3,18,0,5,90,90,0,1",
        f"Style: Cap,{font},80,{WHITE},{WHITE},&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,70,70,0,1",
        f"Style: Credit,{font},38,&H33FFFFFF,&H33FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,5,60,60,0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook:
        end = dur if hook_secs <= 0 else min(dur, hook_secs)
        lines.append(f"Dialogue: 2,{ts(0)},{ts(end)},Hook,,0,0,0,,{{\\pos({W // 2},{hook_y})}}{esc(hook)}")
    if credit:
        lines.append(f"Dialogue: 1,{ts(0)},{ts(dur)},Credit,,0,0,0,,{{\\pos({W // 2},{credit_y})}}{esc(credit)}")
    for chunk in chunk_words(words):
        for i, w in enumerate(chunk):
            start = w["start"]
            end = chunk[i + 1]["start"] if i + 1 < len(chunk) else max(w["end"], start + 0.25)
            parts = []
            for j, other in enumerate(chunk):
                txt = esc(other["word"].upper() if caps else other["word"])
                parts.append(f"{{\\c{HIGHLIGHT}}}{txt}{{\\c{WHITE}}}" if j == i else txt)
            pop = "{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            lines.append(f"Dialogue: 0,{ts(start)},{ts(min(end, dur))},Cap,,0,0,0,,"
                         f"{{\\pos({W // 2},{cap_y})}}{pop}{' '.join(parts)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def words_in(transcript: dict | None, a: float, b: float) -> list[dict]:
    if not transcript:
        return []
    out = []
    for seg in transcript["segments"]:
        for w in seg.get("words") or []:
            if w["start"] >= a and w["end"] <= b + 0.2 and w["word"]:
                out.append({"start": w["start"] - a, "end": min(w["end"], b) - a, "word": w["word"]})
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--pick", type=int, help="numéro du moment dans moments.json")
    ap.add_argument("--start", type=float, help="début manuel (s), remplace --pick")
    ap.add_argument("--end", type=float, help="fin manuelle (s)")
    ap.add_argument("--shift", type=float, default=0, help="décale début et fin (s), ex: -2")
    ap.add_argument("--layout", choices=["fill", "blur", "facecam"], default="blur")
    ap.add_argument("--facecam", help="boîte webcam x,y,w,h (fractions 0-1 ou pixels)")
    ap.add_argument("--hook", help="texte d'accroche (court, en majuscules marche bien)")
    ap.add_argument("--hook-seconds", type=float, default=0, help="durée d'affichage de l'accroche, 0 = tout le clip")
    ap.add_argument("--credit", help="ex: @streamer (sinon celui du job)")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--no-caps", action="store_true", help="sous-titres sans majuscules forcées")
    ap.add_argument("--font", default="Arial Black", help="police des textes")
    ap.add_argument("--preview", action="store_true", help="exporte juste une image du moment (pour placer la facecam)")
    ap.add_argument("--out", help="nom du fichier de sortie (sans dossier)")
    args = ap.parse_args()

    need("ffmpeg")
    job = job_path(args.job)
    meta = load_json(job / "meta.json")
    transcript = load_json(job / "transcript.json")

    if args.start is not None:
        start = args.start
        end = args.end if args.end is not None else start + 20
        label = f"{int(start)}s"
    elif args.pick:
        moments = (load_json(job / "moments.json") or {}).get("moments", [])
        m = next((m for m in moments if m["rank"] == args.pick), None)
        if not m:
            die(f"moment #{args.pick} introuvable. Lance d'abord: python scripts/moments.py {job}")
        start, end, label = m["start"], m["end"], str(args.pick)
    else:
        die("indique --pick N ou --start/--end")
    start, end = max(0.0, start + args.shift), min(meta["duration"], end + args.shift)
    if end - start < 1:
        die("clip trop court")
    dur = end - start
    edits = job / "edits"
    edits.mkdir(exist_ok=True)

    if args.preview:
        shot = edits / f"preview_{label}.jpg"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start + min(2, dur / 2):.2f}", "-i", meta["source"],
             "-frames:v", "1", "-q:v", "3", str(shot)])
        print(f"Image: {shot}  ({meta['width']}x{meta['height']})")
        return

    box = None
    if args.layout == "facecam":
        if not args.facecam:
            die("layout facecam: ajoute --facecam x,y,w,h. Fais --preview pour voir où est la webcam.")
        box = parse_box(args.facecam, meta["width"], meta["height"])

    credit = args.credit or meta.get("creator")
    if credit and not credit.lower().startswith(("crédit", "credit", "via", "🎥")):
        credit = f"via {credit}"
    words = [] if args.no_captions else words_in(transcript, start, end)

    name = args.out or f"clip_{label}.mp4"
    out = edits / name
    ass = edits / (Path(name).stem + ".ass")
    build_ass(ass, layout=args.layout, dur=dur, hook=args.hook, hook_secs=args.hook_seconds,
              credit=credit, words=words, font=args.font, caps=not args.no_caps)

    graph = video_filter(args.layout, box) + f";[base]ass={ass.name}[v]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}",
           "-i", meta["source"], "-filter_complex", graph, "-map", "[v]"]
    if meta.get("has_audio"):
        cmd += ["-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    cmd += ["-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", name]
    t0 = time.time()
    print(f"Rendu {name}: {fmt_t(start)} -> {fmt_t(end)} ({dur:.0f}s), layout={args.layout}, "
          f"sous-titres={'oui' if words else 'non'}")
    run(cmd, cwd=edits)  # run inside edits/ so the .ass path needs no escaping (Windows-safe)

    save_json(out.with_suffix(".json"), {
        "job": job.name, "pick": args.pick, "start": start, "end": end, "duration": round(dur, 2),
        "layout": args.layout, "facecam": box, "hook": args.hook, "credit": credit,
        "captions": bool(words), "source_url": meta.get("url"), "source_title": meta.get("title"),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    print(f"OK en {time.time() - t0:.0f}s -> {out}")
    print(f"Vérifie: python scripts/check.py {out}")


if __name__ == "__main__":
    main()
