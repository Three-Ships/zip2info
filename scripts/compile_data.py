"""
Compile packaged lookup data for zip2info.

Timezones are *derived* from each ZIP centroid via ``timezonefinder`` rather
than copied from the previous build. That matters: the old script re-read its
own output as the timezone source, so the shipped ZIP set could never gain a
code and silently shrank whenever a coordinate went missing. Deriving from the
source geography makes the table a function of the upstream feeds instead.

Coordinate sources, in increasing priority:
  1. U.S. Census ZCTA gazetteer centroids (public domain)
  2. GeoNames postal data for the US and its territories (CC BY 4.0)
  3. Manual overrides in data/coordinate_overrides.json

The previously generated module is consulted only for ZIPs the upstream feeds
have since retired, so established codes are never dropped.

Usage:
    python scripts/compile_data.py
"""

from __future__ import annotations

import ast
import collections
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timezonefinder import TimezoneFinder

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src" / "zip2info"
OUTPUT = SRC_DIR / "_data.py"
OVERRIDES_PATH = ROOT / "data" / "coordinate_overrides.json"

# The US file omits the territories; GeoNames ships each separately.
GEONAMES_COUNTRIES = ("US", "PR", "VI", "GU", "AS", "MP")
GEONAMES_ZIP_URL = "https://download.geonames.org/export/zip/{country}.zip"
CENSUS_ZCTA_GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/Gaz_zcta_national.zip"
)

Coordinate = tuple[float, float]

# Only these zones may ship. A ZIP centroid can legitimately land on foreign
# soil -- APO/FPO/DPO codes carry the coordinates of the overseas base, and a
# handful of border ZIPs have centroids just across the line -- which yields
# zones like Europe/Berlin, America/Toronto or America/Sao_Paulo. The
# "America/" prefix is a continent, not a country, so it cannot be used as the
# filter. ZIPs resolving outside this set are omitted, leaving callers to apply
# their own fallback rather than acting on a foreign local time.
US_TIMEZONES = frozenset(
    {
        "America/Adak",
        "America/Anchorage",
        "America/Boise",
        "America/Chicago",
        "America/Denver",
        "America/Detroit",
        "America/Indiana/Indianapolis",
        "America/Indiana/Knox",
        "America/Indiana/Marengo",
        "America/Indiana/Petersburg",
        "America/Indiana/Tell_City",
        "America/Indiana/Vevay",
        "America/Indiana/Vincennes",
        "America/Indiana/Winamac",
        "America/Juneau",
        "America/Kentucky/Louisville",
        "America/Kentucky/Monticello",
        "America/Los_Angeles",
        "America/Menominee",
        "America/Metlakatla",
        "America/New_York",
        "America/Nome",
        "America/North_Dakota/Beulah",
        "America/North_Dakota/Center",
        "America/North_Dakota/New_Salem",
        "America/Phoenix",
        "America/Puerto_Rico",
        "America/Sitka",
        "America/St_Thomas",
        "America/Yakutat",
        "Pacific/Guam",
        "Pacific/Honolulu",
        "Pacific/Midway",
        "Pacific/Pago_Pago",
        "Pacific/Saipan",
        "Pacific/Wake",
    }
)

# Spot checks that must survive any regeneration. These pin the timezone
# boundaries that are easy to get wrong -- Arizona's no-DST carve-out, the
# Indiana and Kentucky county splits, and the Alaska zones.
EXPECTED_TIMEZONES = {
    "00501": "America/New_York",
    "00926": "America/Puerto_Rico",
    "01001": "America/New_York",
    "10001": "America/New_York",
    "46201": "America/Indiana/Indianapolis",
    "46401": "America/Chicago",
    "47591": "America/Indiana/Vincennes",
    "58102": "America/Chicago",
    "60601": "America/Chicago",
    "78074": "America/Chicago",
    "85001": "America/Phoenix",
    "85701": "America/Phoenix",
    "86515": "America/Denver",
    "90210": "America/Los_Angeles",
    "96801": "Pacific/Honolulu",
    "99501": "America/Anchorage",
    "99546": "America/Adak",
}


def _zip_to_geoid(zip_code: int | str) -> str:
    return str(zip_code).zfill(5)


def _fetch(url: str) -> bytes:
    print(f"Downloading {url}...")
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read()


def _read_single_text_member(payload: bytes, *, skip_readme: bool) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".txt")]
        if skip_readme:
            names = [n for n in names if not n.lower().startswith("readme")]
        if not names:
            raise ValueError("archive did not contain a data .txt file")
        return archive.read(names[0]).decode("utf-8")


