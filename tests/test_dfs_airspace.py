"""Tests for the DFS AIXM to OpenAir airspace converter."""

from pathlib import Path
import hashlib
import json
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "build"))

from dfs_airspace import (  # noqa: E402
    ConversionError,
    amdt_effective_by,
    Limit,
    convert,
    find_release,
    format_limit,
    format_point,
    metadata_json,
    parse,
    verify_checksum,
    write_openair,
)


def limits(upper, lower):
    def one(name, limit):
        value, uom, ref = limit
        return (f'<aixm:{name}Limit uom="{uom}">{value}</aixm:{name}Limit>'
                f"<aixm:{name}LimitReference>{ref}</aixm:{name}LimitReference>")
    return one("upper", upper) + one("lower", lower)


def drawn(segments, upper=(100, "FL", "STD"), lower=(0, "FT", "SFC")):
    return f"""
      <aixm:geometryComponent><aixm:AirspaceGeometryComponent>
        <aixm:theAirspaceVolume><aixm:AirspaceVolume>
          {limits(upper, lower)}
          <aixm:horizontalProjection><aixm:Surface><gml:patches><gml:PolygonPatch>
            <gml:exterior><gml:Ring><gml:curveMember><gml:Curve><gml:segments>
              {segments}
            </gml:segments></gml:Curve></gml:curveMember></gml:Ring></gml:exterior>
          </gml:PolygonPatch></gml:patches></aixm:Surface></aixm:horizontalProjection>
        </aixm:AirspaceVolume></aixm:theAirspaceVolume>
      </aixm:AirspaceGeometryComponent></aixm:geometryComponent>"""


def union(*uuids, operation="UNION"):
    components = ""
    for i, uuid in enumerate(uuids):
        op = "BASE" if i == 0 else operation
        components += f"""
      <aixm:geometryComponent><aixm:AirspaceGeometryComponent>
        <aixm:operation>{op}</aixm:operation>
        <aixm:theAirspaceVolume><aixm:AirspaceVolume><aixm:contributorAirspace>
          <aixm:AirspaceVolumeDependency>
            <aixm:dependency>FULL_GEOMETRY</aixm:dependency>
            <aixm:theAirspace xlink:href="urn:uuid:{uuid}"/>
          </aixm:AirspaceVolumeDependency>
        </aixm:contributorAirspace></aixm:AirspaceVolume></aixm:theAirspaceVolume>
      </aixm:AirspaceGeometryComponent></aixm:geometryComponent>"""
    return components


def note(purpose, text):
    return f"""<aixm:annotation><aixm:Note>
      <aixm:propertyName>activation</aixm:propertyName>
      <aixm:purpose>{purpose}</aixm:purpose>
      <aixm:translatedNote><aixm:LinguisticNote><aixm:note>{text}</aixm:note></aixm:LinguisticNote>
      </aixm:translatedNote></aixm:Note></aixm:annotation>"""


def remark(text):
    """A remark that is not about the activation, as DFS writes them."""
    return f"""<aixm:annotation><aixm:Note>
      <aixm:purpose>REMARK</aixm:purpose>
      <aixm:translatedNote><aixm:LinguisticNote><aixm:note>{text}</aixm:note></aixm:LinguisticNote>
      </aixm:translatedNote></aixm:Note></aixm:annotation>"""


def sheet(day, until="", start="", end="", start_event="", end_event="", dst="NO",
          excluded="NO", season=("", "")):
    return f"""<aixm:timeInterval><aixm:Timesheet>
      <aixm:timeReference>UTC</aixm:timeReference>
      <aixm:startDate>{season[0]}</aixm:startDate><aixm:endDate>{season[1]}</aixm:endDate>
      <aixm:day>{day}</aixm:day><aixm:dayTil>{until}</aixm:dayTil>
      <aixm:startTime>{start}</aixm:startTime><aixm:startEvent>{start_event}</aixm:startEvent>
      <aixm:endTime>{end}</aixm:endTime><aixm:endEvent>{end_event}</aixm:endEvent>
      <aixm:daylightSavingAdjust>{dst}</aixm:daylightSavingAdjust>
      <aixm:excluded>{excluded}</aixm:excluded>
    </aixm:Timesheet></aixm:timeInterval>"""


