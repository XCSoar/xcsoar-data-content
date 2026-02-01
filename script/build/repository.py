#!/bin/env python3
"""
Generate XCSoar's repository file (https://download.xcsoar.org/repository).

Execute in the git repository root dir.
"""

import datetime
import json
from pathlib import Path
import subprocess
import sys
import requests
import re
from typing import Optional

from iso3166 import countries
from aerofiles.seeyou.reader import Reader as CupReader
from aerofiles.openair.reader import Reader as OpenAirReader
from aerofiles.errors import ParserError


def git_commit_datetime(filename: Path) -> datetime.datetime:
    """Return naive UTC datetime of filename's last git commit."""
    cmd = ["git", "log", "-1", "--format=%ct", "--", filename]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    try:
        # Use timezone-aware conversion then convert to naive UTC
        timestamp = int(out)
        dt = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
        # Return naive datetime (as documented) by removing timezone info
        return dt.replace(tzinfo=None)
    except (ValueError, OSError):
        # Return naive UTC datetime
        return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def guess_area(name: str) -> str:
    """From name (e.g. USA-PG-REG1-4), try to guess and return the ISO3166.1-alpha2 code, else empty string."""
    area = ""
    prefix = name.split(".")[0].split("-")[0]
    try:
        area = countries.get(prefix).alpha2.lower()
    except KeyError:
        print(f"Could not guess the country code (ISO 3166 alpha2) for: {name}")
    return area


def calculate_bbox_cup(cup_file: Path) -> Optional[str]:
    """Calculate bounding box from a waypoint CUP file.
    Returns bbox string in format 'min_lon,min_lat,max_lon,max_lat' or None if error."""
    try:
        with open(cup_file, encoding='utf-8') as fp:
            reader = CupReader()
            data = reader.read(fp)
        waypoints = data.get("waypoints", [])

        if not waypoints:
            return None

        lats = [wp["latitude"] for wp in waypoints]
        lons = [wp["longitude"] for wp in waypoints]

        return _calculate_bbox_from_coords(lons, lats)
    except (OSError, ValueError, KeyError, ParserError, IndexError) as e:
        print(f"Warning: Could not calculate bbox for {cup_file}: {e}")
        return None


def _extract_coords_from_airspace(airspace: dict, all_lons: list, all_lats: list):
    """Extract coordinates from an airspace dictionary.

    Handles aerofiles structure with 'elements' containing points, arcs, circles, etc.
    Based on aerofiles documentation: elements have 'location' (list [lat, lon]) for points,
    and 'center' (list [lat, lon]) for circles/arcs.
    """
    # Extract from labels (if present) - labels are [lat, lon]
    labels = airspace.get("labels", [])
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, (list, tuple)) and len(label) >= 2:
                all_lats.append(float(label[0]))
                all_lons.append(float(label[1]))

    # Extract from elements
    elements = airspace.get("elements", [])
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue

            element_type = element.get("type")

            # Handle point elements (DP in OpenAir) - location is [lat, lon]
            if element_type == "point":
                location = element.get("location")
                if isinstance(location, (list, tuple)) and len(location) >= 2:
                    all_lats.append(float(location[0]))
                    all_lons.append(float(location[1]))

            # Handle circle and arc elements (DC, DA, DB in OpenAir) - center is [lat, lon]
            if element_type in ("circle", "arc"):
                center = element.get("center")
                if isinstance(center, (list, tuple)) and len(center) >= 2:
                    all_lats.append(float(center[0]))
                    all_lons.append(float(center[1]))


def _calculate_bbox_from_coords(all_lons: list, all_lats: list) -> Optional[str]:
    """Calculate bbox string from coordinate lists.
    Returns bbox string in format 'min_lon,min_lat,max_lon,max_lat' or None if empty."""
    if not all_lats or not all_lons:
        return None
    return f"{min(all_lons)},{min(all_lats)},{max(all_lons)},{max(all_lats)}"


