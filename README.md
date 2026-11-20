# gta6-clipper

Plugin **Claude Code** qui transforme une partie de GTA 6 ou un stream en **clips verticaux 1080x1920**
prêts pour TikTok, YouTube Shorts et Instagram Reels :

1. **trouve les meilleurs moments** (pics de volume, mots d'excitation dans la transcription, « most replayed » YouTube)
2. **monte le clip** : sous-titres mot par mot, accroche en haut, crédit du créateur, son à -14 LUFS,
   3 mises en page (plein écran, fond flouté, facecam en haut)
3. **vérifie les règles** avant de poster (format, durée, volume, crédit, hashtags, contenus interdits, règles de campagne)

Rien n'est publié automatiquement : tu relis et tu postes toi-même.

> Projet fan non officiel, sans lien avec Rockstar Games, Take-Two ou Anthropic.

## Installation

Prérequis : Python 3.10+, ffmpeg, Claude Code.

Dans Claude Code :

```
/plugin marketplace add zedit1555/gta6-clipper
/plugin install gta6-clipper@gta6-clipper
```

Puis dis à Claude : **« lance le setup de gta6-clipper »**. Il vérifie ffmpeg et Python et installe
`requirements.txt`.

## Utilisation avec Claude

> Fais-moi 3 clips de `D:/captures/braquage.mp4`, c'est ma propre partie, page @mapage, public francophone.

Claude enchaîne : moments → choix de la mise en page → 3 accroches → rendu → vérification, et te rend
les fichiers avec le texte du post.

## Utilisation sans Claude (scripts)

```bash
pip install -r requirements.txt
python scripts/doctor.py                                   # tout est installé ?

python scripts/moments.py "D:/captures/braquage.mp4" --top 8 --creator "@mapage" --lang fr
python scripts/cut.py jobs/<id> --pick 1 --preview         # une image pour repérer la webcam
python scripts/cut.py jobs/<id> --pick 1 --layout blur --hook "IL A VOLÉ UN TANK"
python scripts/cut.py jobs/<id> --pick 2 --layout facecam --facecam 0.74,0.02,0.24,0.30 --hook "..."
python scripts/check.py jobs/<id>/edits/clip_1.mp4 --caption "Il a osé 😳 #gta6 #gtavi @mapage"
```

Les liens (YouTube, Twitch VOD…) sont téléchargés avec yt-dlp :
`python scripts/moments.py "https://www.youtube.com/watch?v=..." --creator "@streamer"`

| Script | Rôle |
|---|---|
| `doctor.py` | vérifie Python, ffmpeg et les paquets |
| `fetch.py` | crée un job depuis un fichier ou un lien |
| `moments.py` | détecte et classe les moments (12-30 s par défaut), écrit `moments.json` + `transcript.json` |
| `cut.py` | rend le clip 9:16 avec sous-titres, accroche, crédit, son normalisé |
| `check.py` | contrôle le clip et le texte du post ; code de sortie 1 s'il y a un FAIL |

### Mises en page

| `fill` | `blur` | `facecam` |
|---|---|---|
| jeu recadré plein écran | image complète sur fond flouté | webcam en haut, jeu en bas, accroche sur la jonction |

### Campagnes de clipping

Copie `campaigns/example.json`, mets-y le créateur, les hashtags et mentions obligatoires, la durée
min/max, puis `check.py ... --campaign campaigns/ma-campagne.json`.

## Transcription

La transcription utilise [faster-whisper](https://github.com/SYSTRAN/faster-whisper). La première fois,
le modèle est téléchargé (`small` ≈ 500 Mo). Sans GPU NVIDIA, compte quelques minutes pour 10 minutes
de vidéo ; `--model base` va plus vite, `--no-transcribe` saute la transcription (pas de sous-titres).

## Règles

- Clippe ta propre partie, ou un créateur **qui l'autorise** (campagne de clipping ou accord écrit). Crédite-le toujours.
- Pas de leaks, de piratage, de « jouer avant tout le monde », de mod menus ou de faux comptes Rockstar :
  `check.py` bloque ces formulations.
- Un simple recadrage sans texte risque d'être refusé comme « re-upload » : accroche + sous-titres.
- Aucun revenu n'est garanti.

## Licence

MIT
