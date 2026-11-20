---
name: hook-writer
description: Write 3 short on-screen hook options and a post caption for a GTA 6 clip. Use when a clip needs a hook/title, or the user asks for captions, titles or post text.
---

# Hook writer

Input: the moment's transcript excerpt (`jobs/<id>/moments.json` → `text`) and what happens on screen
(ask the user or look at a preview frame if unclear). Write in the audience's language
(see `clipper.md` if it exists).

## On-screen hook (3 options)
- Max ~45 characters, CAPITALS, readable in 1 second.
- Promise the payoff without spoiling it: curiosity, stakes or a reaction.
  Patterns: "HE DIDN'T SEE THE TANK COMING", "POV: YOU TRY TO ROB A BANK IN VICE CITY",
  "WAIT FOR THE ENDING", "THIS IS WHY YOU DON'T RACE THE COPS".
- No emoji (they don't render), no clickbait lies, nothing the clip doesn't show.
- Never: leaks, "free download", "play early", fake Rockstar announcements, cheat/mod menus.
- Mark your favourite and say why in one line.

## Post text
`<one line that adds context or a question> + 3-5 hashtags + credit`
- Hashtags: `#gta6 #gtavi` + 1-3 specific (`#vicecity`, `#gta6clips`, the streamer's tag).
- Always credit: `🎥 @creator` (campaigns usually require the exact handle).
- A question at the end ("would you have jumped?") drives comments.

Then suggest running `check.py` with `--caption "<post text>"`.
