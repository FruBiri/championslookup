# Pokémon Champions Stat Lookup

A lightweight static web app for quick in-battle lookup.

## Current behavior
- Search by Pokémon name
- Show only the lowest possible stat and highest possible stat for each of the 6 stats
- Show current possible abilities
- Toggle Mega Evolution when available
- Uses a local JSON dataset

## Why static first
GitHub Pages is enough for the UI, and a checked-in JSON dataset keeps the app fast and simple while Champions data sources are still evolving.

## GitHub Pages deployment
1. Create a GitHub repo.
2. Upload all files in this folder.
3. In repo settings, enable GitHub Pages from the main branch root.
4. Wait for the Pages URL to publish.

## Data model
Each species entry should include:
- speciesId
- displayName
- availableInChampions
- hasMegaEvolution
- baseForm
- megaForm
- verification metadata

## Stat model currently used
- Level 50
- Fixed IV = 31
- Per-stat investment range = 0 to 32
- Displayed range = absolute low to absolute high only

This is optimized for fast lookup rather than full build simulation.