def _download_geonames_coordinates() -> dict[str, Coordinate]:
    """ZIP centroids for the US and its territories, best accuracy per code."""
    coordinates: dict[str, Coordinate] = {}
    accuracy_rank: dict[str, int] = {}

    for country in GEONAMES_COUNTRIES:
        raw = _read_single_text_member(
            _fetch(GEONAMES_ZIP_URL.format(country=country)), skip_readme=True
        )
        found = 0
        for line in raw.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            postal_code = parts[1].strip()
            if len(postal_code) != 5 or not postal_code.isdigit():
                continue
            accuracy = int(parts[11]) if parts[11].strip().isdigit() else 1
            if accuracy < accuracy_rank.get(postal_code, -1):
                continue
            coordinates[postal_code] = (float(parts[9]), float(parts[10]))
            accuracy_rank[postal_code] = accuracy
            found += 1
        print(f"  {country}: {found} postal records")

    print(f"Loaded {len(coordinates)} GeoNames coordinate records")
    return coordinates


def _download_census_zcta_coordinates() -> dict[str, Coordinate]:
    raw = _read_single_text_member(
        _fetch(CENSUS_ZCTA_GAZETTEER_URL), skip_readme=False
    )

    coordinates: dict[str, Coordinate] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if parts[0] == "GEOID":
            continue
        geoid = parts[0].strip()
        if len(geoid) != 5 or not geoid.isdigit():
            continue
        # Gazetteer layout: GEOID, POP10, HU10, ALAND, AWATER, ALAND_SQMI,
        # AWATER_SQMI, INTPTLAT, INTPTLONG
        coordinates[geoid] = (float(parts[7]), float(parts[8]))

    print(f"Loaded {len(coordinates)} Census ZCTA coordinate records")
    return coordinates


def _load_manual_overrides() -> dict[str, Coordinate]:
    if not OVERRIDES_PATH.exists():
        return {}
    raw = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    overrides = {
        _zip_to_geoid(geoid): (float(lat), float(lon))
        for geoid, (lat, lon) in raw.items()
    }
    print(f"Loaded {len(overrides)} manual coordinate overrides")
    return overrides


def _load_previous_dataset() -> dict[str, tuple[str, float, float]]:
    """Previous build keyed by ZIP -> (timezone *name*, lat, lon).

    Resolved by name, never by index: a stale index is exactly how ZIP 00926
    shipped pointing past the end of TIMEZONES.
    """
    if not OUTPUT.exists():
        return {}

    module = ast.parse(OUTPUT.read_text(encoding="utf-8"))
    timezones: tuple[str, ...] | None = None
    zip_info: dict[int, tuple[int, float, float]] | None = None

    for node in module.body:
        targets = (
            [t.id for t in node.targets if isinstance(t, ast.Name)]
            if isinstance(node, ast.Assign)
            else [node.target.id]
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            else []
        )
        value = node.value
        if value is None:
            continue
        for name in targets:
            if name == "TIMEZONES":
                timezones = ast.literal_eval(value)
            elif name == "ZIP_INFO":
                zip_info = ast.literal_eval(value)

    if not timezones or not zip_info:
        return {}

    previous: dict[str, tuple[str, float, float]] = {}
    skipped = 0
    for zip_code, (tz_idx, latitude, longitude) in zip_info.items():
        if not 0 <= tz_idx < len(timezones):
            skipped += 1
            continue
        previous[_zip_to_geoid(zip_code)] = (timezones[tz_idx], latitude, longitude)

    if skipped:
        print(f"Ignored {skipped} previous records with out-of-range timezone indices")
    print(f"Loaded {len(previous)} records from the previous dataset")
    return previous


def _merge_coordinates(*sources: dict[str, Coordinate]) -> dict[str, Coordinate]:
    """Later sources win."""
    merged: dict[str, Coordinate] = {}
    for source in sources:
        merged.update(source)
    return merged


