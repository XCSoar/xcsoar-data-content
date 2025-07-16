#!/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate XCSoar's repository file (https://download.xcsoar.org/repository).

Execute in the git repository root dir.
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import requests
from iso3166 import countries


def git_commit_datetime(filename: Path) -> datetime.datetime:
    """Return naive UTC datetime of filename's last git commit."""
    cmd = ["git", "log", "-1", "--format=%ct", "--", str(filename)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    try:
        return datetime.datetime.utcfromtimestamp(int(out))
    except Exception:
        return datetime.datetime.utcnow()


def guess_area(name: str) -> str:
    """
    Guess the ISO-3166-1 alpha-2 code from a file name like 'USA_PG_REG1-4.*'.
    Returns empty string if no match found.
    """
    prefix = name.split(".")[0].split("_")[0]
    try:
        return countries.get(prefix).alpha2.lower()
    except KeyError:
        print(f"Could not guess the country code (ISO 3166 alpha2) for: {name}")
        return ""


def json_update(json_filename: Path) -> str:
    """
    Return the value of json_filename's 'update' key.

    The special value 'daily' is expanded to today's date (UTC, ISO format).
    """
    if json_filename.suffix.lower() != ".json":
        return ""
    data = json.load(json_filename.open())
    value = data.get("update", "")
    if value == "daily":
        return datetime.datetime.utcnow().date().isoformat()
    return value


def json_description(json_filename: Path) -> str:
    """Return the description from a *.json file if present."""
    if json_filename.suffix.lower() != ".json":
        return ""
    data = json.load(json_filename.open())
    return data.get("description", "")


def json_uri(json_filename: Path) -> str:
    """Return the URI from a *.json file (mandatory field)."""
    data = json.load(json_filename.open())
    return data["uri"]


def get_update_date(datafile: Path) -> str:
    """Prefer the JSON 'update' field, fall back to git commit date."""
    return json_update(datafile) or git_commit_datetime(datafile).date().isoformat()


def generate_content(data_dir: Path, url: str) -> str:
    """Generate repository entries for raw content files."""
    rv = ""
    for xcs_type in sorted(data_dir.iterdir()):
        for geo in sorted(xcs_type.iterdir()):
            rv += f"\n# Data location: {data_dir.name}, type: {xcs_type.name}, geography: {geo.name}.\n"
            for datafile in sorted(geo.iterdir()):
                if datafile.suffix.lower() != ".json":
                    rv += f"""
name={datafile.name}
uri={url}{datafile.relative_to(data_dir)}
type={xcs_type.name}
area={guess_area(datafile.stem)}
update={get_update_date(datafile)}
"""
                    desc = json_description(datafile)
                    if desc:
                        rv += f"description={desc}\n"
    return rv


def generate_source(data_dir: Path, url: str) -> str:
    """Generate repository entries for *.xcm files built from JSON sources."""
    rv = ""
    for xcs_type in sorted(data_dir.iterdir()):
        for geo in sorted(xcs_type.iterdir()):
            rv += f"\n# Data location: {data_dir.name}, type: {xcs_type.name}, geography: {geo.name}.\n"
            for datafile in sorted(geo.iterdir()):
                if datafile.suffix.lower() == ".json":
                    stem = datafile.stem
                    rel = str(datafile.relative_to(data_dir))
                    rv += f"""
name={stem}_HighRes.xcm
uri={url}{rel.replace(".json", "_HighRes.xcm")}
type={xcs_type.name}
area={guess_area(stem)}
update={get_update_date(datafile)}

name={stem}.xcm
uri={url}{rel.replace(".json", ".xcm")}
type={xcs_type.name}
area={guess_area(stem)}
update={get_update_date(datafile)}
"""
    return rv


def generate_asp_openaip() -> str:
    """Generate OpenAIP airspace entries fetched from GCS bucket."""
    base_url = "https://storage.googleapis.com/29f98e10-a489-4c82-ae5e-489dbcd4912f/"
    url = base_url
    openaip_index = ""
    rv = ""

    # Bucket is paginated – follow NextMarker.
    while True:
        xml = requests.get(url, timeout=30).text
        openaip_index += xml
        match = re.search(r"<NextMarker>(.*?)</NextMarker>", xml)
        if not match:
            break
        url = f"{base_url}?marker={match.group(1)}"

    for content in re.findall(r"<Contents>(.*?)</Contents>", openaip_index):
        key = re.search(r"<Key>(.*?)</Key>", content)
        if not key or "asp_v2.txt" not in key.group(1):
            continue
        size = int(re.search(r"<Size>(.*)</Size>", content).group(1))
        if size < 384:  # Ignore obviously broken tiny files.
            continue

        updated = re.search(r"<LastModified>(.*?)</LastModified>", content)
        countrycode = key.group(1)[:2].upper()
        try:
            countryname = countries.get(countrycode).name
        except KeyError:
            countryname = countrycode

        rv += f"""
name={countrycode}-ASP-National-OpenAIP.txt
uri={base_url}{key.group(1)}
type=airspace
description={countryname} Airspace from OpenAIP
area={countrycode}
update={updated.group(1) if updated else ""}
"""
    return rv


def generate_remote(data_dir: Path) -> str:
    """Generate entries that reference external URIs stored in JSON files."""
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
update={git_commit_datetime(datafile).date().isoformat()}
"""
                desc = json_description(datafile)
                if desc:
                    rv += f"description={desc}\n"
    return rv


if __name__ == "__main__":
    """
    Expected directory structure (relative to repo root):

    data/
      content/TYPE/[country|region|global]/*
      source /TYPE/[country|region|global]/*.json
      remote /TYPE/[country|region|global]/*.json
    """
    root_dir = Path("data")
    content_dir = root_dir / "content"
    source_dir = root_dir / "source"
    remote_dir = root_dir / "remote"

    base_url = "http://download.xcsoar.org/"

    repository_text = (
        generate_content(content_dir, base_url + "content/")
        + generate_source(source_dir, base_url + "source/")
        + generate_remote(remote_dir)
        + generate_asp_openaip()
    )

    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "repository"

    with open(out_path, "w") as fp:
        fp.write(repository_text)

    if json_filename.exists():


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        data = json.load(json_filename.open())


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        update_value = data.get("update", "")


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        if update_value == "daily":


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
            return datetime.datetime.now().date().isoformat()


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        return update_value


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
    else:


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        return str("")


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
    """Return the value of json_filename's "update" key, or today's date if value is "daily"."""


def json_update(json_filename: Path) -> str:


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
    """Return the value of json_filename's "update" key, or today's date if value is "daily"."""


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
    if not json_filename.suffix.lower() == ".json":


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        json_filename = json_filename.with_suffix(".json")


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()



def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
    if json_filename.exists():


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        data = json.load(json_filename.open())


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        update_value = data.get("update", "")


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_datetime(datafile).date().isoformat()
        if update_value == "daily":


def get_update_date(datafile: Path) -> str:
    """Get update date from JSON file if available, otherwise use git commit datetime."""
    json_update_value = json_update(datafile)
    if json_update_value:
        return json_update_value
    else:
        return git_commit_dateti


def generate_remote(data_dir: Path) -> str:
    """data_dir/$TYPE/[country,region,global]/*.*"""
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
update={git_commit_datetime(datafile).date().isoformat()}
"""
                if json_description(datafile):
                    rv += f"""description={json_description(datafile)}
"""
    return rv


if __name__ == "__main__":
    """
    ./data/[content,remote,source]/$TYPE/[country,region,global]/*.*
    """
    root_dir = Path("data")
    content_dir = root_dir / Path("content")
    source_dir = root_dir / Path("source")
    remote_dir = root_dir / Path("remote")

    base_url = "http://download.xcsoar.org/"

    repo = ""
    repo += generate_content(data_dir=content_dir, url=base_url + "content/")
    repo += generate_source(data_dir=source_dir, url=base_url + "source/")
    repo += generate_remote(data_dir=remote_dir)
    repo += generate_asp_openaip()

    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "repository"

    with open(out_path, "w") as f:
        f.write(repo)
    print(f"Created: {out_path}")
