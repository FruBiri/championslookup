import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_in_Pok%C3%A9mon_Champions"

OUT_DIR = Path("sources")
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "champions_roster_raw.json"

TYPE_NAMES = {
    "Normal","Fire","Water","Electric","Grass","Ice","Fighting","Poison",
    "Ground","Flying","Psychic","Bug","Rock","Ghost","Dragon","Dark",
    "Steel","Fairy"
}

FORM_REPLACEMENTS = {
    "Alolan Form": "alola",
    "Galarian Form": "galar",
    "Hisuian Form": "hisui",
    "Paldean Form": "paldea",
    "Hero Form": "hero",
    "Hangry Mode": "hangry",
    "Family of Four": "family-of-four",
    "Combat Breed": "combat-breed",
    "Blaze Breed": "blaze-breed",
    "Aqua Breed": "aqua-breed",
    "Blade Forme": "blade",
    "Shield Forme": "shield",
}

ENTRY_RE = re.compile(
    r"(?ms)^(#\d{4})\s+.*?\b([A-Z][A-Za-z0-9'’:. -]+?)\s*\n"   # ndex + name
    r"(.*?)(?=^#\d{4}\s+|\Z)"                                   # payload until next dex
)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("♀", "-f").replace("♂", "-m")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def normalize_form_id(name: str, form_bits: list[str]) -> str:
    base = slugify(name)
    if not form_bits:
        return base

    norm_bits = []
    for bit in form_bits:
        bit = bit.strip()
        if not bit:
            continue
        bit = FORM_REPLACEMENTS.get(bit, slugify(bit))
        norm_bits.append(bit)

    return f"{base}-{'-'.join(norm_bits)}"


def fetch_page_text() -> str:
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    main = soup.select_one(".mw-parser-output")
    text = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)

    # keep only the main Champions roster block
    start_marker = "List of Pokémon in Champions\nNdex"
    stop_marker = "Untransferable Pokémon"

    start = text.find(start_marker)
    if start == -1:
        raise RuntimeError("Could not find the regular Champions roster start marker.")

    stop = text.find(stop_marker, start)
    if stop == -1:
        raise RuntimeError("Could not find the Untransferable Pokémon stop marker.")

    return text[start:stop]


def parse_entry_payload(name: str, payload: str) -> dict:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]

    version_added = None
    types = []
    form_bits = []

    for line in lines:
        if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", line):
            version_added = line
            continue

        if line == "TBD":
            continue

        if line in TYPE_NAMES:
            types.append(line)
            continue

        # split combined lines like "Alolan Form Electric Psychic TBD 1.0.2"
        tokens = re.split(r"\s{2,}|\t", line)
        if len(tokens) == 1:
            words = line.split()
            rebuilt = []
            i = 0
            while i < len(words):
                two = " ".join(words[i:i+2])
                if two in FORM_REPLACEMENTS:
                    form_bits.append(two)
                    i += 2
                    continue
                if words[i] in TYPE_NAMES:
                    types.append(words[i])
                    i += 1
                    continue
                if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", words[i]):
                    version_added = words[i]
                    i += 1
                    continue
                if words[i] != "TBD":
                    rebuilt.append(words[i])
                i += 1

            if rebuilt:
                form_bits.append(" ".join(rebuilt).strip())
        else:
            for token in tokens:
                token = token.strip()
                if not token or token == "TBD":
                    continue
                if token in TYPE_NAMES:
                    types.append(token)
                    continue
                if token in FORM_REPLACEMENTS:
                    form_bits.append(token)
                    continue
                if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", token):
                    version_added = token
                    continue
                form_bits.append(token)

    # dedupe while preserving order
    deduped_types = list(dict.fromkeys(types))
    deduped_form_bits = list(dict.fromkeys([b for b in form_bits if b]))

    return {
        "name": name,
        "types": deduped_types,
        "formText": " ".join(deduped_form_bits) if deduped_form_bits else None,
        "formId": normalize_form_id(name, deduped_form_bits),
        "versionAdded": version_added,
    }


def parse_roster(text: str) -> list[dict]:
    entries = []

    for match in ENTRY_RE.finditer(text):
        ndex = match.group(1).replace("#", "")
        name = match.group(2).strip()
        payload = match.group(3).strip()

        parsed = parse_entry_payload(name, payload)
        entries.append({
            "ndex": ndex,
            "name": parsed["name"],
            "formText": parsed["formText"],
            "formId": parsed["formId"],
            "types": parsed["types"],
            "versionAdded": parsed["versionAdded"],
            "availableInChampions": True,
            "source": URL,
        })

    return entries


def main():
    text = fetch_page_text()
    roster = parse_roster(text)

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(roster, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(roster)} roster entries to {OUT_FILE}")


if __name__ == "__main__":
    main()