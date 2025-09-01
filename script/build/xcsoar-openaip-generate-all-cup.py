#!/bin/env python3

import requests
import re
import argparse
import os
import json
from iso3166 import countries

# Function to parse command line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description="Process OpenAIP data files.")
    parser.add_argument("output", help="Directory to save the files to")
    return parser.parse_args()

# Function to ensure directories exist
def ensure_directories(output_dir, metajson_dir):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(metajson_dir, exist_ok=True)

# Function to fetch data from the server with pagination
def fetch_data(base_url):
    url = base_url
    openaip_index = ""
    while True:
        response = requests.get(url)
        xml_data = response.text
        openaip_index += xml_data

        # Search for the NextMarker tag in the XML data
        match = re.search(r"<NextMarker>(.*?)</NextMarker>", xml_data)
        if not match:
            break
        next_marker = match.group(1)
        url = f"{base_url}?marker={next_marker}"

    return openaip_index

# Function to process a single content block
def process_content_block(content, base_url, output_dir, metajson_dir):
    key = re.search(r"<Key>(.*?)</Key>", content)
    if not key or not re.search(r"\.cup$", key.group(1)):
        return

    country_code = key.group(1)[:2]
    file_url = base_url + key.group(1)
    cup_file_path = os.path.join(
        output_dir, f"{country_code.upper()}-WPT-National-OpenAIP.cup"
    )

    # Download file content
    file_content = requests.get(file_url).text

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

    # Fetch data
    base_url = "https://storage.googleapis.com/29f98e10-a489-4c82-ae5e-489dbcd4912f/"
    openaip_index = fetch_data(base_url)

    # Process each content block
    contents = re.findall(r"<Contents>(.*?)</Contents>", openaip_index)
    for content in contents:
        process_content_block(content, base_url, output_dir, metajson_dir)

if __name__ == "__main__":
    main()
