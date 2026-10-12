"""
Parses BAG OPR (OpenbareRuimte) XML extract files and writes
a deduplicated list of active Dutch street names (type Weg only),
one per line, for use in the org-security-scanner PII detection.

Names are kept in full (no voorvoegsel/prefix stripping as separate
content) but are normalized to match how the actually-used matcher -
personal_info.py's word_token in org-security-workflows - tokenizes
words: letters only, with internal -/' between groups, no periods, no
leading apostrophe, no digits anywhere. Without this, names like
"St. Annastraat", "'s-Gravenhage", or "12e Septemberlaan" would never
match scanned text, since that matcher compares the literal
(lowercased) list entry against the space-joined tokens it extracts —
see WORD_TOKEN_RE below.

Excludes highway-style names (A10, A 15, N201, Rijksweg + number),
1-2 letter names (too short to mean anything, guaranteed false
positives), and data artefacts (names starting with - or unusual quote
characters).

Usage:
    python parse-dutch-street-names.py                  # reads from ./data/
    python parse-dutch-street-names.py /path/to/files/  # reads from given dir
"""

import argparse
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

NS_OBJ   = "www.kadaster.nl/schemas/lvbag/imbag/objecten/v20200601"
NS_HIST  = "www.kadaster.nl/schemas/lvbag/imbag/historie/v20200601"
NS_SL    = "http://www.kadaster.nl/schemas/standlevering-generiek/1.0"
NS_BAG   = "http://www.kadaster.nl/schemas/lvbag/extract-deelbestand-lvc/v20200601"

TAG_STAND     = f"{{{NS_SL}}}stand"
TAG_BAG_OBJ   = f"{{{NS_BAG}}}bagObject"
TAG_OPR       = f"{{{NS_OBJ}}}OpenbareRuimte"
TAG_NAAM      = f"{{{NS_OBJ}}}naam"
TAG_TYPE      = f"{{{NS_OBJ}}}type"
TAG_STATUS    = f"{{{NS_OBJ}}}status"
TAG_VOORKOMEN = f"{{{NS_OBJ}}}voorkomen"
TAG_HIST_VOOR = f"{{{NS_HIST}}}Voorkomen"
TAG_EIND      = f"{{{NS_HIST}}}eindGeldigheid"

ACTIVE_STATUS = "Naamgeving uitgegeven"
OUTPUT_DIR    = "output"
OUTPUT_FILE   = "street_names.txt"

# A highway code token, e.g. "A15", "A 15", "A-15", "N281", "S15",
# matched anywhere in the name (word-boundary-safe) to catch both
# bare highway names and names that merely reference one, e.g.
# "A 73 Rijksweg" or "Staphorst Rijksweg A28".
HIGHWAY_CODE_RE = re.compile(r"(?<![A-Za-z0-9])[ANS][\s-]?\d{1,3}(?![A-Za-z0-9])")

# Mirrors personal_info.py's word_token (org-security-workflows, the
# actually-used matcher): letter runs only, with an internal - or '
# allowed to join two such runs (e.g. "'s-Gravenhage" -> "s-Gravenhage",
# "Nieuw-Vennep" stays whole). A leading apostrophe or any period is
# never part of a token, so both are dropped.
#
# Digits are excluded on purpose, same as the real matcher: house
# numbers are matched separately there, so a digit anywhere in a name
# (leading ordinal like "12e", a plot number like "Archipel 10") can
# never be part of what actually gets matched against scanned text -
# keeping it in the stored name would just make the entry match nothing.
# normalize() drops it the same way the real matcher's tokenizer would,
# e.g. "12e Septemberlaan" -> "e Septemberlaan", "Archipel 10" ->
# "Archipel", "Apollo 11-laan" -> "Apollo laan". The matcher works on
# the filtered token sequence (digits already removed), not the raw
# text, so "Apollo laan" still matches "Apollo 11-laan" in a scanned
# file - "Apollo" and "laan" end up adjacent in that sequence.
WORD_TOKEN_RE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)


def normalize(naam: str) -> str:
    return " ".join(WORD_TOKEN_RE.findall(naam))


def is_invalid(naam: str) -> bool:
    if HIGHWAY_CODE_RE.search(naam):
        return True
    if naam.lower().startswith(("rijksweg", "autosnelweg", "autoweg")):
        return True
    if "rijksweg" in naam.lower() and any(c.isdigit() for c in naam):
        return True
    if naam.startswith("-"):
        return True
    if naam.startswith("'") and naam[1:2].lower() not in ("s", "t", "n"):
        return True
    if '"' in naam:
        return True
    return False


def parse_file(filepath: str, names: Counter) -> int:
    tree = ET.parse(filepath)
    count = 0
    for stand in tree.getroot().iter(TAG_STAND):
        bag_obj = stand.find(TAG_BAG_OBJ)
        if bag_obj is None:
            continue
        opr = bag_obj.find(TAG_OPR)
        if opr is None:
            continue

        if opr.findtext(TAG_STATUS) != ACTIVE_STATUS:
            continue
        if opr.findtext(TAG_TYPE) != "Weg":
            continue

        voorkomen = opr.find(TAG_VOORKOMEN)
        if voorkomen is not None:
            hist = voorkomen.find(TAG_HIST_VOOR)
            if hist is not None and hist.find(TAG_EIND) is not None:
                continue

        naam = opr.findtext(TAG_NAAM)
        if not naam or is_invalid(naam):
            continue

        naam = normalize(naam)
        # Re-check length after normalization: digit-stripping can reduce
        # something like "GP100" (a parcel code, not a real street) down
        # to "GP" - too short to mean anything once the digits are gone.
        if naam and len(naam) > 2:
            names[naam] += 1
            count += 1

    return count


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("input_dir", nargs="?", default="data")
    p.add_argument("--top", type=int, default=None,
                   help="Only write the N most common street names (by number "
                        "of places they occur in), sorted by frequency")
    return p.parse_args()


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    files = sorted(input_dir.glob("*.xml"))

    if not files:
        print(f"No XML files found in {input_dir}")
        return

    print(f"Processing {len(files)} file(s) from {input_dir}...")
    names = Counter()
    for i, f in enumerate(files, 1):
        count = parse_file(str(f), names)
        print(f"  [{i}/{len(files)}] {f.name}: {count} active streets, {len(names)} unique so far")

    # Merge single-letter suffix variants into their base name,
    # e.g. "Wethouder Vrankenstraat A" -> "Wethouder Vrankenstraat".
    # Only collapses on a literal trailing single letter, and only if the
    # base name itself exists — NOT any name that merely shares a leading
    # word with some other name (that would wrongly merge e.g.
    # "Pieter Aertszstraat" into an unrelated street just called "Pieter").
    merged = Counter()
    for naam, cnt in names.items():
        words = naam.split(" ")
        if len(words) > 1 and len(words[-1]) == 1 and words[-1].isalpha() \
                and " ".join(words[:-1]) in names:
            merged[" ".join(words[:-1])] += cnt
        else:
            merged[naam] += cnt

    removed = len(names) - len(merged)

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    if args.top:
        output_file = output_dir / f"street_names_top{args.top}.txt"
        ordered = [name for name, _ in merged.most_common(args.top)]
    else:
        output_file = output_dir / OUTPUT_FILE
        ordered = sorted(merged)

    print(f"\nWriting {len(ordered)} street names to {output_file} "
          f"({removed} suffix variants merged into base names)...")
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("\n".join(ordered) + "\n")
    print("Done.")


if __name__ == "__main__":
    main()