def _build_zip_info(
    coordinates: dict[str, Coordinate],
    previous: dict[str, tuple[str, float, float]],
) -> tuple[tuple[str, ...], dict[int, tuple[int, float, float]]]:
    finder = TimezoneFinder()

    resolved: dict[str, tuple[str, float, float]] = {}
    unresolved = 0
    foreign: collections.Counter[str] = collections.Counter()
    for geoid, (latitude, longitude) in coordinates.items():
        timezone_name = finder.timezone_at(lat=latitude, lng=longitude)
        if timezone_name is None:
            unresolved += 1
            continue
        if timezone_name not in US_TIMEZONES:
            foreign[timezone_name] += 1
            continue
        resolved[geoid] = (timezone_name, latitude, longitude)

    if unresolved:
        print(f"Skipped {unresolved} ZIP codes whose centroid has no timezone")
    if foreign:
        top = ", ".join(f"{name} ({count})" for name, count in foreign.most_common(5))
        print(
            f"Skipped {sum(foreign.values())} ZIP codes resolving outside the US "
            f"across {len(foreign)} zones: {top}, ..."
        )

    # Retired codes: keep whatever the last build knew rather than losing them.
    carried = 0
    for geoid, record in previous.items():
        if geoid not in resolved and record[0] in US_TIMEZONES:
            resolved[geoid] = record
            carried += 1
    if carried:
        print(f"Carried {carried} retired ZIP codes forward from the previous dataset")

    timezones = tuple(sorted({name for name, _, _ in resolved.values()}))
    index_of = {name: index for index, name in enumerate(timezones)}
    zip_info = {
        int(geoid): (index_of[name], latitude, longitude)
        for geoid, (name, latitude, longitude) in sorted(resolved.items())
    }
    return timezones, zip_info


def _validate(
    timezones: tuple[str, ...],
    zip_info: dict[int, tuple[int, float, float]],
    previous: dict[str, tuple[str, float, float]],
) -> None:
    """Fail the build rather than shipping a broken table."""
    errors: list[str] = []

    for zip_code, (tz_idx, _, _) in zip_info.items():
        if not 0 <= tz_idx < len(timezones):
            errors.append(
                f"ZIP {_zip_to_geoid(zip_code)} has timezone index {tz_idx}, "
                f"but TIMEZONES has {len(timezones)} entries"
            )

    for name in timezones:
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"{name!r} is not a valid IANA timezone")

    if len(zip_info) < len(previous):
        errors.append(
            f"ZIP coverage regressed: {len(zip_info)} < {len(previous)} previously"
        )

    for geoid, expected in EXPECTED_TIMEZONES.items():
        record = zip_info.get(int(geoid))
        if record is None:
            errors.append(f"ZIP {geoid} is missing; expected {expected}")
        elif (actual := timezones[record[0]]) != expected:
            errors.append(f"ZIP {geoid} resolved to {actual}, expected {expected}")

    if errors:
        raise SystemExit(
            "Refusing to write data module:\n"
            + "\n".join(f"  - {error}" for error in errors)
        )


def _format_tuple_lines(values: tuple[str, ...], indent: str = "    ") -> str:
    return "\n".join(f"{indent}{value!r}," for value in values)


def _format_zip_info_entries(
    zip_info: dict[int, tuple[int, float, float]],
    indent: str = "    ",
) -> str:
    return "\n".join(
        f"{indent}{zip_code}: ({tz_idx}, {latitude}, {longitude}),"
        for zip_code, (tz_idx, latitude, longitude) in sorted(zip_info.items())
    )


def _write_data_module(
    timezones: tuple[str, ...],
    zip_info: dict[int, tuple[int, float, float]],
) -> None:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    content = f'''"""
Auto-generated lookup data for zip2info.
Do not edit manually - regenerate with: python scripts/compile_data.py

Timezones are derived from ZIP centroids with timezonefinder.
Coordinates merge GeoNames (CC BY 4.0), Census ZCTA centroids (public domain),
and manual overrides.
Coverage: {len(zip_info)} ZIP codes across {len(timezones)} timezones.
"""

# Timezone strings indexed by ID
TIMEZONES: tuple[str, ...] = (
{_format_tuple_lines(timezones)}
)

# Zip code (as int) -> (timezone index, latitude, longitude)
ZIP_INFO: dict[int, tuple[int, float, float]] = {{
{_format_zip_info_entries(zip_info)}
}}
'''
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


def main() -> int:
    previous = _load_previous_dataset()

    coordinates = _merge_coordinates(
        _download_census_zcta_coordinates(),
        _download_geonames_coordinates(),
        _load_manual_overrides(),
    )

    timezones, zip_info = _build_zip_info(coordinates, previous)
    _validate(timezones, zip_info, previous)

    added = len(set(zip_info) - {int(geoid) for geoid in previous})
    print(
        f"Compiled {len(zip_info)} ZIP codes ({added:+d} vs previous) "
        f"across {len(timezones)} timezones"
    )
    _write_data_module(timezones, zip_info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
