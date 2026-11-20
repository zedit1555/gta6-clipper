---
name: find-videos
description: Search YouTube for recent GTA 6 videos the user is allowed to clip (Creative Commons CC BY, or creators listed in creators.json from a clipping campaign or written permission), ranked by views per hour, and optionally start moment detection on the best ones. Use when the user has no video of their own, asks to find videos to clip, or wants the page to run on autopilot.
---

# Find videos to clip

Script: `../../scripts/find.py` relative to this skill's base directory. Run it from the user's
working folder (it reads `creators.json` there and writes `found.json`). Reply in the user's language.

```
python find.py [--query "gta 6"] [--hours 72] [--limit 30] [--cc-only] [--show-all] [--auto N]
```

Only two kinds of video may be clipped:
- **CC BY** (Creative Commons Attribution on YouTube): reuse allowed, the credit "via @channel (CC BY)"
  is added automatically and must stay.
- **accord**: channel listed in `creators.json` (copy `<plugin root>/creators.example.json`).
  Add a creator only when the user tells you they joined that creator's clipping campaign or got
  written permission — ask for the proof line and write it in `proof`.

Never offer to clip a "NON" video, and never suggest `--i-have-permission` unless the user says
they have the creator's permission. If the user wants to clip big channels anyway, explain plainly:
copyright claims, removed videos, risk of losing the page, no monetisation.

Workflow
1. Run `find.py` (try `--cc-only` and broader queries if nothing is allowed).
2. Show the allowed list: views/hour, length, right (CC BY / accord), title, link.
3. Pick 1-3 with the user (or `--auto N`), then continue with the `make-clips` skill
   (moments → hooks → cut → check).
4. If nothing is allowed: suggest joining clipping campaigns (e.g. Whop Content Rewards) or asking
   small GTA 6 streamers for permission, then adding them to `creators.json`.
