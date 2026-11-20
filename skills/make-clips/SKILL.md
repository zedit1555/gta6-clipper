---
name: make-clips
description: End-to-end GTA 6 clip workflow — from a video file or a link to checked, ready-to-post 9:16 clips with captions, hook and credit. Use when the user says "make clips from this", gives a GTA 6 video/VOD/stream link, or asks for TikTok/Shorts/Reels clips.
---

# Make clips (full workflow)

Scripts: `../../scripts/` relative to this skill's base directory (`$SCRIPTS`).
Run them from the user's working folder (jobs are created in `./jobs/`). Reply in the user's language.

## 0. Rights first
Ask (once per source) where the video comes from:
- **their own gameplay** → fine.
- **another creator** → only if there is a clipping campaign or written permission for that creator.
  Note the creator handle; it must appear as the credit. If neither, stop and explain why.
Never clip leaks, pirated builds, "play early"/"free download" content, cheats or mod menus.

## 1. Find moments
`python $SCRIPTS/moments.py "<file or link>" --top 8 --creator "@handle" [--lang fr]`
- Prints a table and writes `jobs/<id>/moments.json` (+ `transcript.json`).
- Read `moments.json` and pick the 3 best: strong payoff, understandable without context,
  not just loud noise. Use the transcript excerpts to judge.

## 2. Choose layout
- Streamer with webcam → `facecam`. First run `cut.py <job> --pick N --preview`, open the
  preview image, find the webcam box and express it as fractions `x,y,w,h` of the frame.
- Pure gameplay with action in the centre → `fill`. Wide shots / HUD matters → `blur`.

## 3. Write hooks
Use the `hook-writer` skill: 3 options per clip, pick the best, no emoji in the hook
(emoji go in the post text).

## 4. Cut
`python $SCRIPTS/cut.py jobs/<id> --pick N --layout <layout> [--facecam x,y,w,h] --hook "..." [--credit "@handle"]`
Adjust with `--shift -2` or `--start/--end` if the moment starts too late or ends too early.

## 5. Check
Write the post text (1 line + 3-5 hashtags + @mention of the creator), then
`python $SCRIPTS/check.py jobs/<id>/edits/clip_N.mp4 --caption "<post text>" [--campaign campaigns/<name>.json]`
Fix every FAIL and re-run.

## 6. Hand over
Give the user, per clip: file path, hook, post text, check result.
**Never upload or post anything yourself** — the user reviews and posts.
