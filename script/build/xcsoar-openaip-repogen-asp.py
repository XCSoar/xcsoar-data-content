#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import re
from iso3166 import countries

base_url = "https://storage.googleapis.com/29f98e10-a489-4c82-ae5e-489dbcd4912f/"
url = base_url
openaip_index = ""

while True:
    response = requests.get(url)
    xml_data = response.text
    openaip_index += response.text

    # Search for the NextMarker tag in the XML data
    next_marker = None
    match = re.search(r"<NextMarker>(.*?)</NextMarker>", xml_data)
    if match:
        next_marker = match.group(1)
    if next_marker is None:
        break

    url = f"{base_url}?marker={next_marker}"

contents = re.findall(r"<Contents>(.*?)</Contents>", openaip_index)
for content in contents:
    key = re.search(r"<Key>(.*?)</Key>", content)
    if key.group(1).__contains__("asp_extended.txt"):
        updatedate = re.search(r"<LastModified>(.*?)</LastModified>", content)
        countrycode = str.upper(str(key.group(1)[0:2]))
        countryname = countries.get(countrycode).name
        print("name=" + countrycode + "-ASP-national" + "-OpenAIP.txt")
        print("uri=" + base_url + key.group(1))
        print("type=airspace")
        print("description=" + "OpenAIP Airspace for " + countryname)
        print("area=" + key.group(1)[0:2])
        print("update=" + updatedate.group(1))
        print("")
