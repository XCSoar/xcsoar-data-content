#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys


def parse_record(record_lines):
    name = ""
    uri = ""
    type = ""
    area = ""
    description = ""
    update = ""

    for line in record_lines:
        if line.startswith("name="):
            name = line.split("=")[1]
            name = name.strip()
        elif line.startswith("uri="):
            uri = line.split("=")[1]
            uri = uri.strip()
        elif line.startswith("type="):
            type = line.split("=")[1]
            type = type.strip()
        elif line.startswith("area="):
            area = line.split("=")[1]
            area = area.strip()
        elif line.startswith("description="):
            description = line.split("=")[1]
            description = description.strip()
        elif line.startswith("update="):
            update = line.split("=")[1]
            update = update.strip()

    return {
        "name": name,
        "uri": uri,
        "type": type,
        "area": area,
        "description": description,
        "update": update,
    }


def parse_file(filename):
    records = []
    current_record = []

    with open(filename, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            if line.startswith("name="):
                if current_record:
                    records.append(parse_record(current_record))
                    current_record = []
            current_record.append(line)

        if current_record:
            records.append(parse_record(current_record))

    return records


def sort_records(records):
    return sorted(records, key=lambda x: x["name"])


def format_records(records):
    formatted_records = []

    for record in records:
        formatted_record = []
        formatted_record.append("name={}".format(record["name"]))
        formatted_record.append("uri={}".format(record["uri"]))
        formatted_record.append("type={}".format(record["type"]))
        if record["area"]:
            formatted_record.append("area={}".format(record["area"]))
        if record["description"]:
            formatted_record.append("description={}".format(record["description"]))
        formatted_record.append("update={}".format(record["update"]))
        formatted_record.append("")
        formatted_records.append("\n".join(formatted_record))

    return "\n".join(formatted_records)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_file.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]

    records = parse_file(filename)
    sorted_records = sort_records(records)
    formatted_records = format_records(sorted_records)

    print(formatted_records)
