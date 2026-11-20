---
name: rule-check
description: Check a finished clip and its post text against default rules or a clipping campaign's rules (format, length, loudness, hook, credit, hashtags, mentions, banned content) before posting. Use before any clip is posted or submitted to a campaign.
---

# Rule check

Script: `../../scripts/check.py` relative to this skill's base directory. Reply in the user's language.

```
python check.py jobs/<id>/edits/clip_N.mp4 [--campaign campaigns/<name>.json] [--caption "post text"]
```

- Default rules: `<plugin root>/rules/default.json` (1080x1920, 7-30 s, -14 LUFS ±2,
  hook + credit required, ≤5 hashtags, banned phrases for leaks/piracy/cheats/fake-official).
- Campaign file: any key overrides the default; `banned_*` lists are added. Fields:
  `creator`, `min_seconds`, `max_seconds`, `required_hashtags`, `required_mentions`,
  `max_hashtags`, `banned_phrases`.
- When the user gives you a campaign's rules (pasted text or a page), turn them into
  `campaigns/<short-name>.json`, show the file, and ask them to confirm it.

Exit code 1 = at least one FAIL. Explain each FAIL in plain words and how to fix it
(re-cut with cut.py, edit the caption, etc.). WARN lines are advice, not blockers.
A pass does not replace the user's own review: remind them to watch the clip once before posting.
