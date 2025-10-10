# CSV Converter

A simple Python tool to batch-convert raw CSV exports into normalized CSVs for specific usage. It reads all `.csv` files under `raw/`, groups rows by device number, prompts you for a Building name once and a Device Name per output file, and writes results into `processed/`.

## Features
- Scans `raw/` for `.csv` files and processes them all.
- Extracts object type/number, name, and units; groups by `DEV_Number`.
- Prompts once for `Building`, and per output for `DEV_Name`.
- Writes UTF-8 with BOM for Excel compatibility into `processed/`.
- Safe write fallback if an output file is locked by another app.

## Folder Structure
- `main.py`
- `raw/` — place source CSVs here (ignored by git except the folder)
- `processed/` — results are written here (ignored by git except the folder)

## Requirements
- Python 3.8+ (no external dependencies)

## Setup (optional virtual env)
- Windows (PowerShell):
  - `python -m venv .venv`
  - `.\\.venv\\Scripts\\Activate.ps1`
- macOS/Linux:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`

No packages to install — the script uses only the standard library.

## Usage
1. Put your input `.csv` files into `raw/`.
2. Run the script from the project root:
   - Windows: `python .\\main.py`
   - macOS/Linux: `python3 ./main.py`
3. When prompted, enter a Building name (applies to all files).
4. For each output file, enter a Device Name when prompted.
5. Converted files will appear in `processed/` as `<DEV_Number>.csv` (or `<source_stem>.csv` if no DEV number is found).

## Input Assumptions
The script expects a layout similar to prior exports:
- Column 0: Full object reference, e.g. `//Morisset/10409.AV28`
- Column 4: Point name (Name)
- Column 5: Value with units (e.g., `23.1 °C`, `10 %`, `0.0 L/s`)

From these, it derives:
- `Object_Type` and `Object_Number` from the last token after the dot (e.g., `AV28` → `AV`, `28`).
- `Units` from the value string (e.g., `°C`, `%`, `L/s`).
- `DEV_Number` from the path in column 0 (e.g., `10409` in `//Morisset/10409.AV28`). If missing, falls back to the source filename stem.

## Output Format
Each processed CSV contains (header included by default):
- `Object_Type`, `Object_Number`, `Name`, `Units`, `Building`, `DEV_Number`, `DEV_Name`

## CLI Options
- `--encoding` (default: `utf-8`)
- `--delimiter` (default: `,`)
- `--no-header` (omit the header row)

Note: The script currently prompts for `Building` at runtime and ignores the `--building` flag if provided.

## Tips & Troubleshooting
- Excel lock: If an output file is open in Excel, the script tries an alternate filename with `_new` appended. Close the file and re-run if needed.
- Encoding: Output uses UTF-8 with BOM so units like `°C` render correctly in Excel.
- Git hygiene: CSVs in `raw/` and `processed/` are ignored by git; folders are kept with `.gitkeep`.

## File Reference
- `main.py:1` — entry point and processing logic

---
Maintained as a lightweight, no-dependency helper for CSV normalization.