def _parse_airspace_records(reader: OpenAirReader):
    """Parse airspace records from OpenAirReader and extract coordinates.
    Returns tuple of (all_lons, all_lats) lists."""
    all_lats = []
    all_lons = []

    # Reader is an iterator that yields (record, error) tuples
    for record, error in reader:
        if error:
            continue  # Skip records with errors
        if record and record.get("type") == "airspace":
            _extract_coords_from_airspace(record, all_lons, all_lats)

    return all_lons, all_lats


def calculate_bbox_airspace(airspace_file: Path) -> Optional[str]:
    """Calculate bounding box from an airspace OpenAir file.
    Returns bbox string in format 'min_lon,min_lat,max_lon,max_lat' or None if error."""
    try:
        with open(airspace_file, encoding='utf-8') as fp:
            reader = OpenAirReader(fp)
            all_lons, all_lats = _parse_airspace_records(reader)
        return _calculate_bbox_from_coords(all_lons, all_lats)
    except (OSError, ValueError, KeyError) as e:
        print(f"Warning: Could not calculate bbox for {airspace_file}: {e}")
        return None


def calculate_bbox_airspace_from_content(content: str) -> Optional[str]:
    """Calculate bounding box from airspace OpenAir file content (string).
    Returns bbox string in format 'min_lon,min_lat,max_lon,max_lat' or None if error."""
    try:
        from io import StringIO
        fp = StringIO(content)
        reader = OpenAirReader(fp)
        all_lons, all_lats = _parse_airspace_records(reader)
        return _calculate_bbox_from_coords(all_lons, all_lats)
    except (ValueError, KeyError) as e:
        print(f"Warning: Could not calculate bbox from airspace content: {e}")
        return None


def get_bbox_from_map_json(json_file: Path) -> Optional[str]:
    """Extract bounding box from source map JSON file.
    Returns bbox string in format 'min_lon,min_lat,max_lon,max_lat' or None if error."""
    try:
        if not json_file.exists():
            return None

        with json_file.open() as f:
            data = json.load(f)
        bbox = data.get("bounding_box")

        if not bbox or len(bbox) != 4:
            return None

        # Format: [min_lon, min_lat, max_lon, max_lat]
        return f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not extract bbox from {json_file}: {e}")
        return None


def _calculate_bbox_for_file(datafile: Path, file_type: str) -> Optional[str]:
    """Calculate bbox for a georeferencable file based on its type."""
    suffix = datafile.suffix.lower()
    if file_type == "waypoint" and suffix == ".cup":
        return calculate_bbox_cup(datafile)
    elif file_type == "airspace" and suffix == ".txt":
        return calculate_bbox_airspace(datafile)
    return None


def generate_content(data_dir: Path, url: str, skip_openaip_cup: bool = False) -> str:
    """Generate repository entries for content files.

    Args:
        data_dir: Directory containing content files ($TYPE/[country,region,global]/*.*)
        url: Base URL for content files
        skip_openaip_cup: If True, skip OpenAIP CUP files (handled via remote entries)
    """
    rv = ""
    for xcs_type in sorted(data_dir.iterdir()):
        for geo in sorted(xcs_type.iterdir()):
            if geo.name == "0_META":
                continue  # Web/metadata artefacts, not for repository
            rv += f"\n# Data location: {data_dir.name}, type: {xcs_type.name}, geography: {geo.name}.\n"
            for datafile in sorted(geo.iterdir()):
                if datafile.name.lower().endswith(".json"):
                    continue

                # Skip OpenAIP CUP files if requested (handled via remote entries)
                if (skip_openaip_cup and xcs_type.name == "waypoint" and
                    datafile.suffix.lower() == ".cup" and "OpenAIP" in datafile.name):
                    continue

                rv += f"""
name={datafile.name}
uri={url + str(datafile.relative_to(data_dir))}
type={xcs_type.name}
area={guess_area(datafile.stem)}
update={git_commit_datetime(datafile).date().isoformat()}
"""
                description = json_description(datafile)
                if description:
                    rv += f"description={description}\n"

                # Calculate and add bbox for georeferencable files
                bbox = _calculate_bbox_for_file(datafile, xcs_type.name)
                if bbox:
                    rv += f"bbox={bbox}\n"
    return rv

