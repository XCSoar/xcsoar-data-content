#!/usr/bin/env python3
"""Convert the DFS airspace data set for Germany from AIXM 5.1.1 to OpenAir.

DFS Deutsche Flugsicherung GmbH publishes the German AIP data sets at
https://aip.dfs.de/datasets/, one release per AIRAC cycle.  The airspace data
DFS originates is licensed CC BY 4.0 (XCSoar/xcsoar-data-content#555), so the
converted file names DFS as the rights holder, links the licence and says what
was changed.

Two things make the download more than a fixed URL:

1. The file name carries the publication and effective dates
   (``ED_Airspace_StrokedBorders_2026-10-01_2026-10-29_revision.xml``), so it
   is read from the REST metadata right before each download.
2. The metadata publishes a SHA-512 per file; a download that does not match
   it is refused rather than converted.

The "StrokedBorders" variant is used because it writes national borders out
as coordinates; the "ReferencedBorders" one points at separate border
features instead.

Only the airspace a glider pilot plans around is written, in the classic
OpenAir classes the DAeC file uses: CTR, classes C and D, ED-R, ED-D, TMZ,
RMZ, ATZ, parachute jumping areas and gliding areas.  The rest of the data
set (ATC sectors, FIR, CTA/UTA, class E, aerobatic boxes, ...) is counted
and left out; run with --report to see what.  Of the ED-R, the night low
flying areas (LANTA), the temporary reserved areas (TRA) and the variable
profile areas (VPA) are left out.

When an airspace is active is appended to its name, as in the AIP and the
DAeC file: "H24", "HX", "NOTAM", or the days and times of its time sheets,
e.g. "MON-FRI 0700(0600)-1700(1600)".  Times are UTC; a time that moves with
daylight saving time is given for winter, with summer in brackets.  "SR" and
"SS" are sunrise and sunset, "EXC HOL" means not on public holidays, and
"+NOTAM" that the times can be extended or set by NOTAM.  Hours for part of
the year are labelled with the dates ("01APR-31OCT: ...") or with SUMMER and
WINTER for the time with and without daylight saving time.  "H24" is left out
except for ED-R and ED-D, where it says the area is never off.

An upper limit that can be raised by NOTAM, given in the DFS data only as a
remark, follows as text too ("NOTAM up to 14000ft MSL").  The airspace keeps
its published limits: XCSoar shows a raise that is in force as NOTAM
airspace, so a second, always active block would warn on every other day.

Geometry:

- An airspace is either drawn itself or the union of other airspaces ("BASE"
  plus "UNION" components, e.g. TMZ DORTMUND = EDLWTMZA + EDLWTMZB + ...).
  OpenAir has no union, so each contributing volume is written as its own
  block under the composite's class and name, with the contributor's limits.
- Arc angles are bearings in degrees (clockwise from true north), and the arc
  runs from startAngle to endAngle: endAngle > startAngle is clockwise.
  Angles may be negative or exceed 180 degrees of sweep, so the signed
  difference is used, never a normalised one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REST_URL = "https://aip.dfs.de/datasets/rest/"
DATASET_NAME = "ED Airspace StrokedBorders"

AIXM = "{http://www.aixm.aero/schema/5.1.1}"
GML = "{http://www.opengis.net/gml/3.2}"
XLINK = "{http://www.w3.org/1999/xlink}"

EARTH_RADIUS_NM = 3440.065
FEET_PER_METRE = 1 / 0.3048

# OpenAir class per (AIXM type, local type); None keeps any local type.
# Class E is left out like in the DAeC file: it covers most of the country
# above 2500 ft and is not something to avoid.
CLASS_BY_TYPE = {
    ("CTR", None): "CTR",
    ("CTR_P", None): "CTR",
    ("R", None): "R",
    ("OTHER:R_AMC", None): "R",
    ("OTHER:D_AMC", None): "Q",
    ("D_OTHER", None): "Q",
    ("RAS", "TMZ"): "TMZ",
    ("RAS", "RMZ"): "RMZ",
    # Classic OpenAir has no class for these; the DAeC file writes them as Q.
    ("RAS", "ATZ"): "Q",
    ("A", "PJA"): "Q",
    ("A", "GLD"): "W",
}
CLASS_BY_CLASSIFICATION = {"C": "C", "D": "D"}

# Night low flying areas, temporary reserved areas and variable profile
# areas are ED-R in the data set too, but only named as such.
LEFT_OUT_NAME = re.compile(r"\b(LANTA|TRA|VPA)\b")

# Output order: what a pilot must not enter first.
CLASS_ORDER = ["CTR", "C", "D", "R", "Q", "TMZ", "RMZ", "W"]

NAME_PREFIX = {"CTR": "CTR ", "TMZ": "TMZ ", "RMZ": "RMZ "}
NAME_PREFIX_BY_LOCAL_TYPE = {"ATZ": "ATZ ", "PJA": "PARA "}

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
HOLIDAYS_EXCLUDED = re.compile(
    r"not during (public|legal) holidays|not effective on legal holidays|EXC HOL",
    re.IGNORECASE)

# Remarks on an upper limit that can be raised, e.g. "If required, the upper
# limit may be raised up to 14000 ft MSL. This will be announced by NOTAM."
# and, for the gliding area Boxberg, "upper limit ggf. 5500 MSL (bei Anhebung
# der Obergrenze der ED-R 76 Sektor C auf 5500 ft MSL)".
RAISED_BY_NOTAM = re.compile(
    r"upper limit (?:may|will) be raised (?:up )?to (?:up to )?"
    r"(?:FL ?(\d+)|(\d[\d ]*\d) ?ft MSL)", re.IGNORECASE)
RAISED_WITH_AREA = re.compile(
    r"upper limit ggf\. (\d+) (?:ft )?MSL \(bei Anhebung der Obergrenze der "
    r"ED-R ?(\d+) Sektor ([A-Z])", re.IGNORECASE)


class ConversionError(Exception):
    """The data set does not look the way this converter expects."""


@dataclass
class Limit:
    value: float | None  # None for "UNL"
    uom: str
    reference: str


@dataclass
class Volume:
    upper: Limit | None = None
    lower: Limit | None = None
    # Either a list of ring segments, or the uuid of a contributor airspace.
    segments: list = field(default_factory=list)
    contributor: str | None = None


@dataclass
class Airspace:
    uuid: str
    type: str
    local_type: str
    designator: str
    name: str
    classification: str
    volumes: list[Volume]
    activation: str = ""
    raised_limit: str = ""


# --- metadata and download -------------------------------------------------


def find_release(metadata: dict, amdt: int = 0) -> dict:
    """Return the AIXM release of the airspace data set for one amendment.

    ``amdt`` 0 is the current AIRAC cycle, 1 the next one.
    """
    for entry in metadata.get("Amdts", []):
        if entry.get("Amdt") != amdt:
            continue
        for leaf in _leaves(entry.get("Metadata", {}).get("datasets", [])):
            if leaf.get("name") != DATASET_NAME:
                continue
            for release in leaf.get("releases", []):
                if release.get("type", "").startswith("AIXM"):
                    return release
    raise ConversionError(f"no '{DATASET_NAME}' release for amendment {amdt}")


def _leaves(items):
    for item in items:
        if item.get("type") == "leaf":
            yield item
        else:
            yield from _leaves(item.get("items", []))


def verify_checksum(payload: bytes, release: dict) -> None:
    checksum = release.get("checksum", {})
    if checksum.get("type") != "sha512":
        raise ConversionError(f"unexpected checksum type {checksum.get('type')!r}")
    actual = hashlib.sha512(payload).hexdigest()
    if actual != checksum.get("value", "").lower():
        raise ConversionError(
            f"{release['filename']}: SHA-512 {actual} does not match the published "
            f"{checksum.get('value')}"
        )


def amdt_effective_by(metadata: dict, day: str) -> int:
    """Return the amendment of the newest AIRAC cycle in effect on ``day``.

    ``day`` is an ISO date.  Run on the eve of a cycle with the next day,
    this picks that cycle (amendment 1) before it takes effect at 00:00
    UTC; on every other day it picks the current one.  The non-AIRAC
    snapshot (9999) is never picked.
    """
    effective = {}
    for entry in metadata.get("Amdts", []):
        amdt = entry.get("Amdt")
        if amdt == 9999:
            continue
        try:
            date = find_release(metadata, amdt)["effectiveDate"]
        except ConversionError:
            continue
        if date <= day:
            effective[amdt] = date
    if not effective:
        raise ConversionError(f"no '{DATASET_NAME}' release in effect on {day}")
    return max(effective, key=effective.get)


def download(amdt: int | None, effective_by: str | None) -> tuple[dict, bytes]:
    import requests

    def get(url: str, timeout: int):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as error:
            raise ConversionError(f"{url}: {error}") from error
        return response

    try:
        metadata = get(REST_URL, 60).json()
    except ValueError as error:
        raise ConversionError(f"{REST_URL}: no JSON metadata") from error
    if effective_by:
        amdt = amdt_effective_by(metadata, effective_by)
    release = find_release(metadata, amdt)
    payload = get(f"{REST_URL}{amdt}/{release['filename']}", 300).content
    verify_checksum(payload, release)
    return release, payload


# --- AIXM parsing ----------------------------------------------------------


def _text(element, path: str) -> str:
    found = element.find(path)
    return (found.text or "").strip() if found is not None and found.text else ""


def _limit(volume, name: str) -> Limit | None:
    element = volume.find(f"{AIXM}{name}Limit")
    if element is None or not (element.text or "").strip():
        return None
    text = element.text.strip()
    value = None if text.upper() == "UNL" else float(text)
    return Limit(value, element.get("uom", ""), _text(volume, f"{AIXM}{name}LimitReference"))


def _positions(segment) -> list[tuple[float, float]]:
    pos_list = segment.find(f"{GML}posList")
    if pos_list is not None:
        values = [float(v) for v in pos_list.text.split()]
        return list(zip(values[0::2], values[1::2]))
    return [tuple(float(v) for v in p.text.split()) for p in segment.findall(f"{GML}pos")]


def _radius_nm(segment) -> float:
    radius = segment.find(f"{GML}radius")
    uom = radius.get("uom")
    value = float(radius.text)
    if uom == "[nmi_i]":
        return value
    if uom == "KM":
        return value / 1.852
    if uom == "M":
        return value / 1852
    raise ConversionError(f"unknown radius unit {uom!r}")


def _segments(volume) -> list:
    # OpenAir has one outline per airspace: no holes, no second patch.
    if volume.find(f".//{GML}interior") is not None:
        raise ConversionError("surface with an interior ring")
    if len(list(volume.iter(f"{GML}PolygonPatch"))) > 1:
        raise ConversionError("surface with several polygon patches")
    segments = []
    for curve in volume.iter(f"{GML}segments"):
        for segment in curve:
            tag = segment.tag.removeprefix(GML)
            if tag in ("GeodesicString", "LineStringSegment"):
                segments.append(("points", _positions(segment)))
            elif tag == "ArcByCenterPoint":
                segments.append((
                    "arc",
                    _positions(segment)[0],
                    _radius_nm(segment),
                    float(segment.find(f"{GML}startAngle").text),
                    float(segment.find(f"{GML}endAngle").text),
                ))
            elif tag == "CircleByCenterPoint":
                segments.append(("circle", _positions(segment)[0], _radius_nm(segment)))
            else:
                raise ConversionError(f"unknown curve segment {tag}")
    return segments


def _sheet_time(sheet, which: str) -> str:
    event = _text(sheet, f"{AIXM}{which}Event")
    if event:
        offset = _text(sheet, f"{AIXM}{which}TimeRelativeEvent")
        minutes = round(float(offset)) if offset else 0
        return f"{event}{minutes:+d}" if minutes else event
    time = _text(sheet, f"{AIXM}{which}Time")
    if not time:
        return ""  # days without hours, e.g. ED-R34A "MON-FRI"
    hours, minutes = (int(v) for v in time.split(":"))
    text = f"{hours:02d}{minutes:02d}"
    if _text(sheet, f"{AIXM}daylightSavingAdjust") == "YES":
        summer = (hours * 60 + minutes - 60) % (24 * 60)
        text += f"({summer // 60:02d}{summer % 60:02d})"
    return text


def _sheet_days(sheet) -> list[str]:
    day = _text(sheet, f"{AIXM}day") or "ANY"
    until = _text(sheet, f"{AIXM}dayTil")
    if day in WEEKDAYS and until in WEEKDAYS:
        # a range may run over the weekend, e.g. FRI to MON
        first, last = WEEKDAYS.index(day), WEEKDAYS.index(until)
        return [WEEKDAYS[(first + i) % 7] for i in range((last - first) % 7 + 1)]
    return [day]


MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _sheet_season(sheet) -> tuple[str, str]:
    """Return the part of the year a time sheet is for, e.g. ("01-04", "31-10").

    The whole year gives ("", ""); SDLST and EDLST are the start and end of
    daylight saving time.
    """
    start = _text(sheet, f"{AIXM}startDate")
    end = _text(sheet, f"{AIXM}endDate")
    if (start, end) in (("", ""), ("01-01", "31-12")):
        return "", ""
    return start, end


def _format_season(season: tuple[str, str]) -> str:
    if season == ("", ""):
        return "ALL YEAR"
    if season == ("SDLST", "EDLST"):
        return "SUMMER"
    if season == ("EDLST", "SDLST"):
        return "WINTER"

    def date(text: str) -> str:
        day, month = text.split("-")
        return f"{day}{MONTHS[int(month) - 1]}"

    return f"{date(season[0])}-{date(season[1])}"


def _format_days(days: list[str]) -> str:
    """MON TUE WED FRI HOL -> MON-WED FRI HOL; ANY alone is every day."""
    weekdays = sorted({d for d in days if d in WEEKDAYS}, key=WEEKDAYS.index)
    runs: list[list[str]] = []
    for day in weekdays:
        if runs and WEEKDAYS.index(day) == WEEKDAYS.index(runs[-1][-1]) + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    # a run over the weekend: SUN and MON-FRI -> SUN-FRI
    if len(runs) > 1 and runs[0][0] == "MON" and runs[-1][-1] == "SUN":
        runs = [runs[-1] + runs[0]] + runs[1:-1]
    parts = [run[0] if len(run) == 1 else f"{run[0]}-{run[-1]}" for run in runs]
    parts += sorted({d for d in days if d not in WEEKDAYS and d != "ANY"})
    return " ".join(parts)


def format_timesheets(sheets) -> str:
    """Summarise AIXM time sheets like the AIP: "MON-FRI 0700(0600)-1700(1600)".

    Sheets for part of the year are grouped by season and labelled, e.g.
    "SUMMER: SAT-SUN HOL 0700-1830 / WINTER: SAT-SUN HOL 0800-1700".
    """
    seasons: dict[tuple[str, str], list] = {}
    for sheet in sheets:
        seasons.setdefault(_sheet_season(sheet), []).append(sheet)

    texts = {season: _format_sheets(group) for season, group in seasons.items()}
    # 30-10 to 31-12 and 01-01 to 26-03 with the same hours are one winter
    for season, text in list(texts.items()):
        if season in texts and season[1] == "31-12":
            for other, other_text in list(texts.items()):
                if other[0] == "01-01" and other_text == text and other != season:
                    del texts[season], texts[other]
                    texts[(season[0], other[1])] = text
                    break

    if list(texts) == [("", "")]:
        return texts[("", "")]

    def order(season):
        if season in (("SDLST", "EDLST"), ("EDLST", "SDLST")):
            return (0, season[0] != "SDLST")
        if season == ("", ""):
            return (2, 0)
        day, month = season[0].split("-")
        return (1, int(month) * 100 + int(day))

    return " / ".join(f"{_format_season(season)}: {texts[season]}"
                      for season in sorted(texts, key=order))


def _format_sheets(sheets) -> str:
    spans: dict[tuple[str, bool], list[str]] = {}
    for sheet in sheets:
        start, end = _sheet_time(sheet, "start"), _sheet_time(sheet, "end")
        # Midnight to midnight local time, e.g. ED-R136B 2300(2200)-2300(2200).
        if start and (start == end or (start == "0000" and end in ("2400", "2359"))):
            span = "H24"
        elif start or end:
            span = f"{start}-{end}"
        else:
            span = ""
        excluded = _text(sheet, f"{AIXM}excluded") == "YES"
        spans.setdefault((span, excluded), []).extend(_sheet_days(sheet))

    def first_day(item):
        days = item[1]
        return min((WEEKDAYS.index(d) for d in days if d in WEEKDAYS), default=len(WEEKDAYS))

    parts = []
    for (span, excluded), days in sorted(spans.items(), key=lambda i: (i[0][1], first_day(i))):
        text = " ".join(filter(None, [_format_days(days), span]))
        parts.append(f"EXC {text}" if excluded else text)
    return ", ".join(parts)


def activation_text(slice_) -> str:
    """Return when an airspace is active, e.g. "HX" or "MON-FRI 0700(0600)-1700(1600)"."""
    code, remarks = "", []
    for note in slice_.findall(f"{AIXM}annotation/{AIXM}Note"):
        if _text(note, f"{AIXM}propertyName") != "activation":
            continue
        texts = [(t.text or "").strip() for t in note.iter(f"{AIXM}note")]
        if _text(note, f"{AIXM}purpose") == "DESCRIPTION":
            code = code or (texts[0] if texts else "")
        else:
            remarks += texts
    for activation in slice_.findall(f"{AIXM}activation/{AIXM}AirspaceActivation"):
        remarks += [(t.text or "").strip() for t in activation.iter(f"{AIXM}note")]

    if code in ("H24", "HX", "NOTAM"):
        text = code
    else:
        text = format_timesheets(slice_.iterfind(
            f"{AIXM}activation/{AIXM}AirspaceActivation/{AIXM}timeInterval/{AIXM}Timesheet"))
    if text and any(HOLIDAYS_EXCLUDED.search(r) for r in remarks):
        text += " EXC HOL"
    if text and code != "NOTAM" and any("NOTAM" in r for r in remarks):
        text += " +NOTAM"
    return text


def raised_limit_text(slice_) -> str:
    """Return how far a NOTAM can raise the upper limit, e.g. "NOTAM up to 14000ft MSL"."""
    for note in slice_.findall(f"{AIXM}annotation/{AIXM}Note"):
        if _text(note, f"{AIXM}propertyName") == "activation":
            continue
        for linguistic in note.iter(f"{AIXM}note"):
            text = " ".join((linguistic.text or "").split())
            if match := RAISED_BY_NOTAM.search(text):
                flight_level, feet = match.groups()
                return (f"NOTAM up to FL{flight_level}" if flight_level else
                        f"NOTAM up to {feet.replace(' ', '')}ft MSL")
            if match := RAISED_WITH_AREA.search(text):
                feet, number, sector = match.groups()
                return f"up to {feet}ft MSL with ED-R{number}{sector}"
    return ""


def parse(payload: bytes) -> dict[str, Airspace]:
    """Return every airspace of the data set, keyed by its uuid."""
    airspaces = {}
    for feature in ET.fromstring(payload).iter(f"{AIXM}Airspace"):
        uuid = _text(feature, f"{GML}identifier")
        slice_ = feature.find(f".//{AIXM}AirspaceTimeSlice")
        volumes = []
        for volume in slice_.iter(f"{AIXM}AirspaceVolume"):
            if volume.find(f"{AIXM}horizontalProjection") is not None:
                volumes.append(Volume(_limit(volume, "upper"), _limit(volume, "lower"),
                                      _segments(volume)))
                continue
            link = volume.find(f".//{AIXM}theAirspace")
            if link is None:
                raise ConversionError(f"{uuid}: volume without geometry or contributor")
            href = link.get(f"{XLINK}href", "")
            volumes.append(Volume(contributor=href.removeprefix("urn:uuid:")))
        for operation in slice_.iter(f"{AIXM}operation"):
            if operation.text not in ("BASE", "UNION"):
                # SUBTR or INTERS would need polygon clipping.
                raise ConversionError(f"{uuid}: unsupported operation {operation.text}")
        airspaces[uuid] = Airspace(
            uuid=uuid,
            type=_text(slice_, f"{AIXM}type"),
            local_type=_text(slice_, f"{AIXM}localType"),
            designator=_text(slice_, f"{AIXM}designator"),
            name=_text(slice_, f"{AIXM}name"),
            classification=_text(slice_, f".//{AIXM}AirspaceLayerClass/{AIXM}classification"),
            volumes=volumes,
            activation=activation_text(slice_),
            raised_limit=raised_limit_text(slice_),
        )
    return airspaces


def drawn_volumes(airspace: Airspace, airspaces: dict[str, Airspace],
                  missing: list[str], written: frozenset = frozenset(),
                  seen: frozenset = frozenset()) -> list[Volume]:
    """Return the volumes with geometry that make up an airspace.

    Contributors in ``written`` are skipped, because they are written on
    their own: HAMBURG is the union of HAMBURG A to K, which are class C
    airspaces themselves.

    A contributor outside the data set is appended to ``missing`` and left
    out: the parts of a German CTR that lie in a neighbouring country (e.g.
    EDSB2, "KARLSRUHE BADEN PARTIE FRANCAISE") are referenced but not
    published by DFS.
    """
    if airspace.uuid in seen:
        raise ConversionError(f"{airspace.designator}: contributor cycle")
    result = []
    for volume in airspace.volumes:
        if volume.contributor is None:
            result.append(volume)
            continue
        if volume.contributor in written:
            continue
        contributor = airspaces.get(volume.contributor)
        if contributor is None:
            missing.append(f"{airspace.designator}: {volume.contributor}")
            continue
        result += drawn_volumes(contributor, airspaces, missing, written,
                                seen | {airspace.uuid})
    return result


# --- OpenAir output --------------------------------------------------------


def openair_class(airspace: Airspace, airspaces: dict[str, Airspace]) -> str | None:
    """Return the OpenAir class to write an airspace as, or None to leave it out."""
    if airspace.type != "CLASS":
        if LEFT_OUT_NAME.search(airspace.name):
            return None
        return (CLASS_BY_TYPE.get((airspace.type, airspace.local_type))
                or CLASS_BY_TYPE.get((airspace.type, None)))
    cls = CLASS_BY_CLASSIFICATION.get(airspace.classification)
    # Class C covers the whole country from FL100 (FL130 over the Alps).
    # Like the DAeC file, only the class C and D around airports is written.
    volumes = drawn_volumes(airspace, airspaces, [])
    if volumes and all(v.lower and v.lower.uom == "FL" and v.lower.value >= 100
                       for v in volumes):
        return None
    return cls


def openair_name(airspace: Airspace, cls: str) -> str:
    # EDR32A -> ED-R32A, EDD19A -> ED-D19A, like the AIP and the DAeC file.
    match = re.fullmatch(r"ED([RD])(\d.*)", airspace.designator)
    if match:
        name = f"ED-{match[1]}{match[2]} {airspace.name}"
    else:
        prefix = (NAME_PREFIX_BY_LOCAL_TYPE.get(airspace.local_type)
                  or NAME_PREFIX.get(cls, ""))
        name = prefix + airspace.name
    activation = airspace.activation
    if activation == "H24" and cls not in ("R", "Q"):
        activation = ""
    if airspace.raised_limit:
        # " / ", not ";": some OpenAir readers take ";" for a comment
        activation = (f"{activation} / {airspace.raised_limit}" if activation
                      else airspace.raised_limit)
    return f"{name} {activation}" if activation else name


def format_limit(limit: Limit | None) -> str:
    if limit is None:
        raise ConversionError("volume without vertical limit")
    if limit.value is None:
        return "UNL"
    if limit.uom == "FL":
        return f"FL{limit.value:.0f}"
    feet = limit.value * FEET_PER_METRE if limit.uom == "M" else limit.value
    if limit.uom not in ("FT", "M"):
        raise ConversionError(f"unknown limit unit {limit.uom!r}")
    if limit.reference == "SFC":
        return "GND" if feet == 0 else f"{feet:.0f}ft AGL"
    if limit.reference == "MSL":
        return f"{feet:.0f}ft MSL"
    raise ConversionError(f"unknown limit reference {limit.reference!r}")


def format_point(point: tuple[float, float]) -> str:
    lat, lon = point

    # Tenths of a second (about 3 m): whole seconds (about 30 m) fold some
    # border-following rings onto themselves, e.g. ED-R117 at the Belgian
    # border.  aerofiles and XCSoar both read decimal seconds.
    def dms(value: float, width: int, hemispheres: str) -> str:
        hemisphere = hemispheres[0] if value >= 0 else hemispheres[1]
        tenths = round(abs(value) * 36000)
        return (f"{tenths // 36000:0{width}d}:{tenths // 600 % 60:02d}:"
                f"{tenths % 600 // 10:02d}.{tenths % 10} {hemisphere}")

    return f"{dms(lat, 2, 'NS')} {dms(lon, 3, 'EW')}"


def destination(center: tuple[float, float], bearing: float, distance_nm: float):
    lat1, lon1 = math.radians(center[0]), math.radians(center[1])
    theta, delta = math.radians(bearing), distance_nm / EARTH_RADIUS_NM
    lat2 = math.asin(math.sin(lat1) * math.cos(delta)
                     + math.cos(lat1) * math.sin(delta) * math.cos(theta))
    lon2 = lon1 + math.atan2(math.sin(theta) * math.sin(delta) * math.cos(lat1),
                             math.cos(delta) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def _near(a: tuple[float, float], b: tuple[float, float], limit_nm: float = 0.1) -> bool:
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1]) * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlon) * EARTH_RADIUS_NM < limit_nm


def geometry_lines(segments: list) -> list[str]:
    if len(segments) == 1 and segments[0][0] == "circle":
        _, center, radius = segments[0]
        return [f"V X={format_point(center)}", f"DC {radius:g}"]

    lines: list[str] = []
    last = None  # the last point written
    skip_next = None  # the published point an arc already ended on

    def point(p: tuple[float, float]) -> None:
        nonlocal last
        if last is None or format_point(p) != format_point(last):
            lines.append(f"DP {format_point(p)}")
            last = p

    for i, segment in enumerate(segments):
        if segment[0] == "points":
            for p in segment[1]:
                if skip_next is not None:
                    p_skip, skip_next = skip_next, None
                    if p == p_skip:
                        continue
                point(p)
        elif segment[0] == "arc":
            _, center, radius, start, end = segment
            # The neighbouring strings carry the published end points of the
            # arc; computing them again from the angles lands up to 30 m off.
            start_point = destination(center, start, radius)
            if last is not None and _near(last, start_point):
                start_point = last
                if lines[-1].startswith("DP "):
                    lines.pop()  # DB draws its own start point
            end_point = destination(center, end, radius)
            following = segments[i + 1] if i + 1 < len(segments) else segments[0]
            if following[0] == "points" and _near(following[1][0], end_point):
                end_point = following[1][0]
            lines.append(f"V D={'+' if end > start else '-'}")
            lines.append(f"V X={format_point(center)}")
            lines.append(f"DB {format_point(start_point)}, {format_point(end_point)}")
            last = skip_next = end_point
        else:
            raise ConversionError("circle inside a ring")

    # OpenAir closes the polygon itself.
    if len(lines) > 1 and lines[-1] == lines[0]:
        lines.pop()
    return lines


def convert(airspaces: dict[str, Airspace],
            missing: list[str]) -> tuple[list[tuple], Counter, Counter]:
    """Return (blocks, written per type, left out per type).

    A block is (class, name, upper, lower, geometry lines, designator).
    Contributors that are not in the data set are appended to ``missing``.
    """
    blocks, written, left_out = [], Counter(), Counter()
    classes = {uuid: openair_class(airspace, airspaces)
               for uuid, airspace in airspaces.items()}
    selected = frozenset(uuid for uuid, cls in classes.items() if cls)
    for airspace in airspaces.values():
        key = (airspace.type, airspace.local_type or airspace.classification)
        cls = classes[airspace.uuid]
        if cls is None:
            left_out[key] += 1
            continue
        volumes = drawn_volumes(airspace, airspaces, missing, selected)
        if not volumes and not drawn_volumes(airspace, airspaces, []):
            # every part lies outside the data set (parts written on their
            # own still count): say so, do not count it as written
            missing.append(f"{airspace.designator}: no part left, airspace left out")
            left_out[key] += 1
            continue
        written[key] += 1
        name = openair_name(airspace, cls)
        for volume in volumes:
            blocks.append((cls, name, format_limit(volume.upper),
                           format_limit(volume.lower), geometry_lines(volume.segments),
                           airspace.designator))
    blocks.sort(key=lambda b: (CLASS_ORDER.index(b[0]), b[1], b[5]))
    return blocks, written, left_out


def header(release: dict) -> list[str]:
    return [
        "* Airspace Germany",
        "*",
        "* Source: DFS Deutsche Flugsicherung GmbH, https://aip.dfs.de/datasets/",
        f"* Data set: {DATASET_NAME} (AIXM 5.1.1), effective {release['effectiveDate']},",
        f"*   published {release['publishedDate']}, {release['filename']}",
        "* Licence: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/",
        "*   (c) DFS Deutsche Flugsicherung GmbH",
        "*",
        "* Changes: converted to OpenAir by script/build/dfs_airspace.py in",
        "*   https://github.com/XCSoar/xcsoar-data-content; only CTR, classes C",
        "*   and D, ED-R (without LANTA, TRA and VPA), ED-D, TMZ, RMZ, ATZ,",
        "*   parachute jumping areas and gliding areas are included;",
        "*   coordinates rounded to a tenth of a second.",
        "* Gliding sectors: only those in the DFS data set (type GLD), which",
        "*   does not hold all sectors the Federal Ministry of Transport sets",
        "*   out in the NfL; use the DAeC file for the others.  Local sectors",
        "*   agreed between ATC and a single user are not published.",
        "*",
        "* Activation times follow the name, in UTC; a time that moves with",
        "* daylight saving time is given for winter, with summer in brackets,",
        "* e.g. MON-FRI 0700(0600)-1700(1600).  SR/SS = sunrise/sunset,",
        "* HX = no fixed hours, NOTAM = active by NOTAM only, +NOTAM = times can",
        "* be extended by NOTAM, EXC HOL = not on public holidays.  Hours for",
        "* part of the year carry the dates (01APR-31OCT:) or SUMMER: and WINTER:",
        "* for the time with and without daylight saving time.  Always check",
        "* the AIP and NOTAM.",
        "*",
        "* Upper limits raised by NOTAM are noted in the name (\"NOTAM up to",
        "* 14000ft MSL\"); use XCSoar's NOTAM airspace for the current state.",
        "",
    ]


def write_openair(release: dict, blocks: list[tuple]) -> str:
    lines = header(release)
    for cls, name, upper, lower, geometry, _ in blocks:
        lines += [f"AC {cls}", f"AN {name}", f"AH {upper}", f"AL {lower}", *geometry, ""]
    return "\n".join(lines)


def metadata_json() -> str:
    """Return the repository metadata beside the OpenAir file.

    No "update": for files under data/content/ repository.py takes the date
    of the last commit, and ignores the field.
    """
    return json.dumps({
        "description": ("Airspace Germany from DFS, with the gliding sectors of the "
                        "DFS data set only (CC BY 4.0, DFS Deutsche Flugsicherung "
                        "GmbH)"),
    }, indent=2) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, help="OpenAir file to write")
    parser.add_argument("--amdt", type=int, default=0,
                        help="amendment: 0 = current AIRAC cycle (default), 1 = next")
    parser.add_argument("--effective-by", metavar="YYYY-MM-DD",
                        help="instead of --amdt, the newest cycle in effect on that day")
    parser.add_argument("--input", type=Path,
                        help="use a downloaded AIXM file instead of downloading")
    parser.add_argument("--metadata", type=Path,
                        help="REST metadata JSON for --input (checks its SHA-512)")
    parser.add_argument("--report", action="store_true",
                        help="list the airspace types written and left out")
    parser.add_argument("--json", action="store_true",
                        help="also write the repository metadata (OUTPUT with .json)")
    args = parser.parse_args(argv)

    try:
        if args.input:
            payload = args.input.read_bytes()
            if not args.metadata:
                parser.error("--input needs --metadata")
            metadata = json.loads(args.metadata.read_text())
            amdt = (amdt_effective_by(metadata, args.effective_by)
                    if args.effective_by else args.amdt)
            release = find_release(metadata, amdt)
            verify_checksum(payload, release)
        else:
            release, payload = download(args.amdt, args.effective_by)
        missing: list[str] = []
        blocks, written, left_out = convert(parse(payload), missing)
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    args.output.write_text(write_openair(release, blocks), encoding="utf-8")
    if args.json:
        args.output.with_suffix(".json").write_text(metadata_json(), encoding="utf-8")
    print(f"{args.output}: {len(blocks)} blocks from {sum(written.values())} airspaces, "
          f"{sum(left_out.values())} left out", file=sys.stderr)
    for reference in missing:
        print(f"warning: contributor not in the data set, left out: {reference}",
              file=sys.stderr)
    if args.report:
        for title, counter in (("written", written), ("left out", left_out)):
            print(f"{title}:", file=sys.stderr)
            for (type_, local), count in sorted(counter.items(), key=lambda kv: -kv[1]):
                print(f"  {count:4d} {type_} {local}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
