---
name: clip-cutter
description: Render a vertical 1080x1920 clip from a moment with word-by-word captions, a hook box, a credit line and -14 LUFS audio, in fill, blurred-background or facecam-on-top layout. Use when the user wants to cut, render or re-edit a clip.
---

# Clip cutter

Script: `../../scripts/cut.py` relative to this skill's base directory. Reply in the user's language.

```
python cut.py jobs/<id> --pick N --layout fill|blur|facecam --hook "TEXT" [--credit "@handle"]
              [--facecam x,y,w,h] [--shift -2] [--start S --end E] [--hook-seconds 0]
              [--no-captions] [--no-caps] [--font "Arial Black"] [--out name.mp4]
python cut.py jobs/<id> --pick N --preview      # one frame, to locate the webcam
```

Facecam box
1. Run `--preview`, then look at the image (`jobs/<id>/edits/preview_N.jpg`).
2. Estimate the webcam rectangle as fractions of width/height, e.g. top-right cam ≈ `0.74,0.02,0.24,0.30`.
3. Render, extract a frame (`ffmpeg -ss 3 -i clip.mp4 -frames:v 1 check.png`) and look at it.
   If the face is cut or there is game HUD in the cam band, adjust and re-render.

Rules baked in
- Hook stays on screen for the whole clip by default (`--hook-seconds 3` to show it only at the start).
- Captions need `transcript.json` (from moments.py without `--no-transcribe`).
- Credit defaults to the job's creator, shown as "via @handle".
- Emoji do not render in the hook — put them in the post text instead.

Always look at a frame of the finished clip before telling the user it is ready.
