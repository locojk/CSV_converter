#!/usr/bin/env python3
import csv
import re
from pathlib import Path
import argparse
from typing import Iterable, Dict, List, Tuple
import sys


def last_token_after_dot(s: str) -> str:
    parts = s.split(".")
    return parts[-1].strip() if parts else s.strip()

def split_type_number(obj_ref: str):
    """
    'AI1' -> ('AI', '1'), 'AV100' -> ('AV','100'); if no match, returns (obj_ref, '')
    """
    m = re.match(r"^([A-Za-z]+)(\d+)$", obj_ref.strip())
    if m:
        return m.group(1).upper(), m.group(2)
    return obj_ref.strip(), ""

def _normalize_mojibake(s: str) -> str:
    """Fix common mojibake artifacts like 'Â°' -> '°' and NBSPs.
    Also collapses stray replacement chars preceding C/F.
    """
    if not s:
        return s
    # Normalize non-breaking space and zero-widths
    s = s.replace("\u00A0", " ").replace("\u200B", "")
    # Fix typical UTF-8->cp1252 mojibake for degree sign
    s = s.replace("Â°", "°")
    # Fix replacement-char sequences occasionally seen
    s = s.replace("�C", "°C").replace("�F", "°F")
    # If any lone 'Â' remain, drop them
    s = s.replace("Â", "")
    return s

def _clean_ws(s: str) -> str:
    """Normalize mojibake, collapse whitespace, trim ends."""
    if s is None:
        return ""
    s = _normalize_mojibake(str(s))
    # Collapse any runs of whitespace to single spaces, then trim
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _sanitize_cell(s: str, empty_placeholder: str) -> str:
    """Clean whitespace and replace empties with a placeholder."""
    cleaned = _clean_ws(s)
    return cleaned if cleaned != "" else empty_placeholder

def extract_dev_number_from_ref(ref: str) -> str:
    """
    Extracts DEV number directly from column 0, expected like:
      "//Morisset/10409.AV28" -> "10409"
    Looks for digits between a slash/backslash and a dot.
    Returns '' if not found.
    """
    m = re.search(r"[\\/](\d+)\.", ref)
    return m.group(1) if m else ""

def extract_units(value_field: str) -> str:
    """
    Extracts the units from a value string like '23.1 °C' -> '°C', '0.0 L/s' -> 'L/s', '10 %' -> '%'
    If no units present, returns ''.
    """
    s = value_field.strip().strip('"').replace("'", "")
    s = _normalize_mojibake(s)
    # Common pattern: "<number> <units...>"
    # Accept negative/decimal numbers, optionally scientific, then spaces then unit tokens
    m = re.match(r"^[\s]*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s+(.+?)\s*$", s)
    units = m.group(1) if m else ""
    units = _normalize_mojibake(units)
    return units

def read_rows(input_path: Path, encoding: str = "utf-8", delimiter: str = ","):
    """
    Reads the source CSV.
    Assumes:
      col0 = full object ref (e.g., '//Morisset/10409.AV28')
      col4 = point name (Name)
      col5 = value-with-units (to derive Units)
    Skips the first line assuming it's a header (as per prior files).
    """
    out = []
    with input_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        # skip header
        try:
            next(reader)
        except StopIteration:
            return out

        for row in reader:
            if len(row) < 6:
                continue
            obj_ref_full = _clean_ws(row[0])
            name = _clean_ws(row[4])
            value_field = row[5].strip()

            obj_ref = last_token_after_dot(obj_ref_full)  # e.g., AV28
            obj_type, obj_num = split_type_number(obj_ref)
            units = extract_units(value_field)
            dev_number = extract_dev_number_from_ref(obj_ref_full)
            dev_name = ""  # user will input per device during writing

            out.append((obj_type, obj_num, name, units, dev_number, dev_name))
    return out

def sort_rows(rows: Iterable[tuple]) -> list:
    rows = list(rows)
    def s_key(r):
        t, n, *_ = r
        try:
            ni = int(n) if n else 0
        except ValueError:
            ni = 0
        return (t.upper(), ni)
    rows.sort(key=s_key)
    return rows

