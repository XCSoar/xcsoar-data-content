#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import os
import requests


def download_file(url, directory, filename):
    # Make sure the directory exists
    os.makedirs(directory, exist_ok=True)

    # Download the file and save it to the directory
    response = requests.get(url)
    with open(os.path.join(directory, filename), "wb") as f:
        f.write(response.content)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL of the file to download")
    parser.add_argument("directory", help="Directory to save the file to")
    parser.add_argument("filename", help="Name of the file to save as")
    args = parser.parse_args()

    # Download the file
    download_file(args.url, args.directory, args.filename)
