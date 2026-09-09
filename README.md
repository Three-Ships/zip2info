# zip2info

Fast, zero-dependency US ZIP code lookups for Python.

- **41,000+ zip codes** mapped to IANA timezones, including Puerto Rico and the territories
- **Geocoordinates** for ZIP centroids (latitude/longitude)
- **Zero dependencies** — pure Python, works everywhere
- **O(1) lookup** — instant hash table lookups, no database or file I/O
- **Type-annotated** — full type hints included

## Installation

```bash
pip install zip2info
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add zip2info
```

## Usage

```python
import zip2info

# Timezone lookup
tz = zip2info.timezone("90210")
print(tz)  # America/Los_Angeles

# Coordinate lookup (latitude, longitude)
coords = zip2info.coordinates("90210")
print(coords)  # (34.0901, -118.4065)

# Rich metadata
record = zip2info.info("10001")
print(record.timezone)   # America/New_York
print(record.latitude)   # 40.7484
print(record.longitude)  # -73.9967

# Works with integers too
tz = zip2info.timezone(60601)
print(tz)  # America/Chicago

# Returns None if zip code not found
tz = zip2info.timezone("00000")
print(tz)  # None
```

## API

### `timezone(zipcode: str | int) -> str | None`

Returns the IANA timezone string for a US ZIP code.

### `coordinates(zipcode: str | int) -> tuple[float, float] | None`

Returns `(latitude, longitude)` for a US ZIP code, or `None` if unavailable.

### `info(zipcode: str | int) -> ZipInfo | None`

Returns a `ZipInfo` dataclass with `zipcode`, `timezone`, `latitude`, and `longitude`.
Returns `None` when timezone or coordinate data is unavailable.

## Data sources

- **Coordinates** (merged in priority order):
  1. U.S. Census ZCTA gazetteer centroids (public domain)
  2. [GeoNames](https://www.geonames.org/) postal codes for the US and its territories ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))
  3. Manual overrides in `data/coordinate_overrides.json`
- **Timezones**: derived from each ZIP centroid at build time with
  [timezonefinder](https://github.com/jannikmi/timezonefinder). Deriving rather than
  copying is what lets coverage track the upstream feeds; the shipped package stays
  dependency-free.

Only US timezones are shipped. A ZIP centroid can land on foreign soil — APO/FPO/DPO
codes carry the coordinates of the overseas base — and those ZIPs are omitted rather
than reported with a foreign local time. Note that `America/` is a continent, not a
country, so it is not a usable filter on its own.

Regenerate packaged data with:

```bash
python scripts/compile_data.py
```

## Migration from zip2tz

`zip2info` is a new PyPI package and import path. Existing `zip2tz` installs are unchanged.

```python
# before
import zip2tz
zip2tz.timezone("90210")

# after
import zip2info
zip2info.timezone("90210")
```

## Coverage

Covers all 50 US states plus DC, including Alaska, Hawaii, Indiana county-level boundaries, and other edge cases.

## Data accuracy

Timezone and coordinate mappings are provided on a **best-effort basis**. ZIP codes can span multiple timezones or areas, and coordinate points are centroids/estimates rather than exact address locations.

If you find incorrect data, please open an issue with the ZIP code, expected value, and a source if available.

## License

MIT License — see [LICENSE](LICENSE) for details.

Coordinate data includes GeoNames material licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
