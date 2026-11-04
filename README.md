# Dutch Street Name Extractor

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23918635.svg)](https://doi.org/10.5281/zenodo.23918635)

Parses BAG (Basisregistratie Adressen en Gebouwen) OPR (OpenbareRuimte) extract data from PDOK to generate the list of Dutch street names that the GitHub security infrastructure of the Amsterdam UMC uses to detect addresses. The result is committed as `personal-info-lists/common-dutch-streetnames.txt` in [org-security-workflows](https://github.com/AmsterdamUMC/org-security-workflows).

## Requirements

Python 3.9 or newer and the packages in `requirements.txt`:

```bash
pip install -r requirements.txt
```

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
- Excludes data artefacts (names starting with a dash or containing unusual quote characters)
- Normalizes names the same way the detection splits text into words: letters only, with internal hyphens and apostrophes kept; digits, periods and a leading apostrophe are dropped (e.g. `'s-Gravenhage` becomes `s-Gravenhage`, `12e Septemberlaan` becomes `e Septemberlaan`)
- Excludes names of one or two letters
- Merges single-letter suffix variants (e.g. `Wethouder Vrankenstraat A` → `Wethouder Vrankenstraat`)
- Excludes names that are common English or Dutch words or phrases (such as `As`, `Data`, `Page`, `Contact`), using word frequencies from [wordfreq](https://pypi.org/project/wordfreq/). Street names are matched case-insensitively, so these would otherwise match ordinary text. Single-word names (such as `Plein`, `Brug`, `Bron`) and month and weekday names are filtered more strictly. The thresholds are the `*_ZIPF_*` constants in the script.
- Deduplicates and writes one name per line, UTF-8 encoded

## Using the output

Copy `output/street_names.txt` to `personal-info-lists/common-dutch-streetnames.txt` in org-security-workflows. The normalization above must stay in step with `word_token` in that repository's `personal_info.py`; see the Technical Maintenance Guide (https://doi.org/10.5281/zenodo.22789041), Section 6.4, for the full procedure.
