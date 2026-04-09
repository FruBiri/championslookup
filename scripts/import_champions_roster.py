import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_in_Pok%C3%A9mon_Champions"

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "sources"
OUT_PATH = SOURCES_DIR / "champions_roster_raw.json"
DEBUG_LINES_PATH = SOURCES_DIR / "bulbapedia_lines.txt"

TYPE_NAMES = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark",
    "Steel", "Fairy"
}

FORM_REPLACEMENTS = {
    "alolan form": "alola",
    "galarian form": "galar",
    "hisuian form": "hisui",
    "paldean form": "paldea",
    "hero form": "hero",
    "hangry mode": "hangry",
    "family of four": "family-of-four",
    "combat breed": "combat-breed",
    "blaze breed": "blaze-breed",
    "aqua breed": "aqua-breed",
    "blade forme": "blade",
    "shield forme": "shield",
    "school form": "school",
    "bloodmoon form": "bloodmoon",
    "male form": "male",
    "female form": "female",
    "rainbow swirl": "rainbow-swirl",
}


def slugify(value: str) -> str:
    value = (value or "").lower().strip()
    value = value.replace("♀", "-f").replace("♂", "-m")
    value = value.replace("’", "").replace("'", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def dedupe_preserve_order(items):
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def fetch_lines():
    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    main = soup.select_one(".mw-parser-output")
    text = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_LINES_PATH.write_text("\n".join(lines), encoding="utf-8")
    return lines


def find_header_block(lines, section_title):
    # Parsed Bulbapedia text appears as one item per line:
    # List of Pokémon in Champions
    # Ndex
    # MS
    # Pokémon
    # Type
    # Normally available?
    # Version added
    for i in range(len(lines) - 6):
        if (
            lines[i] == section_title
            and lines[i + 1] == "Ndex"
            and lines[i + 2] == "MS"
            and lines[i + 3] == "Pokémon"
            and lines[i + 4] == "Type"
            and lines[i + 5] == "Normally available?"
            and lines[i + 6] == "Version added"
        ):
            return i + 7
    return None


def find_section_end(lines, start_idx):
    stop_markers = {
        "Forms",
        "Mega Evolutions",
        "Other forms",
        "Untransferable Pokémon",
        "Trivia",
        "Related articles",
    }

    for i in range(start_idx, len(lines)):
        if lines[i] in stop_markers:
            return i
    return len(lines)


def normalize_form_id(name: str, form_text: str | None) -> str:
    low_name = (name or "").lower().strip()
    low_form = (form_text or "").lower().strip()

    # Mega names should derive entirely from the name field
    if low_name.startswith("mega "):
        rest = low_name[5:].strip()

        if rest.endswith(" x"):
            return f"{slugify(rest[:-2].strip())}-mega-x"
        if rest.endswith(" y"):
            return f"{slugify(rest[:-2].strip())}-mega-y"

        return f"{slugify(rest)}-mega"

    base = slugify(name)
    if not low_form:
        return base

    suffixes = []
    remainder = low_form

    ordered_phrases = [
        "alolan form",
        "galarian form",
        "hisuian form",
        "paldean form",
        "combat breed",
        "blaze breed",
        "aqua breed",
        "hero form",
        "hangry mode",
        "family of four",
        "blade forme",
        "shield forme",
        "school form",
        "bloodmoon form",
        "male form",
        "female form",
        "rainbow swirl",
    ]

    for phrase in ordered_phrases:
        if phrase in remainder:
            suffixes.append(FORM_REPLACEMENTS[phrase])
            remainder = remainder.replace(phrase, " ")

    remainder = re.sub(r"\bTBD\b", " ", remainder, flags=re.I)
    remainder = re.sub(r"\b\d+\.\d+(?:\.\d+)?\b", " ", remainder)
    remainder = " ".join(remainder.split())

    if remainder:
        remainder_slug = slugify(remainder)
        if remainder_slug:
            suffixes.extend([p for p in remainder_slug.split("-") if p])

    suffixes = dedupe_preserve_order(suffixes)
    return f"{base}-{'-'.join(suffixes)}" if suffixes else base


def format_display_name(name: str, form_text: str | None) -> str:
    if not form_text:
        return name
    # Mega names already include Mega in the base name line
    if name.lower().startswith("mega "):
        return name
    return f"{name} ({form_text})"


def parse_line_stream_entries(lines, start_idx, end_idx):
    block = lines[start_idx:end_idx]
    entries = []
    i = 0

    while i < len(block):
        line = block[i]

        if not re.fullmatch(r"#\d{4}", line):
            i += 1
            continue

        ndex = line[1:]
        if i + 1 >= len(block):
            break

        name = block[i + 1]
        i += 2

        form_parts = []
        types = []
        version_added = None

        while i < len(block) and not re.fullmatch(r"#\d{4}", block[i]):
            current = block[i]

            if current in TYPE_NAMES:
                types.append(current)
            elif current == "TBD":
                pass
            elif re.fullmatch(r"\d+\.\d+(?:\.\d+)?", current):
                version_added = current
            else:
                form_parts.append(current)

            i += 1

        form_text = " ".join(form_parts).strip() if form_parts else None

        entries.append({
            "ndex": ndex,
            "name": name,
            "displayName": format_display_name(name, form_text),
            "formText": form_text,
            "formId": normalize_form_id(name, form_text),
            "types": dedupe_preserve_order(types),
            "versionAdded": version_added,
            "availableInChampions": True,
            "source": URL,
        })

    return entries


def dedupe_entries(entries):
    by_form_id = {}

    for entry in entries:
        score = 0
        if entry.get("formText"):
            score += 2
        if entry.get("types"):
            score += 1
        if entry.get("versionAdded"):
            score += 1
        if entry.get("name", "").lower().startswith("mega "):
            score += 1

        existing = by_form_id.get(entry["formId"])
        if not existing or score > existing["_score"]:
            by_form_id[entry["formId"]] = {"_score": score, "entry": entry}

    return [v["entry"] for v in by_form_id.values()]


def parse_main_roster(lines):
    start_idx = find_header_block(lines, "List of Pokémon in Champions")
    if start_idx is None:
        raise RuntimeError(f"Could not find main roster header block. See {DEBUG_LINES_PATH}")

    end_idx = find_section_end(lines, start_idx)
    return parse_line_stream_entries(lines, start_idx, end_idx)


def parse_mega_roster(lines):
    start_idx = find_header_block(lines, "Mega Evolutions")
    if start_idx is None:
        return []

    end_idx = find_section_end(lines, start_idx)
    return parse_line_stream_entries(lines, start_idx, end_idx)


def main():
    lines = fetch_lines()

    main_entries = parse_main_roster(lines)
    mega_entries = parse_mega_roster(lines)

    combined = dedupe_entries(main_entries + mega_entries)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(combined)} roster entries to {OUT_PATH}")
    print(f"  Main roster entries: {len(main_entries)}")
    print(f"  Mega entries: {len(mega_entries)}")


if __name__ == "__main__":
    main()