def write_csv(
    rows: Iterable[tuple],
    output_path: Path,
    building: str,
    dev_name_override: str,
    *,
    write_header: bool = True,
    empty_placeholder: str = "",
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Write with UTF-8 BOM for better Excel compatibility (avoids displaying 'Â°')
    with output_path.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out, delimiter=",", lineterminator="\n")
        if write_header:
            writer.writerow(["Object_Type", "Object_Number", "Name", "Units", "Building", "DEV_Number", "DEV_Name"])
        for (obj_type, obj_num, name, units, dev_number, dev_name) in rows:
            # Sanitize each field; fill Building and DEV_Name from user input
            out_row = [
                _sanitize_cell(obj_type, empty_placeholder),
                _sanitize_cell(obj_num, empty_placeholder),
                _sanitize_cell(name, empty_placeholder),
                _sanitize_cell(units, empty_placeholder),
                _sanitize_cell(building, empty_placeholder),
                _sanitize_cell(dev_number, empty_placeholder),
                _sanitize_cell(dev_name_override, empty_placeholder),
            ]
            writer.writerow(out_row)

def process_all_raw(
    raw_dir: Path,
    processed_dir: Path,
    *,
    encoding: str,
    delimiter: str,
    building: str,
    write_header: bool,
    empty_placeholder: str,
):
    csv_files = sorted([p for p in raw_dir.glob("**/*") if p.is_file() and p.suffix.lower() == ".csv"])
    if not csv_files:
        print(f"No CSV files found in '{raw_dir}'. Nothing to do.")
        return
    for src in csv_files:
        rows = read_rows(src, encoding=encoding, delimiter=delimiter)
        if not rows:
            print(f"No usable rows in {src}, skipping.")
            continue
        # Group rows by DEV_Number; use source stem as fallback if missing
        groups: Dict[str, List[Tuple]] = {}
        for r in rows:
            dev_number = r[4] if len(r) >= 5 else ""
            key = dev_number if dev_number else src.stem
            groups.setdefault(key, []).append(r)

        for key, g_rows in groups.items():
            g_rows = sort_rows(g_rows)
            dst = processed_dir / f"{key}.csv"
            try:
                # Prompt user for device name for this output file
                while True:
                    src_display = str(src.relative_to(raw_dir)) if src.is_relative_to(raw_dir) else src.name
                    dev_name_input = _clean_ws(
                        input(f"Enter Device Name for {key} (source: {src_display}): ")
                    )
                    if dev_name_input:
                        break
                    print("Device Name cannot be empty. Please enter a value.")
                write_csv(
                    g_rows,
                    dst,
                    building,
                    dev_name_input,
                    write_header=write_header,
                    empty_placeholder=empty_placeholder,
                )
                print(f"Converted: {src} -> {dst}")
            except PermissionError:
                alt = dst.with_name(f"{dst.stem}_new{dst.suffix}")
                try:
                    # Try alternate filename with same provided device name
                    write_csv(
                        g_rows,
                        alt,
                        building,
                        dev_name_input,
                        write_header=write_header,
                        empty_placeholder=empty_placeholder,
                    )
                    print(
                        f"WARNING: Could not write {dst} (locked?). Wrote to {alt} instead."
                    )
                except PermissionError:
                    print(
                        f"ERROR: Could not write {dst} or {alt}. Close any open apps (e.g., Excel) holding the file and retry."
                    )

def parse_args():
    """
    Kept for future extensibility; no positional args required anymore since
    the script now processes all CSVs under the `raw` directory on each run.
    """
    p = argparse.ArgumentParser(
        description=(
            "Batch-convert all CSV files in ./raw to CSV (UTF-8, comma-delimited) into ./processed with fields: "
            "Object_Type, Object_Number, Name, Units, Building, DEV_Number, DEV_Name. "
            "Prompts once for Building and per file for Device Name."
        )
    )
    p.add_argument("--encoding", default="utf-8", help="File encoding (default: utf-8)")
    p.add_argument("--delimiter", default=",", help="Input CSV delimiter (default: ,)")
    p.add_argument("--building", default="007_MRT", help='Building string (default: "007_MRT")')
    p.add_argument("--no-header", action="store_true", help="Do not write header line")
    p.add_argument(
        "--empty-placeholder",
        default="",
        help="Value to use for empty cells after trimming (default: empty)",
    )
    return p.parse_args()

def main():
    args = parse_args()
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "raw"
    processed_dir = base_dir / "processed"

    # Prompt user once for Building name
    building = ""
    while not building:
        building = _clean_ws(input("Enter Building name (applies to all files): "))
        if not building:
            print("Building name cannot be empty. Please enter a value.")

    process_all_raw(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        encoding=args.encoding,
        delimiter=args.delimiter,
        building=building,
        write_header=not args.no_header,
        empty_placeholder=args.empty_placeholder,
    )

if __name__ == "__main__":
    main()
