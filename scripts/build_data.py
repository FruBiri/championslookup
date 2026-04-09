import json
import math
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "sources"
DATA_DIR = BASE_DIR / "data"

ENRICHED_PATH = SOURCES_DIR / "champions_enriched.json"
POKEMON_OUT_PATH = DATA_DIR / "pokemon.json"
ABILITIES_OUT_PATH = DATA_DIR / "abilities.json"

LEVEL = 50
IV = 31
MAX_SP_PER_STAT = 32
TOTAL_SP_BUDGET = 66


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def slugify(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace(".", "")
        .replace("’", "")
        .replace("'", "")
        .replace(":", "")
    )


def hp_stat(base: int, sp: int) -> int:
    base_at_50 = math.floor(((2 * base + IV) * LEVEL) / 100) + LEVEL + 10
    return base_at_50 + sp


def other_stat(base: int, sp: int, nature: float) -> int:
    base_at_50 = math.floor(((2 * base + IV) * LEVEL) / 100) + 5
    return math.floor((base_at_50 + sp) * nature)


def build_stat_ranges(base_stats: dict) -> dict:
    if not base_stats:
        return {}

    ranges = {}

    hp_base = base_stats.get("hp")
    if isinstance(hp_base, int):
        ranges["hp"] = {
            "min": hp_stat(hp_base, 0),
            "max": hp_stat(hp_base, MAX_SP_PER_STAT),
        }

    for stat_key in ["atk", "def", "spa", "spd", "spe"]:
        base = base_stats.get(stat_key)
        if isinstance(base, int):
            ranges[stat_key] = {
                "min": other_stat(base, 0, 0.9),
                "max": other_stat(base, MAX_SP_PER_STAT, 1.1),
            }

    return ranges


def build_pokemon_record(record: dict) -> dict:
    form_id = record.get("formId") or slugify(record.get("displayName") or record.get("name", "unknown"))
    display_name = record.get("displayName") or record.get("name") or form_id
    base_stats = record.get("baseStats") or {}
    abilities = record.get("abilities") or []
    types = record.get("types") or []

    mega_flag = form_id.startswith("mega-") or "-mega" in form_id or display_name.lower().startswith("mega ")

    return {
        "formId": form_id,
        "name": display_name,
        "baseName": record.get("name") or display_name,
        "lookupName": record.get("lookupName"),
        "nationalDex": record.get("nationalDex"),
        "types": types,
        "baseStats": base_stats,
        "statRanges": build_stat_ranges(base_stats),
        "abilities": abilities,
        "abilityDetails": record.get("abilityDetails") or [],
        "hiddenAbility": record.get("hiddenAbility"),
        "genus": record.get("genus"),
        "availableInChampions": bool(record.get("availableInChampions", True)),
        "hasMegaEvolution": bool(record.get("hasMegaEvolution", False)),
        "megaEvolution": record.get("megaEvolution"),
        "isMegaForm": mega_flag,
        "enriched": bool(record.get("enriched", False)),
        "lookupFailed": bool(record.get("lookupFailed", False)),
        "source": {
            "roster": record.get("source"),
            "pokemonApi": record.get("pokeApiPokemon"),
            "speciesApi": record.get("pokeApiSpecies"),
        },
    }


def index_abilities(ability_records: list) -> dict:
    abilities = {}

    for ability in ability_records:
        if not isinstance(ability, dict):
            continue

        name = ability.get("name")
        if not name:
            continue

        key = slugify(name)
        abilities[key] = {
            "name": name,
            "apiName": ability.get("apiName"),
            "effect": ability.get("effect") or "Effect text not found.",
            "shortEffect": ability.get("shortEffect") or ability.get("effect") or "Effect text not found.",
            "source": ability.get("source"),
        }

    return dict(sorted(abilities.items(), key=lambda item: item[1]["name"].lower()))


def attach_mega_links(pokemon_records: list[dict]) -> list[dict]:
    by_base_name = {}
    mega_by_base_name = {}

    for record in pokemon_records:
        name = record["name"]
        base_name = record.get("baseName") or name

        normalized_base = base_name.lower().removeprefix("mega ").strip()
        normalized_name = name.lower().strip()

        by_base_name.setdefault(normalized_base, []).append(record)

        if record.get("isMegaForm"):
            stripped = normalized_name
            if stripped.startswith("mega "):
                stripped = stripped[5:].strip()
            mega_by_base_name[stripped] = record

    for record in pokemon_records:
        if record.get("isMegaForm"):
            continue

        base_name = (record.get("baseName") or record["name"]).lower().strip()
        mega = mega_by_base_name.get(base_name)
        if mega:
            record["hasMegaEvolution"] = True
            record["megaEvolution"] = mega["formId"]

    return pokemon_records


def main():
    if not ENRICHED_PATH.exists():
        raise RuntimeError(f"{ENRICHED_PATH} is missing. Run scripts/enrich_from_pokeapi.py first.")

    enriched = load_json(ENRICHED_PATH)

    if not isinstance(enriched, dict):
        raise RuntimeError("champions_enriched.json must be a JSON object.")

    raw_records = enriched.get("records", [])
    raw_abilities = enriched.get("abilities", [])

    if not isinstance(raw_records, list):
        raise RuntimeError("'records' in champions_enriched.json must be a list.")

    pokemon_records = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        pokemon_records.append(build_pokemon_record(item))

    pokemon_records = attach_mega_links(pokemon_records)

    pokemon_records.sort(key=lambda r: (r["nationalDex"] or 9999, r["name"].lower()))
    ability_index = index_abilities(raw_abilities)

    pokemon_payload = {
        "generatedAt": enriched.get("generatedAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "format": {
            "level": LEVEL,
            "iv": IV,
            "maxSpPerStat": MAX_SP_PER_STAT,
            "totalSpBudget": TOTAL_SP_BUDGET,
        },
        "pokemon": pokemon_records,
    }

    abilities_payload = {
        "generatedAt": enriched.get("generatedAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "abilities": ability_index,
    }

    save_json(POKEMON_OUT_PATH, pokemon_payload)
    save_json(ABILITIES_OUT_PATH, abilities_payload)

    print(f"Wrote {len(pokemon_records)} Pokémon records to {POKEMON_OUT_PATH}")
    print(f"Wrote {len(ability_index)} Ability records to {ABILITIES_OUT_PATH}")


if __name__ == "__main__":
    main()