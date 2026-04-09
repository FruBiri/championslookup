import json
import re
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "sources"

ROSTER_PATH = SOURCES_DIR / "champions_roster_raw.json"
OVERRIDES_PATH = SOURCES_DIR / "form_overrides.json"
OUT_PATH = SOURCES_DIR / "champions_enriched.json"

POKEAPI_POKEMON = "https://pokeapi.co/api/v2/pokemon/{name}"
POKEAPI_SPECIES = "https://pokeapi.co/api/v2/pokemon-species/{name}"
POKEAPI_ABILITY = "https://pokeapi.co/api/v2/ability/{name}"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "pokemon-champions-tool/1.0"})


def load_json(path: Path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("♀", "-f").replace("♂", "-m")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def pokeapi_slug(value: str) -> str:
    value = value.strip()
    value = value.replace("Farfetch’d", "Farfetchd")
    value = value.replace("Sirfetch’d", "Sirfetchd")
    value = value.replace("Mr. Mime", "Mr Mime")
    value = value.replace("Mime Jr.", "Mime Jr")
    value = value.replace("Type: Null", "Type Null")
    value = value.replace("Nidoran♀", "Nidoran F")
    value = value.replace("Nidoran♂", "Nidoran M")
    return slugify(value)


def fetch_json(url: str):
    resp = SESSION.get(url, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    time.sleep(0.1)
    return resp.json()


def get_english_text(entries, key="effect_entries", text_key="short_effect"):
    for entry in entries:
        lang = entry.get("language", {}).get("name")
        if lang == "en":
            return entry.get(text_key)
    return None


def extract_english_genus(species_json):
    for entry in species_json.get("genera", []):
        if entry.get("language", {}).get("name") == "en":
            return entry.get("genus")
    return None


def parse_base_form_id(form_id: str) -> str:
    prefixes = [
        "-mega-x",
        "-mega-y",
        "-mega",
        "-alola",
        "-galar",
        "-hisui",
        "-paldea",
        "-hero",
        "-hangry",
        "-family-of-four",
        "-combat-breed",
        "-blaze-breed",
        "-aqua-breed",
        "-blade",
        "-shield",
    ]
    for suffix in prefixes:
        if form_id.endswith(suffix):
            return form_id[: -len(suffix)]
    return form_id


def load_overrides():
    overrides = load_json(OVERRIDES_PATH, {})
    return {
        "pokemon_name_map": overrides.get("pokemon_name_map", {}),
        "form_id_map": overrides.get("form_id_map", {}),
        "ability_name_map": overrides.get("ability_name_map", {}),
    }


def resolve_pokemon_lookup_name(record: dict, overrides: dict) -> str:
    form_id = record.get("formId", "")
    name = record.get("name", "")

    if form_id in overrides["form_id_map"]:
        return overrides["form_id_map"][form_id]

    if name in overrides["pokemon_name_map"]:
        return overrides["pokemon_name_map"][name]

    return pokeapi_slug(form_id or name)


def build_ability_record(ability_name: str, ability_api_name: str, cache: dict, overrides: dict):
    cache_key = ability_api_name.lower()

    if cache_key in cache:
        return cache[cache_key]

    mapped_name = overrides["ability_name_map"].get(ability_api_name, ability_api_name)
    data = fetch_json(POKEAPI_ABILITY.format(name=mapped_name))
    if not data:
        record = {
            "name": ability_name,
            "apiName": mapped_name,
            "effect": "Effect text not found.",
            "shortEffect": "Effect text not found.",
            "source": f"https://pokeapi.co/api/v2/ability/{mapped_name}",
        }
        cache[cache_key] = record
        return record

    effect = get_english_text(data.get("effect_entries", []), text_key="effect") or "Effect text not found."
    short_effect = get_english_text(data.get("effect_entries", []), text_key="short_effect") or effect

    record = {
        "name": ability_name,
        "apiName": data.get("name", mapped_name),
        "effect": effect.replace("\n", " ").replace("\f", " ").strip(),
        "shortEffect": short_effect.replace("\n", " ").replace("\f", " ").strip(),
        "source": f"https://pokeapi.co/api/v2/ability/{data.get('name', mapped_name)}",
    }
    cache[cache_key] = record
    return record


def enrich_record(record: dict, overrides: dict, ability_cache: dict):
    lookup_name = resolve_pokemon_lookup_name(record, overrides)
    pokemon_json = fetch_json(POKEAPI_POKEMON.format(name=lookup_name))

    if not pokemon_json:
        return {
            **record,
            "lookupName": lookup_name,
            "enriched": False,
            "lookupFailed": True,
            "abilities": record.get("abilities", []),
            "baseStats": record.get("baseStats"),
            "types": record.get("types", []),
        }

    species_name = pokemon_json.get("species", {}).get("name")
    species_json = fetch_json(POKEAPI_SPECIES.format(name=species_name)) if species_name else None

    stats = {}
    for stat in pokemon_json.get("stats", []):
        stat_name = stat.get("stat", {}).get("name")
        base_stat = stat.get("base_stat")
        if stat_name == "hp":
            stats["hp"] = base_stat
        elif stat_name == "attack":
            stats["atk"] = base_stat
        elif stat_name == "defense":
            stats["def"] = base_stat
        elif stat_name == "special-attack":
            stats["spa"] = base_stat
        elif stat_name == "special-defense":
            stats["spd"] = base_stat
        elif stat_name == "speed":
            stats["spe"] = base_stat

    types = [
        t.get("type", {}).get("name", "").capitalize()
        for t in sorted(pokemon_json.get("types", []), key=lambda x: x.get("slot", 0))
        if t.get("type", {}).get("name")
    ]

    ability_names = []
    ability_records = []
    hidden_ability = None

    for ability_info in pokemon_json.get("abilities", []):
        api_name = ability_info.get("ability", {}).get("name")
        if not api_name:
            continue

        display_name = api_name.replace("-", " ").title()
        ability_names.append(display_name)

        ability_record = build_ability_record(display_name, api_name, ability_cache, overrides)
        ability_records.append(ability_record)

        if ability_info.get("is_hidden"):
            hidden_ability = display_name

    genus = extract_english_genus(species_json) if species_json else None

    return {
        **record,
        "lookupName": lookup_name,
        "enriched": True,
        "lookupFailed": False,
        "nationalDex": pokemon_json.get("id"),
        "displayName": record.get("name"),
        "genus": genus,
        "baseStats": stats,
        "types": types or record.get("types", []),
        "abilities": ability_names,
        "abilityDetails": ability_records,
        "hiddenAbility": hidden_ability,
        "pokeApiPokemon": f"https://pokeapi.co/api/v2/pokemon/{pokemon_json.get('name')}",
        "pokeApiSpecies": f"https://pokeapi.co/api/v2/pokemon-species/{species_name}" if species_name else None,
    }


def dedupe_records(records: list[dict]) -> list[dict]:
    by_form_id = {}

    for record in records:
        form_id = record.get("formId") or slugify(record.get("name", ""))
        score = 0
        if record.get("enriched"):
            score += 5
        if record.get("baseStats"):
            score += 3
        if record.get("abilities"):
            score += 2
        if record.get("types"):
            score += 1

        existing = by_form_id.get(form_id)
        if not existing or score > existing["_score"]:
            by_form_id[form_id] = {
                "_score": score,
                "record": record,
            }

    return [v["record"] for v in by_form_id.values()]


def main():
    if not ROSTER_PATH.exists():
        raise RuntimeError(
            f"{ROSTER_PATH} is missing. Run scripts/import_champions_roster.py first."
        )

    roster = load_json(ROSTER_PATH, [])
    if not isinstance(roster, list):
        raise RuntimeError(
            f"Unexpected roster format in {ROSTER_PATH}. Expected a JSON list."
        )

    overrides = load_overrides()
    ability_cache = {}
    enriched_records = []

    print(f"Loaded {len(roster)} raw roster entries")

    for idx, record in enumerate(roster, start=1):
        name = record.get("name", "Unknown")
        form_id = record.get("formId", "")
        print(f"[{idx}/{len(roster)}] Enriching {name} ({form_id})...")
        try:
            enriched = enrich_record(record, overrides, ability_cache)
        except Exception as exc:
            enriched = {
                **record,
                "enriched": False,
                "lookupFailed": True,
                "error": str(exc),
            }
        enriched_records.append(enriched)

    deduped_records = dedupe_records(enriched_records)

    payload = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rawCount": len(roster),
        "dedupedCount": len(deduped_records),
        "records": deduped_records,
        "abilities": sorted(
            ability_cache.values(),
            key=lambda x: x.get("name", "").lower()
        ),
    }

    save_json(OUT_PATH, payload)

    print(f"Wrote {len(deduped_records)} enriched records to {OUT_PATH}")


if __name__ == "__main__":
    main()