def json_update(json_filename: Path) -> str:
    """Return the value of json_filename's "update" key."""
    if json_filename.suffix.lower() != ".json":
        json_filename = json_filename.with_suffix(".json")

    if json_filename.exists():
        try:
            with json_filename.open() as f:
                data = json.load(f)
            return data.get("update", "")
        except (OSError, json.JSONDecodeError):
            return ""
    return ""

def generate_source(data_dir: Path, url: str) -> str:
    """Generate repository entries for source files (maps).

    Args:
        data_dir: Directory containing source files ($TYPE/[country,region,global]/*.*)
        url: Base URL for source files
    """
    rv = ""
    for xcs_type in sorted(data_dir.iterdir()):
        for geo in sorted(xcs_type.iterdir()):
            if geo.name == "0_META":
                continue  # Web/metadata artefacts, not for repository
            rv += f"\n# Data location: {data_dir.name}, type: {xcs_type.name}, geography: {geo.name}.\n"
            for datafile in sorted(geo.iterdir()):
                # Extract bbox from source map JSON file
                bbox = None
                if xcs_type.name == "map" and datafile.suffix.lower() == ".json":
                    bbox = get_bbox_from_map_json(datafile)

                bbox_line = f"bbox={bbox}\n" if bbox else ""
                base_name = datafile.stem
                base_uri = str(datafile.relative_to(data_dir)).replace(".json", "")

                rv += f"""
name={base_name}_HighRes.xcm
uri={url}{base_uri}_HighRes.xcm
type={xcs_type.name}
area={guess_area(base_name)}
update={git_commit_datetime(datafile).date().isoformat()}
{bbox_line}name={base_name}.xcm
uri={url}{base_uri}.xcm
type={xcs_type.name}
area={guess_area(base_name)}
update={git_commit_datetime(datafile).date().isoformat()}
{bbox_line}"""
    return rv


def generate_asp_openaip():
    """Generate OpenAIP repository entries from cloud storage (airspace files)."""
    base_url = "https://storage.googleapis.com/29f98e10-a489-4c82-ae5e-489dbcd4912f/"
    url = base_url
    openaip_index = ""
    rv = ""

    # Fetch all pages of the OpenAIP index
    while True:
        response = requests.get(url, timeout=30)
        xml_data = response.text
        openaip_index += xml_data

        match = re.search(r"<NextMarker>(.*?)</NextMarker>", xml_data)
        if not match:
            break
        url = f"{base_url}?marker={match.group(1)}"

    contents = re.findall(r"<Contents>(.*?)</Contents>", openaip_index)
    for content in contents:
        key_match = re.search(r"<Key>(.*?)</Key>", content)
        if not key_match or "asp_v2.txt" not in key_match.group(1):
            continue

        size_match = re.search(r"<Size>(.*)</Size>", content)
        if not size_match:
            continue

        size = int(size_match.group(1))
        if size < 384:
            continue

        key = key_match.group(1)
        print(f"OK: {key} {size}")

        updatedate_match = re.search(r"<LastModified>(.*?)</LastModified>", content)
        if not updatedate_match:
            continue

        countrycode = key[:2].upper()
        try:
            countryname = countries.get(countrycode).name
        except KeyError:
            continue

        # Download and parse airspace file to calculate bbox
        bbox = None
        try:
            file_url = base_url + key
            file_response = requests.get(file_url, timeout=30)
            if file_response.status_code == 200:
                bbox = calculate_bbox_airspace_from_content(file_response.text)
        except Exception as e:
            print(f"Warning: Could not download/parse OpenAIP airspace for {countrycode}: {e}")

        bbox_line = f"bbox={bbox}\n" if bbox else ""

        rv += f"""
name={countrycode}-ASP-National-OpenAIP.txt
uri={base_url}{key}
type=airspace
description={countryname} Airspace from OpenAIP
area={countrycode}
update={updatedate_match.group(1)}
{bbox_line}"""
    return rv


