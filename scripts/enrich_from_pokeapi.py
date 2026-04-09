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
    value = (value or "").lower().strip()
    value = value.replace("♀", "-f").replace("♂", "-m")
    value = value.replace("’", "").replace("'", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def fetch_json(url: str):
    response = SESSION.get(url, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    time.sleep(0.1)
    return response.json()


def get_english_effect(entries, field_name):
    for entry in entries:
        if entry.get("language", {}).get("name") == "en":
            value = entry.get(field_name)
            if value:
                return value.replace("\n", " ").replace("\f", " ").strip()
    return None


def get_english_genus(species_json):
    for entry in species_json.get("genera", []):
        if entry.get("language", {}).get("name") == "en":
            return entry.get("genus")
    return None


def load_overrides():
    raw = load_json(OVERRIDES_PATH, {})
    if not isinstance(raw, dict):
        return {}

    normalized = {}

    for key, value in raw.items():
        if not isinstance(value, dict):
            continue

        candidates = [key]
        aliases = value.get("aliases", [])
        if isinstance(aliases, list):
            candidates.extend(aliases)

        for candidate in candidates:
            normalized[slugify(candidate).replace("-", " ")] = value

    return normalized


def normalize_override_key(record):
    candidates = []

    name = (record.get("name") or "").strip()
    display_name = (record.get("displayName") or "").strip()
    form_text = (record.get("formText") or "").strip()
    form_id = (record.get("formId") or "").strip()

    if name and form_text:
        candidates.append(f"{name} {form_text}")
    if display_name:
        candidates.append(display_name)
    if form_id:
        candidates.append(form_id.replace("-", " "))
    if name:
        candidates.append(name)

    normalized = []
    for candidate in candidates:
        candidate = candidate.replace("(", " ").replace(")", " ")
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if candidate:
            normalized.append(slugify(candidate).replace("-", " "))

    seen = set()
    ordered = []
    for item in normalized:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def fallback_pokeapi_name(record):
    form_id = (record.get("formId") or "").strip()
    if form_id:
        return form_id
    return slugify(record.get("name") or "")


def strip_mega_suffix(form_id: str) -> str:
    for suffix in ("-mega-x", "-mega-y", "-mega"):
        if form_id.endswith(suffix):
            return form_id[: -len(suffix)]
    return form_id


def build_ability_record(display_name, api_name, ability_cache):
    key = slugify(api_name)
    if key in ability_cache:
        return ability_cache[key]

    data = fetch_json(POKEAPI_ABILITY.format(name=api_name))
    if not data:
        record = {
            "name": display_name,
            "apiName": api_name,
            "effect": "Effect text not found.",
            "shortEffect": "Effect text not found.",
            "source": f"https://pokeapi.co/api/v2/ability/{api_name}"
        }
        ability_cache[key] = record
        return record

    effect = get_english_effect(data.get("effect_entries", []), "effect") or "Effect text not found."
    short_effect = get_english_effect(data.get("effect_entries", []), "short_effect") or effect

    record = {
        "name": display_name,
        "apiName": data.get("name", api_name),
        "effect": effect,
        "shortEffect": short_effect,
        "source": f"https://pokeapi.co/api/v2/ability/{data.get('name', api_name)}"
    }
    ability_cache[key] = record
    return record


def build_display_name(record, override):
    if override and override.get("displayName"):
        return override["displayName"]
    if record.get("displayName"):
        return record["displayName"]
    return record.get("name") or record.get("formId") or "Unknown"


def enrich_record(record, overrides, ability_cache):
    override = None
    for candidate in normalize_override_key(record):
        if candidate in overrides:
            override = overrides[candidate]
            break

    pokeapi_name = None
    if override and override.get("pokeApiName"):
        pokeapi_name = override["pokeApiName"]
    else:
        pokeapi_name = fallback_pokeapi_name(record)

    pokemon_json = fetch_json(POKEAPI_POKEMON.format(name=pokeapi_name))

    if not pokemon_json:
        form_id = record.get("formId") or fallback_pokeapi_name(record)
        return {
            **record,
            "displayName": build_display_name(record, override),
            "speciesId": override.get("speciesId") if override else form_id,
            "baseSpeciesId": strip_mega_suffix(form_id),
            "lookupName": pokeapi_name,
            "enriched": False,
            "lookupFailed": True,
            "baseStats": record.get("baseStats") or {},
            "abilities": [],
            "abilityDetails": [],
            "hiddenAbility": None
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

    abilities = []
    ability_details = []
    hidden_ability = None

    for ability_info in pokemon_json.get("abilities", []):
        ability_api_name = ability_info.get("ability", {}).get("name")
        if not ability_api_name:
            continue

        display_name = ability_api_name.replace("-", " ").title()
        abilities.append(display_name)

        detail = build_ability_record(display_name, ability_api_name, ability_cache)
        ability_details.append(detail)

        if ability_info.get("is_hidden"):
            hidden_ability = display_name

    form_id = record.get("formId") or pokemon_json.get("name")
    species_id = override.get("speciesId") if override and override.get("speciesId") else form_id

    return {
        **record,
        "displayName": build_display_name(record, override),
        "speciesId": species_id,
        "baseSpeciesId": strip_mega_suffix(form_id),
        "lookupName": pokemon_json.get("name"),
        "nationalDex": pokemon_json.get("id"),
        "genus": get_english_genus(species_json) if species_json else None,
        "types": types,
        "baseStats": stats,
        "abilities": abilities,
        "abilityDetails": ability_details,
        "hiddenAbility": hidden_ability,
        "enriched": True,
        "lookupFailed": False,
        "pokeApiPokemon": f"https://pokeapi.co/api/v2/pokemon/{pokemon_json.get('name')}",
        "pokeApiSpecies": f"https://pokeapi.co/api/v2/pokemon-species/{species_name}" if species_name else None
    }


def dedupe_records(records):
    by_form_id = {}

    for record in records:
        form_id = record.get("formId") or slugify(record.get("displayName") or record.get("name"))
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
            by_form_id[form_id] = {"_score": score, "record": record}

    return [v["record"] for v in by_form_id.values()]


def main():
    if not ROSTER_PATH.exists():
        raise RuntimeError(f"{ROSTER_PATH} is missing. Run scripts/import_champions_roster.py first.")

    roster = load_json(ROSTER_PATH, [])
    if not isinstance(roster, list):
        raise RuntimeError("champions_roster_raw.json must be a JSON list.")

    overrides = load_overrides()
    ability_cache = {}
    enriched_records = []

    print(f"Loaded {len(roster)} raw roster entries")

    for index, record in enumerate(roster, start=1):
        label = record.get("displayName") or record.get("name") or "Unknown"
        print(f"[{index}/{len(roster)}] Enriching {label}...")
        try:
            enriched = enrich_record(record, overrides, ability_cache)
        except Exception as exc:
            enriched = {
                **record,
                "displayName": record.get("displayName") or record.get("name"),
                "enriched": False,
                "lookupFailed": True,
                "error": str(exc)
            }
        enriched_records.append(enriched)

    deduped = dedupe_records(enriched_records)

    payload = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rawCount": len(roster),
        "dedupedCount": len(deduped),
        "records": deduped,
        "abilities": sorted(ability_cache.values(), key=lambda x: x.get("name", "").lower())
    }

    save_json(OUT_PATH, payload)
    print(f"Wrote {len(deduped)} enriched records to {OUT_PATH}")


if __name__ == "__main__":
    main()