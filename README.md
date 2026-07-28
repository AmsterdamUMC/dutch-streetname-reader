# Dutch Street Name Extractor

Parses BAG (Basisregistratie Adressen en Gebouwen) OPR (OpenbareRuimte) extract data from PDOK to generate validated street name lists for the org-security-scanner's two-stage PII detection.

## Data Setup

1. Download the full BAG address extract from PDOK:
   ```
   https://service.pdok.nl/kadaster/bag-adressen/atom/adressen.xml
   ```

2. Look for the `9999OPR08072026.zip` file (or the current peildatum equivalent) and download it.

3. Unzip the file and extract all 36 XML files (`9999OPR08072026-000001.xml` through `9999OPR08072026-000036.xml`) into a `data/` directory in the repository root:
   ```
   unzip 9999OPR08072026.zip -d data/
   ```

## Running the Script

Generate a complete street name list (sorted alphabetically):
```bash
python parse-dutch-street-names.py data/
```
Output: `output/street_names.txt`

Generate the top N most common street names (by number of cities they occur in):
```bash
python parse-dutch-street-names.py data/ --top 250
python parse-dutch-street-names.py data/ --top 500
```
Output: `output/street_names_top250.txt`, `output/street_names_top500.txt`

The `output/` folder is created automatically if it doesn't exist.

## What It Does

- Parses only active street records (status `Naamgeving uitgegeven`, type `Weg`)
- Excludes highways (`A##`, `N##`, `S##`, `Rijksweg`, `Autosnelweg`, `Autoweg`)
- Excludes data artefacts (names starting with dash or containing only punctuation)
- Normalizes typographic apostrophes and dashes
- Strips Dutch article prefixes (`'s-`, `'s `, `'t `, `'n `)
- Removes dotted-prefix groups (`Prof.`, `Dr.`, `v.d.`, etc.) and keeps only the street stem
- Merges single-letter suffix variants (e.g. `Wethouder Vrankenstraat A` → `Wethouder Vrankenstraat`)
- Deduplicates and counts occurrences across all municipalities

Output is a deduplicated list of street name stems, one per line, UTF-8 encoded.

## Usage in org-security-scanner

Use the generated `.txt` file as a second-pass validator in the scanner's PII detection pipeline: first match a street suffix pattern, then validate the extracted name against this list.