# Pokémon Champions Stat Lookup

Fast, battle-focused lookup for Pokémon Champions stat ranges, Abilities, and Mega forms.

## How it works

This site is a static app for GitHub Pages. The page reads local JSON files from `data/`.
You edit or generate source files in `sources/`, run the data build script, and commit the
updated output.

## File layout

- `index.html` – app shell
- `styles.css` – UI
- `app.js` – search, stat rendering, Mega toggle, Ability help
- `sources/pokemon_seed.json` – editable source-of-truth Pokémon records
- `sources/abilities_seed.json` – editable source-of-truth Ability records
- `data/pokemon.json` – generated file served by GitHub Pages
- `data/abilities.json` – generated file served by GitHub Pages
- `scripts/build_data.py` – writes generated JSON from the seed files
- `.github/workflows/update-data.yml` – optional GitHub Actions job

## Local update flow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_data.py
```

Commit the changed `data/*.json` files and push.

## GitHub Pages

Because the site uses plain JSON fetched from the same repo, GitHub Pages can host the app
without a backend server.

## Source policy

Keep Champions availability Champions-specific.

Recommended source priority:
1. Official Pokémon Champions pages for roster gating and training behavior.
2. Champions-specific community trackers for forms, mega availability, and live updates.
3. Manual review before committing new data.

Avoid treating a generic Pokédex as proof that a Pokémon or form is currently valid in Champions.

## Ability help

Abilities use both:
- a quick local effect summary in the UI
- an external wiki link for full detail

That keeps the battle screen short while still giving you a deeper reference when needed.
