# Data pipeline notes

This prototype is intentionally static-first.

Recommended production pipeline:

1. Pull a Champions-only roster source.
2. Pull per-form ability and base-stat data only for Pokémon/forms present in Champions.
3. Normalize into `data/pokemon.json`.
4. Commit the generated JSON to GitHub Pages.

Important rule:
Do not silently fall back to a generic Pokédex if Champions-specific verification is missing.
Instead, mark the entry as unverified or exclude it.
