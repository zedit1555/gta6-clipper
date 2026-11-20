---
name: setup
description: Install and check everything gta6-clipper needs (Python 3.10+, ffmpeg, faster-whisper, yt-dlp) and create the working folders. Use on first run, or when a gta6-clipper script fails because something is missing.
---

# Setup

The plugin's scripts live in `../../scripts/` relative to this skill's base directory.
Call that path `$SCRIPTS` below. Reply in the user's language.

1. Run `python $SCRIPTS/doctor.py` (use `python3` if `python` is not found).
2. For each `KO` line, fix it:
   - ffmpeg missing: Windows `winget install Gyan.FFmpeg`, macOS `brew install ffmpeg`,
     Linux `sudo apt install ffmpeg`. Ask before installing system packages.
   - Python packages: `pip install -r <plugin root>/requirements.txt`
     (suggest a virtual env: `python -m venv .venv`).
3. Run `doctor.py` again until it prints "Tout est prêt."
4. In the user's current folder create `campaigns/` and copy
   `<plugin root>/campaigns/example.json` into it as a template.
5. Ask the user 3 quick questions and write the answers to `clipper.md` in the current folder:
   - which page / handle they post from,
   - which languages their audience speaks,
   - whether they work from their own gameplay recordings, from a clipping campaign
     (creator + rules), or both.
6. Tell them the first command to try:
   `python $SCRIPTS/moments.py "<video file or link>" --top 5`

Notes
- First transcription downloads a Whisper model (~500 MB for `small`). On a laptop without
  an NVIDIA GPU, a 10-minute video takes a few minutes; `--model base` is faster.
