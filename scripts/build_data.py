from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"
DATA_DIR = ROOT / "data"

POKEMON_SEED = SOURCES_DIR / "pokemon_seed.json"
ABILITY_SEED = SOURCES_DIR / "abilities_seed.json"
POKEMON_OUT = DATA_DIR / "pokemon.json"
ABILITY_OUT = DATA_DIR / "abilities.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def sort_pokemon_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: item["displayName"].lower())


def sort_ability_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: item["name"].lower())


def main() -> None:
    pokemon = load_json(POKEMON_SEED)
    abilities = load_json(ABILITY_SEED)

    write_json(POKEMON_OUT, sort_pokemon_records(pokemon))
    write_json(ABILITY_OUT, sort_ability_records(abilities))

    print(f"Wrote {POKEMON_OUT.relative_to(ROOT)}")
    print(f"Wrote {ABILITY_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
