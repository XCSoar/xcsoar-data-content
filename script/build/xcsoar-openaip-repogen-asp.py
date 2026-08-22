#!/usr/bin/env python3

from iso3166 import countries

from openaip_exports import iter_exports

for obj in iter_exports():
    if not obj.key.endswith("asp_v2.txt"):
        continue

    countrycode = obj.key[:2].upper()
    countryname = countries.get(countrycode).name
    print("name=" + countrycode + "-ASP-national" + "-OpenAIP.txt")
    print("uri=" + obj.url)
    print("type=airspace")
    print("description=" + "OpenAIP Airspace for " + countryname)
    print("area=" + obj.key[:2])
    print("update=" + obj.last_modified)
    print("")
