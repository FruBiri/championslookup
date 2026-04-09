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
        str(value or "")
        .lower()
        .replace("’", "")
        .replace("'", "")
        .replace(".", "")
        .replace(":", "")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "-")
    )


def hp_stat(base: int, sp: int) -> int:
    base_at_50 = math.floor(((2 * base + IV) * LEVEL) / 100) + LEVEL + 10
    return base_at_50 + sp


def other_stat(base: int, sp: int, nature: float) -> int:
    base_at_50 = math.floor(((2 * base + IV) * LEVEL) / 100) + 5
    return math.floor((base_at_50 + sp) * nature)


def build_stat_ranges(base_stats: dict) -> dict:
    if not isinstance(base_stats, dict):
        return {}

    ranges = {}

    if isinstance(base_stats.get("hp"), int):
        ranges["hp"] = {
            "min": hp_stat(base_stats["hp"], 0),
            "max": hp_stat(base_stats["hp"], MAX_SP_PER_STAT)
        }

    for key in ["atk", "def", "spa", "spd", "spe"]:
        if isinstance(base_stats.get(key), int):
            ranges[key] = {
                "min": other_stat(base_stats[key], 0, 0.9),
                "max": other_stat(base_stats[key], MAX_SP_PER_STAT, 1.1)
            }

    return ranges


def is_mega_form(form_id: str) -> bool:
    form_id = str(form_id or "").lower()
    return form_id.endswith("-mega") or form_id.endswith("-mega-x") or form_id.endswith("-mega-y")


def base_species_from_form(form_id: str, base_species_id: str | None) -> str:
    if base_species_id:
        return base_species_id
    form_id = str(form_id or "")
    for suffix in ("-mega-x", "-mega-y", "-mega"):
        if form_id.endswith(suffix):
            return form_id[: -len(suffix)]
    return form_id


def build_pokemon_record(record: dict) -> dict:
    form_id = record.get("formId") or slugify(record.get("displayName") or record.get("name") or "unknown")
    display_name = record.get("displayName") or record.get("name") or form_id

    return {
        "formId": form_id,
        "name": display_name,
        "baseName": record.get("name") or display_name,
        "speciesId": record.get("speciesId") or form_id,
        "baseSpeciesId": base_species_from_form(form_id, record.get("baseSpeciesId")),
        "lookupName": record.get("lookupName"),
        "nationalDex": record.get("nationalDex"),
        "types": record.get("types") or [],
        "baseStats": record.get("baseStats") or {},
        "statRanges": build_stat_ranges(record.get("baseStats") or {}),
        "abilities": record.get("abilities") or [],
        "abilityDetails": record.get("abilityDetails") or [],
        "hiddenAbility": record.get("hiddenAbility"),
        "genus": record.get("genus"),
        "availableInChampions": bool(record.get("availableInChampions", True)),
        "isMegaForm": is_mega_form(form_id),
        "hasMegaEvolution": False,
        "megaEvolutions": [],
        "enriched": bool(record.get("enriched", False)),
        "lookupFailed": bool(record.get("lookupFailed", False)),
        "source": {
            "roster": record.get("source"),
            "pokemonApi": record.get("pokeApiPokemon"),
            "speciesApi": record.get("pokeApiSpecies")
        }
    }


def index_abilities(ability_records):
    indexed = {}

    for ability in ability_records:
        if not isinstance(ability, dict):
            continue
        name = ability.get("name")
        if not name:
            continue
        key = slugify(name)
        indexed[key] = {
            "name": name,
            "apiName": ability.get("apiName"),
            "effect": ability.get("effect") or "Effect text not found.",
            "shortEffect": ability.get("shortEffect") or ability.get("effect") or "Effect text not found.",
            "source": ability.get("source")
        }

    return dict(sorted(indexed.items(), key=lambda item: item[1]["name"].lower()))


def attach_mega_links(pokemon_records):
    mega_map = {}

    for record in pokemon_records:
        if record.get("isMegaForm"):
            base_id = record.get("baseSpeciesId") or record.get("speciesId") or record.get("formId")
            mega_map.setdefault(base_id, []).append(record["formId"])

    for record in pokemon_records:
        if record.get("isMegaForm"):
            continue
        base_id = record.get("speciesId") or record.get("formId")
        megas = sorted(mega_map.get(base_id, []))
        if megas:
            record["hasMegaEvolution"] = True
            record["megaEvolutions"] = megas

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
        raise RuntimeError("'records' must be a list.")

    pokemon_records = [build_pokemon_record(record) for record in raw_records if isinstance(record, dict)]
    pokemon_records = attach_mega_links(pokemon_records)
    pokemon_records.sort(key=lambda r: ((r.get("nationalDex") or 9999), r["name"].lower()))

    ability_index = index_abilities(raw_abilities)

    pokemon_payload = {
        "generatedAt": enriched.get("generatedAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "format": {
            "level": LEVEL,
            "iv": IV,
            "maxSpPerStat": MAX_SP_PER_STAT,
            "totalSpBudget": TOTAL_SP_BUDGET
        },
        "pokemon": pokemon_records
    }

    abilities_payload = {
        "generatedAt": enriched.get("generatedAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "abilities": ability_index
    }

    save_json(POKEMON_OUT_PATH, pokemon_payload)
    save_json(ABILITIES_OUT_PATH, abilities_payload)

    print(f"Wrote {len(pokemon_records)} Pokémon records to {POKEMON_OUT_PATH}")
    print(f"Wrote {len(ability_index)} Ability records to {ABILITIES_OUT_PATH}")


if __name__ == "__main__":
    main()