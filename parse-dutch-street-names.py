"""
Parses BAG OPR (OpenbareRuimte) XML extract files and writes
a deduplicated list of active Dutch street names (type Weg only),
one per line, for use in the org-security-scanner PII detection.

Excludes highway-style names (A10, N201, Rijksweg) and data artefacts
(names starting with - or unusual quote characters).

For names containing a dot, extracts only the part after the last
dotted-token group (initials, titles, abbreviations). Names where
nothing meaningful remains are discarded.

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

HIGHWAY_RE = re.compile(r"^[ANS]\d+", re.IGNORECASE)

# 's-Foo, 's Foo, 't Foo, 'n Foo
DUTCH_ARTICLE_RE = re.compile(r"^'[stn]-?\s*", re.IGNORECASE)

# A dotted-token group: one or more sequences of 1-4 letters + dot + optional space
# Used to find the last such group in a name and take what follows.
LAST_DOTTED_RE = re.compile(r"(?:[A-Za-z]{1,4}\.\s*)+")


def clean(naam: str) -> str:
    # Strip Dutch articles
    naam = DUTCH_ARTICLE_RE.sub("", naam).strip()

    # If the name contains a dot, take everything after the last dotted-token group
    if "." in naam:
        matches = list(LAST_DOTTED_RE.finditer(naam))
        if matches:
            remainder = naam[matches[-1].end():].strip()
            if not remainder:
                return ""   # nothing left, will be discarded
            naam = remainder

    return naam


def is_invalid(naam: str) -> bool:
    if HIGHWAY_RE.match(naam):
        return True
    if naam.lower().startswith(("rijksweg", "autosnelweg", "autoweg")):
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

        naam = clean(naam)
        if naam:
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