def activation(code, *sheets, remark=""):
    xml = note("DESCRIPTION", code)
    if remark:
        xml += note("REMARK", remark)
    if sheets:
        xml += ("<aixm:activation><aixm:AirspaceActivation><aixm:status>ACTIVE</aixm:status>"
                + "".join(sheets) + "</aixm:AirspaceActivation></aixm:activation>")
    return xml


def airspace(uuid, type_, designator, name, geometry, local_type="", classification="",
             active=""):
    layer = (f"<aixm:class><aixm:AirspaceLayerClass><aixm:classification>{classification}"
             "</aixm:classification></aixm:AirspaceLayerClass></aixm:class>"
             if classification else "")
    return f"""
  <message:hasMember><aixm:Airspace>
    <gml:identifier codeSpace="urn:uuid:">{uuid}</gml:identifier>
    <aixm:timeSlice><aixm:AirspaceTimeSlice>
      <aixm:type>{type_}</aixm:type>
      <aixm:designator>{designator}</aixm:designator>
      <aixm:localType>{local_type}</aixm:localType>
      <aixm:name>{name}</aixm:name>
      {layer}
      {active}
      {geometry}
    </aixm:AirspaceTimeSlice></aixm:timeSlice>
  </aixm:Airspace></message:hasMember>"""


def dataset(*members):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<message:AIXMBasicMessage xmlns:message="http://www.aixm.aero/schema/5.1.1/message"
    xmlns:aixm="http://www.aixm.aero/schema/5.1.1"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:xlink="http://www.w3.org/1999/xlink">
{"".join(members)}
</message:AIXMBasicMessage>""".encode()


SQUARE = """<gml:GeodesicString><gml:posList>
  50.0 8.0 50.0 9.0 49.0 9.0 49.0 8.0 50.0 8.0
