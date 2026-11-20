---
name: moment-finder
description: Find the best 12-30 second moments in a GTA 6 video using loudness spikes, hype words in the transcript and YouTube "most replayed" data. Use when the user wants to know what to clip from a video, VOD or link.
---

# Moment finder

Script: `../../scripts/moments.py` relative to this skill's base directory. Reply in the user's language.

```
python moments.py "<file, link or jobs/<id>>" --top 8 [--creator "@handle"] [--lang fr]
                  [--min 12 --max 30] [--model small] [--no-transcribe]
```

- A file or link creates a job in `./jobs/<id>/` (links are downloaded with yt-dlp — only for
  creators who allow clipping).
- `--no-transcribe` is fast (loudness only) but then clips get no captions.
- Output: table + `jobs/<id>/moments.json` with `start`, `end`, `score`, `signals`, `text`.

How to present results
- Re-rank with judgement: a moment needs a clear payoff (chase ending, crash, funny line,
  surprise). Loud music or menu screens score high but are useless — drop them.
- For each kept moment give: rank, timestamps, one-line description, suggested layout.
- If the transcript is in another language than the audience, say so (captions will be in
  the spoken language).
