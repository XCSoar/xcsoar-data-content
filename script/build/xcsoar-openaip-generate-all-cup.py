#!/usr/bin/env python3

import argparse
import json
import os
import re

from iso3166 import countries

from openaip_exports import get as openaip_get, iter_exports


# Function to parse command line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description="Process OpenAIP data files.")
    parser.add_argument("output", help="Directory to save the files to")
    return parser.parse_args()


# Function to ensure directories exist
def ensure_directories(output_dir, metajson_dir):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(metajson_dir, exist_ok=True)


# Function to process a single export object
def process_export(obj, output_dir, metajson_dir):
    if not obj.key.endswith(".cup"):
        return

    country_code = obj.key[:2]
    cup_file_path = os.path.join(
        output_dir, f"{country_code.upper()}-WPT-National-OpenAIP.cup"
    )

    # Download file content
    file_content = openaip_get(obj.url).text

    # Write or append to the `.cup` file, filtering header lines
    write_cup_file(cup_file_path, file_content)

    # Create metadata JSON if applicable
    create_metadata(country_code, metajson_dir)


# A CUP frequency is a VHF airband value such as 118.500, and readers
# enforce it -- aerofiles rejects anything outside ^[123]\d{2}\.\d+$.
# openAIP occasionally carries something else in this column: in
# September 2026 seven Indonesian airports held 534.000, 681.120,
# 905.500, 449.500, 544.250 and 658.900, which look like NDB
# frequencies in kHz.  One of those makes the whole national file
# unreadable, and with it the bounding box that decides whether XCSoar
# offers the file at the pilot's position at all.
RE_CUP_FREQUENCY = re.compile(r"^[123]\d{2}\.\d+$")

# name,code,country,lat,lon,elev,style,rwdir,rwlen,rwwidth,freq,...
FREQ_COLUMN = 10


def _field_span(line, index):
    """Return (start, end) of the index-th CSV field, or None.

    Spliced rather than re-serialised so every other byte of the line
    survives untouched -- openAIP quotes some fields and not others,
    and a round trip through csv.writer would rewrite all of them.
    """
    start = 0
    field = 0
    in_quotes = False
    for pos, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            if field == index:
                return start, pos
            field += 1
            start = pos + 1
    return (start, len(line)) if field == index else None


def clear_impossible_frequency(line):
    """Blank a freq field no CUP reader accepts, keeping the waypoint.

    The frequency is optional metadata; the waypoint is not.  Reported
    rather than dropped quietly, so it can be raised with openAIP.
    """
    if line.startswith("name,"):
        # a header line; write_cup_file() filters these, but the value
        # in its freq column is the word "freq" and must never be
        # mistaken for a bad frequency
        return line

    span = _field_span(line, FREQ_COLUMN)
    if span is None:
        return line

    start, end = span
    value = line[start:end].strip().strip('"')
    if not value or RE_CUP_FREQUENCY.match(value):
        return line

    name = (_field_span(line, 0) or (0, 0))
    print(f"Warning: {line[name[0]:name[1]].strip().strip(chr(34))}: "
          f"dropping frequency {value} (not a CUP frequency)")
    return line[:start] + line[end:]


# Function to write or append to a `.cup` file, filtering redundant headers

def write_cup_file(file_path, content):
    """
    Ensures that the header line ("name,code,country,lat,lon,...") appears only once
    at the top of the .cup file, with the rest of the content appended below it.
    """
    header = "name,code,country,lat,lon,elev,style,rwdir,rwlen,rwwidth,freq,desc"
    all_lines = []

    # Read existing content from the file if it exists
    if os.path.exists(file_path):
        with open(file_path) as file:
            all_lines = file.readlines()

    # Remove any existing headers from the file's content
    all_lines = [line for line in all_lines if not line.startswith(header)]

    # Parse new content, filtering out headers
    new_lines = [
        clear_impossible_frequency(line)
        for line in content.splitlines()
        if not line.startswith(header)
    ]

    # Write the combined content back, starting with the header
    with open(file_path, "w") as file:
        file.write(header + "\n")
        file.writelines(all_lines + [line + "\n" for line in new_lines])


# Function to create metadata JSON for a country
def create_metadata(country_code, metajson_dir):
    metadata = {
        "uri": f"https://download.xcsoar.org/content/waypoint/country/{country_code.upper()}-WPT-National-OpenAIP.cup",
        "description": f"{countries.get(country_code).apolitical_name} aviation data from OpenAIP",
    }
    metadata_file_path = os.path.join(
        metajson_dir, f"{country_code.upper()}-WPT-National-OpenAIP.cup.json"
    )
    with open(metadata_file_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)


# Main function to orchestrate the workflow
def main():
    args = parse_arguments()
    output_dir = os.path.join(args.output, "./content/waypoint/country/")
    metajson_dir = "./data/remote/waypoint/country/"

    # Ensure directories exist
    ensure_directories(output_dir, metajson_dir)

    for obj in iter_exports():
        process_export(obj, output_dir, metajson_dir)


if __name__ == "__main__":
    main()