</gml:posList></gml:GeodesicString>"""


def blocks_of(payload):
    missing = []
    blocks, _, _ = convert(parse(payload), missing)
    return blocks, missing


class GeometryTest(unittest.TestCase):
    def test_polygon_drops_the_closing_point(self):
        blocks, _ = blocks_of(dataset(airspace("a", "R", "EDR1", "GARCHING", drawn(SQUARE))))
        self.assertEqual(blocks[0][4], [
            "DP 50:00:00.0 N 008:00:00.0 E",
            "DP 50:00:00.0 N 009:00:00.0 E",
            "DP 49:00:00.0 N 009:00:00.0 E",
            "DP 49:00:00.0 N 008:00:00.0 E",
        ])

    def test_circle(self):
        circle = """<gml:CircleByCenterPoint numArc="1"><gml:pos>49.5 11.25</gml:pos>
          <gml:radius uom="[nmi_i]">1.4</gml:radius></gml:CircleByCenterPoint>"""
        blocks, _ = blocks_of(dataset(airspace("a", "CTR", "EDXX", "TEST", drawn(circle))))
        self.assertEqual(blocks[0][4], ["V X=49:30:00.0 N 011:15:00.0 E", "DC 1.4"])

    def arc_ring(self, start, end):
        # Centre 49N 10E, radius 6 nm: 0.1 degree of latitude north and south.
        return f"""
          <gml:GeodesicString><gml:posList>49.0 10.0 49.1 10.0</gml:posList></gml:GeodesicString>
          <gml:ArcByCenterPoint numArc="1"><gml:pos>49.0 10.0</gml:pos>
            <gml:radius uom="[nmi_i]">6</gml:radius>
            <gml:startAngle uom="deg">{start}</gml:startAngle>
            <gml:endAngle uom="deg">{end}</gml:endAngle>
          </gml:ArcByCenterPoint>
          <gml:GeodesicString><gml:posList>48.9 10.0 49.0 10.0</gml:posList></gml:GeodesicString>"""

    def test_increasing_bearing_is_clockwise(self):
        blocks, _ = blocks_of(dataset(airspace(
            "a", "R", "EDR1", "T", drawn(self.arc_ring(0, 180)))))
        geometry = blocks[0][4]
        self.assertIn("V D=+", geometry)
        self.assertIn("V X=49:00:00.0 N 010:00:00.0 E", geometry)
        # The arc starts and ends on the published points of its neighbours,
        # which are not repeated as DP.
        self.assertIn("DB 49:06:00.0 N 010:00:00.0 E, 48:54:00.0 N 010:00:00.0 E", geometry)
        self.assertEqual(geometry[0], "DP 49:00:00.0 N 010:00:00.0 E")
        self.assertEqual(len([line for line in geometry if line.startswith("DP")]), 1)

    def test_decreasing_and_negative_bearing_is_counterclockwise(self):
        # 0 to -180 sweeps west; "end > start" must use the signed angles.
        blocks, _ = blocks_of(dataset(airspace(
            "a", "R", "EDR1", "T", drawn(self.arc_ring(0, -180)))))
        self.assertIn("V D=-", blocks[0][4])

    def test_rounds_to_tenths_of_a_second_with_carry(self):
        self.assertEqual(format_point((47.99999999, -0.5)), "48:00:00.0 N 000:30:00.0 W")
        self.assertEqual(format_point((-33.123456, 151.2)), "33:07:24.4 S 151:12:00.0 E")


class LimitTest(unittest.TestCase):
    def test_limits(self):
        self.assertEqual(format_limit(Limit(100, "FL", "STD")), "FL100")
        self.assertEqual(format_limit(Limit(3500, "FT", "MSL")), "3500ft MSL")
        self.assertEqual(format_limit(Limit(0, "FT", "SFC")), "GND")
        self.assertEqual(format_limit(Limit(1000, "FT", "SFC")), "1000ft AGL")
        self.assertEqual(format_limit(Limit(300, "M", "MSL")), "984ft MSL")
        self.assertEqual(format_limit(Limit(None, "FL", "STD")), "UNL")

    def test_rejects_what_it_does_not_know(self):
        with self.assertRaises(ConversionError):
            format_limit(Limit(100, "FT", "W84"))
        with self.assertRaises(ConversionError):
            format_limit(None)


class SelectionTest(unittest.TestCase):
    def test_union_of_parts_is_written_under_the_composite(self):
        blocks, _ = blocks_of(dataset(
            airspace("p1", "PART", "EDLWTMZA", "EDLWTMZA", drawn(SQUARE)),
            airspace("p2", "PART", "EDLWTMZB", "EDLWTMZB", drawn(SQUARE, lower=(2500, "FT", "MSL"))),
            airspace("t", "RAS", "EDLWTMZ", "DORTMUND", union("p1", "p2"), local_type="TMZ"),
        ))
        self.assertEqual([(b[0], b[1], b[3]) for b in blocks],
                         [("TMZ", "TMZ DORTMUND", "GND"), ("TMZ", "TMZ DORTMUND", "2500ft MSL")])

    def test_parts_written_on_their_own_are_not_repeated(self):
        blocks, _ = blocks_of(dataset(
            airspace("a", "CLASS", "EDDHCLCA", "HAMBURG A", drawn(SQUARE), classification="C"),
            airspace("b", "CLASS", "EDDHCLCB", "HAMBURG B", drawn(SQUARE), classification="C"),
            airspace("h", "CLASS", "EDDHCLC", "HAMBURG", union("a", "b"), classification="C"),
        ))
        self.assertEqual([b[1] for b in blocks], ["HAMBURG A", "HAMBURG B"])

    def test_country_wide_class_c_and_class_e_are_left_out(self):
        blocks, _ = blocks_of(dataset(
            airspace("c", "CLASS", "EDCLC", "DEUTSCHLAND/GERMANY",
                     drawn(SQUARE, upper=(660, "FL", "STD"), lower=(100, "FL", "STD")),
                     classification="C"),
            airspace("e", "CLASS", "EDCLE", "E", drawn(SQUARE), classification="E"),
            airspace("s", "SECTOR", "EDWWFRI", "FRIESLAND", drawn(SQUARE)),
        ))
        self.assertEqual(blocks, [])

    def test_names_and_classes(self):
        blocks, _ = blocks_of(dataset(
            airspace("r", "OTHER:R_AMC", "EDR32A", "MUNSTER A", drawn(SQUARE)),
            airspace("d", "OTHER:D_AMC", "EDD19A", "TODENDORF-PUTLOS A", drawn(SQUARE)),
            airspace("g", "A", "EDDKGLD02", "KOELN NORD A", drawn(SQUARE), local_type="GLD"),
            airspace("k", "CTR", "EDDK", "KOELN/BONN", drawn(SQUARE), classification="D"),
        ))
        self.assertEqual([(b[0], b[1]) for b in blocks], [
            ("CTR", "CTR KOELN/BONN"),
            ("R", "ED-R32A MUNSTER A"),
            ("Q", "ED-D19A TODENDORF-PUTLOS A"),
            ("W", "KOELN NORD A"),
        ])

    def test_lanta_tra_and_vpa_are_left_out(self):
        blocks, _ = blocks_of(dataset(
            airspace("l", "OTHER:R_AMC", "EDR164", "LANTA STRAUBING", drawn(SQUARE)),
            airspace("t", "OTHER:R_AMC", "EDR201A", "TRA FRIESLAND 1 A", drawn(SQUARE)),
            airspace("v", "OTHER:R_AMC", "EDR4011D", "VPA NORTHEAST BASIC 1 D", drawn(SQUARE)),
            airspace("s", "R", "EDR4", "STRAUSBERG", drawn(SQUARE)),
        ))
        self.assertEqual([b[1] for b in blocks], ["ED-R4 STRAUSBERG"])

    def test_parachute_jumping_areas_and_atz_are_written_as_q(self):
        blocks, _ = blocks_of(dataset(
            airspace("p", "A", "EDADPJA", "DESSAU/SACHSEN-ANHALT", drawn(SQUARE),
                     local_type="PJA"),
            airspace("a", "RAS", "EDFEATZ", "EGELSBACH", drawn(SQUARE), local_type="ATZ"),
        ))
        self.assertEqual([(b[0], b[1]) for b in blocks],
                         [("Q", "ATZ EGELSBACH"), ("Q", "PARA DESSAU/SACHSEN-ANHALT")])

    def test_foreign_part_of_a_ctr_is_reported_not_fatal(self):
        blocks, missing = blocks_of(dataset(
            airspace("p1", "CTR_P", "EDSB1", "KARLSRUHE", drawn(SQUARE), classification="D"),
            airspace("c", "CTR", "EDSB", "KARLSRUHE", union("p1", "gone"), classification="D"),
        ))
        self.assertEqual([b[1] for b in blocks], ["CTR KARLSRUHE"])
        self.assertEqual(missing, ["EDSB: gone"])

    def test_airspace_with_every_part_abroad_is_reported_as_left_out(self):
        missing = []
        blocks, written, left_out = convert(parse(dataset(
            airspace("c", "CTR", "EDSB", "KARLSRUHE", union("gone1", "gone2"),
                     classification="D"),
        )), missing)
        self.assertEqual(blocks, [])
        self.assertEqual(sum(written.values()), 0)
        self.assertEqual(sum(left_out.values()), 1)
        self.assertEqual(missing[-1], "EDSB: no part left, airspace left out")

    def test_holes_and_several_patches_are_refused(self):
        hole = drawn(SQUARE).replace(
            "</gml:exterior>",
            f"</gml:exterior><gml:interior><gml:Ring><gml:curveMember><gml:Curve>"
            f"<gml:segments>{SQUARE}</gml:segments></gml:Curve></gml:curveMember>"
            f"</gml:Ring></gml:interior>")
        two = drawn(SQUARE).replace(
            "</gml:PolygonPatch>",
            f"</gml:PolygonPatch><gml:PolygonPatch><gml:exterior><gml:Ring>"
            f"<gml:curveMember><gml:Curve><gml:segments>{SQUARE}</gml:segments>"
            f"</gml:Curve></gml:curveMember></gml:Ring></gml:exterior></gml:PolygonPatch>",
            1)
        for geometry in (hole, two):
            with self.assertRaises(ConversionError):
                parse(dataset(airspace("a", "R", "EDR1", "T", geometry)))

    def test_subtraction_is_refused(self):
        payload = dataset(
            airspace("p1", "PART", "X1", "X1", drawn(SQUARE)),
            airspace("p2", "PART", "X2", "X2", drawn(SQUARE)),
            airspace("x", "R", "EDR9", "X", union("p1", "p2", operation="SUBTR")),
        )
        with self.assertRaises(ConversionError):
            parse(payload)


class ActivationTest(unittest.TestCase):
    def name(self, type_, active, designator="EDR32A", local_type=""):
        blocks, _ = blocks_of(dataset(airspace(
            "a", type_, designator, "MUNSTER A", drawn(SQUARE), local_type=local_type,
            active=active)))
        return blocks[0][1]

    def test_codes(self):
        self.assertEqual(self.name("R", activation("HX")), "ED-R32A MUNSTER A HX")
        self.assertEqual(self.name("R", activation("NOTAM")), "ED-R32A MUNSTER A NOTAM")
        self.assertEqual(self.name("R", activation("H24")), "ED-R32A MUNSTER A H24")

    def test_h24_is_only_said_for_restricted_and_danger_areas(self):
        self.assertEqual(self.name("RAS", activation("H24"), "EDLWTMZ", "TMZ"), "TMZ MUNSTER A")
        self.assertEqual(self.name("RAS", activation("HX"), "EDLWTMZ", "TMZ"),
                         "TMZ MUNSTER A HX")

    def test_weekdays_with_daylight_saving_time(self):
        active = activation(
            "TIMSH",
            *(sheet(day, start="07:00", end="22:30", dst="YES")
              for day in ("MON", "TUE", "WED", "THU")),
            sheet("FRI", start="07:00", end="16:00", dst="YES"),
            remark="Not during legal holidays")
        self.assertEqual(
            self.name("OTHER:R_AMC", active),
            "ED-R32A MUNSTER A MON-THU 0700(0600)-2230(2130), FRI 0700(0600)-1600(1500) EXC HOL")

    def test_day_range_sunrise_sunset_and_notam(self):
        active = activation(
            "TIMSH",
            sheet("FRI", "FRI", start="14:00", end_event="SS", dst="YES"),
            sheet("SAT", "SAT", start_event="SR", end_event="SS"),
            sheet("SUN", "SUN", start_event="SR", end_event="SS"),
            sheet("HOL", "HOL", start_event="SR", end_event="SS"),
            remark="Aktivierung per NOTAM./Activation by NOTAM.")
        self.assertEqual(self.name("A", active, "EDADPJA", "PJA"),
                         "PARA MUNSTER A FRI 1400(1300)-SS, SAT-SUN HOL SR-SS +NOTAM")

    def test_midnight_to_midnight_local_time_is_h24(self):
        active = activation("TIMSH", sheet("ANY", start="23:00", end="23:00", dst="YES"))
        self.assertEqual(self.name("R", active), "ED-R32A MUNSTER A H24")

    def test_upper_limit_raised_by_notam_is_noted(self):
        raised = remark("Hinweis/Note: Im Bedarfsfall wird die obere Begrenzung auf bis zu "
                        "14000 ft MSL angehoben./If required, the upper limit may be raised "
                        "up to 14000 ft MSL. This will be announced by NOTAM.")
        self.assertEqual(self.name("R", activation("HX") + raised),
                         "ED-R32A MUNSTER A HX / NOTAM up to 14000ft MSL")
        spaced = remark("If required, the upper limit may be raised to 40 000 ft MSL. "
                        "This will be announced by NOTAM.")
        self.assertEqual(self.name("R", spaced), "ED-R32A MUNSTER A NOTAM up to 40000ft MSL")
        flight_level = remark("After coordination the upper limit will be raised to FL 100.")
        self.assertEqual(self.name("R", flight_level), "ED-R32A MUNSTER A NOTAM up to FL100")

    def test_gliding_area_raised_with_a_restricted_area(self):
        boxberg = remark("upper limit ggf. 5500 MSL (bei Anhebung der Obergrenze der "
                         "ED-R 76 Sektor C auf 5500 ft MSL)")
        self.assertEqual(self.name("A", activation("HX") + boxberg, "EDABGLD01", "GLD"),
                         "MUNSTER A HX / up to 5500ft MSL with ED-R76C")

    def test_other_remarks_are_not_noted(self):
        self.assertEqual(self.name("R", activation("HX") + remark("Upper limit exclusively.")),
                         "ED-R32A MUNSTER A HX")

    def test_days_without_hours(self):
        self.assertEqual(self.name("R", activation("TIMSH", sheet("MON", "FRI"))),
                         "ED-R32A MUNSTER A MON-FRI")

    def test_day_range_over_the_weekend(self):
        self.assertEqual(self.name("R", activation("TIMSH", sheet("FRI", "MON", "07:00", "17:00"))),
                         "ED-R32A MUNSTER A FRI-MON 0700-1700")
        self.assertEqual(self.name("R", activation("TIMSH", sheet("SUN", "FRI", "06:00", "18:00"))),
                         "ED-R32A MUNSTER A SUN-FRI 0600-1800")

    def test_summer_and_winter(self):
        summer, winter = ("SDLST", "EDLST"), ("EDLST", "SDLST")
        active = activation(
            "TIMSH",
            sheet("SAT", start="07:00", end="18:30", season=summer),
            sheet("WORK_DAY", start="06:00", end="20:30", season=winter),
            sheet("SAT", start="08:00", end="17:00", season=winter),
            sheet("WORK_DAY", start="05:00", end="19:30", season=summer))
        self.assertEqual(self.name("CTR", active, "EDVE"),
                         "CTR MUNSTER A SUMMER: SAT 0700-1830, WORK_DAY 0500-1930"
                         " / WINTER: SAT 0800-1700, WORK_DAY 0600-2030")

    def test_dates_of_the_year_and_the_turn_of_the_year(self):
        active = activation(
            "TIMSH",
            sheet("ANY", start="09:00", end="19:00", season=("27-03", "29-10")),
            sheet("ANY", start="07:00", end="19:00", season=("30-10", "31-12")),
            sheet("ANY", start="07:00", end="19:00", season=("01-01", "26-03")))
        self.assertEqual(self.name("CTR", active, "EDHL"),
                         "CTR MUNSTER A 27MAR-29OCT: 0900-1900 / 30OCT-26MAR: 0700-1900")

    def test_whole_year_next_to_a_season_is_labelled(self):
        active = activation(
            "TIMSH",
            sheet("WED", start="16:00", end_event="SS", season=("01-04", "31-10")),
            sheet("FRI", start="14:00", end_event="SS"),
            sheet("SAT", start_event="SR", end_event="SS", season=("01-01", "31-12")))
        self.assertEqual(
            self.name("A", active, "EDXXPJA", "PJA"),
            "PARA MUNSTER A 01APR-31OCT: WED 1600-SS / ALL YEAR: FRI 1400-SS, SAT SR-SS")


class ReleaseTest(unittest.TestCase):
    PAYLOAD = b"<aixm/>"
    RELEASE = {
        "type": "AIXM 5.1",
        "publishedDate": "2026-10-01",
        "effectiveDate": "2026-10-29",
        "filename": "ED_Airspace_StrokedBorders_2026-10-01_2026-10-29_revision.xml",
        "checksum": {"type": "sha512", "value": hashlib.sha512(PAYLOAD).hexdigest()},
    }
    METADATA = {"Amdts": [
        {"Amdt": 0, "Metadata": {"datasets": [
            {"type": "group", "name": "aip", "items": [
                {"type": "leaf", "name": "ED Airspace ReferencedBorders",
                 "releases": [{"type": "AIXM 5.1", "filename": "wrong.xml"}]},
                {"type": "leaf", "name": "ED Airspace StrokedBorders", "releases": [RELEASE]},
            ]},
        ]}},
    ]}

    def test_finds_the_stroked_borders_release(self):
        self.assertEqual(find_release(self.METADATA, 0)["filename"], self.RELEASE["filename"])
        with self.assertRaises(ConversionError):
            find_release(self.METADATA, 1)

    def test_picks_the_cycle_in_effect_on_a_day(self):
        def amdt(number, effective):
            release = {"type": "AIXM 5.1", "effectiveDate": effective, "filename": "x.xml"}
            return {"Amdt": number, "Metadata": {"datasets": [
                {"type": "leaf", "name": "ED Airspace StrokedBorders", "releases": [release]},
            ]}}

        metadata = {"Amdts": [amdt(0, "2026-10-29"), amdt(1, "2026-11-26"),
                              amdt(2, "2026-12-24"), amdt(9999, "2026-11-02")]}
        # the Wednesday before a cycle asks for Thursday and gets the next one
        self.assertEqual(amdt_effective_by(metadata, "2026-11-26"), 1)
        # on any other Wednesday the current one stays
        self.assertEqual(amdt_effective_by(metadata, "2026-11-19"), 0)
        self.assertEqual(amdt_effective_by(metadata, "2026-11-05"), 0)
        with self.assertRaises(ConversionError):
            amdt_effective_by(metadata, "2026-10-28")

    def test_checksum(self):
        verify_checksum(self.PAYLOAD, self.RELEASE)
        with self.assertRaises(ConversionError):
            verify_checksum(self.PAYLOAD + b" ", self.RELEASE)

    def test_metadata_credits_the_licence(self):
        data = json.loads(metadata_json())
        self.assertIn("CC BY 4.0", data["description"])
        # repository.py dates content files by their last commit
        self.assertNotIn("update", data)

    def test_header_credits_dfs_and_the_licence(self):
        text = write_openair(self.RELEASE, [])
        self.assertIn("DFS Deutsche Flugsicherung GmbH", text)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", text)
        self.assertIn("effective 2026-10-29", text)
        self.assertIn("Changes:", text)


if __name__ == "__main__":
    unittest.main()