def json_uri(json_filename: Path) -> str:
    """Return the value of json_filename's "uri" key."""
    with json_filename.open() as f:
        data = json.load(f)
    return data["uri"]


def json_description(json_filename: Path) -> str:
    """Return the value of json_filename's "description" key."""
    if json_filename.suffix.lower() != ".json":
        json_filename = json_filename.with_suffix(".json")

    if json_filename.exists():
        try:
            with json_filename.open() as f:
                data = json.load(f)
            return data.get("description", "")
        except (OSError, json.JSONDecodeError):
            return ""
    return ""


def json_bbox(json_filename: Path) -> Optional[str]:
    """Return the value of json_filename's "bbox" key if present."""
    if json_filename.suffix.lower() != ".json":
        json_filename = json_filename.with_suffix(".json")

    if json_filename.exists():
        try:
            with json_filename.open() as f:
                data = json.load(f)
            bbox = data.get("bbox")
            if bbox:
                if isinstance(bbox, list) and len(bbox) == 4:
                    return f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
                elif isinstance(bbox, str):
                    return bbox
        except (OSError, json.JSONDecodeError):
            pass
    return None


def generate_remote(data_dir: Path, out_content_dir: Path = None) -> str:
    """Generate repository entries for remote files.

    Args:
        data_dir: Directory containing remote metadata files ($TYPE/[country,region,global]/*.*)
        out_content_dir: Optional output content directory to check for generated files
                        (e.g., OpenAIP CUP files for bbox calculation)
    """
    rv = ""
    for xcs_type in sorted(data_dir.iterdir()):
        for geo in sorted(xcs_type.iterdir()):
            rv += f"\n# Data location: {data_dir.name}, type: {xcs_type.name}, geography: {geo.name}.\n"
            for datafile in sorted(geo.iterdir()):
                rv += f"""
name={datafile.stem}
uri={json_uri(datafile)}
type={xcs_type.name}
area={guess_area(datafile.stem)}
update={json_update(datafile) or git_commit_datetime(datafile).date().isoformat()}
"""
                description = json_description(datafile)
                if description:
                    rv += f"description={description}\n"

                # Check for optional bbox in metadata JSON
                bbox = json_bbox(datafile)

                # If no bbox in JSON and this is an OpenAIP waypoint CUP file,
                # try to find the generated file in output directory
                if (not bbox and xcs_type.name == "waypoint" and
                    datafile.stem.endswith("-OpenAIP.cup") and
                    out_content_dir and out_content_dir.exists()):
                    # datafile.stem is already "NAME.cup" (without .json), so use it directly
                    generated_cup = out_content_dir / "waypoint" / geo.name / datafile.stem
                    if generated_cup.exists():
                        bbox = calculate_bbox_cup(generated_cup)

                if bbox:
                    rv += f"bbox={bbox}\n"
    return rv


if __name__ == "__main__":
    """
    ./data/[content,remote,source]/$TYPE/[country,region,global]/*.*
    Also processes files from output directory (for OpenAIP generated files)
    """
    root_dir = Path("data")
    content_dir = root_dir / Path("content")
    source_dir = root_dir / Path("source")
    remote_dir = root_dir / Path("remote")

    base_url = "http://download.xcsoar.org/"

    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    # Also process content from output directory (for OpenAIP generated files)
    out_content_dir = out_dir / Path("content")

    repo = ""
    repo += generate_content(data_dir=content_dir, url=base_url + "content/")
    # Process OpenAIP generated files from output directory, but skip OpenAIP CUP files
    # (they're handled via remote entries with bbox calculated from the generated files)
    if out_content_dir.exists():
        repo += generate_content(data_dir=out_content_dir, url=base_url + "content/", skip_openaip_cup=True)
    repo += generate_source(data_dir=source_dir, url=base_url + "source/")
    repo += generate_remote(data_dir=remote_dir, out_content_dir=out_content_dir)
    repo += generate_asp_openaip()

    out_path = out_dir / "repository"

    with open(out_path, "w") as f:
        f.write(repo)
    print(f"Created: {out_path}")
