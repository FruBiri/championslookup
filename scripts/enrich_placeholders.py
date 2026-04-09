"""Optional enrichment hooks for future Champions-specific scraping.

This file is intentionally conservative.

Use it to fetch Champions-only availability pages or structured community pages,
normalize them, and merge them into the seed files before build_data.py runs.
Do not treat a generic Pokédex as authoritative for Champions availability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class AbilityRecord:
    name: str
    effect: str
    source_url: str


@dataclass
class PokemonRecord:
    species_id: str
    display_name: str



def fetch_champions_roster() -> Iterable[PokemonRecord]:
    """Stub for future work.

    Recommended source priority:
      1. Official Pokémon Champions pages for availability gating.
      2. Champions-specific community trackers for forms / mega details.
      3. Manual review before committing generated data.
    """
    return []


if __name__ == "__main__":
    print("This is a placeholder for future scraping logic.")
