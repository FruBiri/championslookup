# Pokémon Champions Quick Scout

A lightweight static web app for checking compact stat ranges, Abilities, and Mega Evolution availability for Pokémon that are valid in **Pokémon Champions**.

## What the site shows
- Search by Pokémon name
- Lowest and highest possible values for all 6 stats at level 50
- Possible Abilities with quick effect help and an external wiki link
- Mega Evolution toggle where relevant
- Data provenance notes so you can distinguish Champions roster validation from canonical species data

## Data pipeline
This project is meant to stay static on GitHub Pages.
The site reads local JSON from `data/`, while the import pipeline writes those files ahead of time.

### Source priority
1. **Bulbapedia Champions roster page** for whether a Pokémon or Mega form is available in Champions
2. **PokeAPI** for canonical form stats, types, and standard Abilities
3. **Manual seeds / overrides** for Champions-specific cleanup and edge cases

### Why it works this way
Champions availability is the thing that most needs a Champions-specific source.
Stats and standard Abilities can then be imported from canonical species/form data once the roster gate is known.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Rebuild the dataset
```bash
python scripts/import_champions_roster.py
python scripts/enrich_from_pokeapi.py
python scripts/build_data.py
```

That flow will:
- import the current Champions roster into `sources/champions_roster.json`
- enrich it into `sources/champions_enriched.json`
- publish the final site files to `data/pokemon.json` and `data/abilities.json`

## Manual override files
- `sources/pokemon_seed.json` — hand-maintained entries and hard overrides
- `sources/abilities_seed.json` — hand-maintained ability blurbs and source links
- `sources/form_overrides.json` — Bulbapedia-form to PokeAPI-form mapping for special cases

## GitHub Actions
The repo includes a workflow at `.github/workflows/update-data.yml`.
It can refresh the roster and generated JSON on a schedule or from the Actions tab.

## Important caution
This tool is only as good as the live-source mapping.
If Bulbapedia changes page structure or Champions changes availability, revisit the import scripts and override files.
