#!/bin/env python3

import argparse
import json
import os

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
        line for line in content.splitlines() if not line.startswith(header)
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
