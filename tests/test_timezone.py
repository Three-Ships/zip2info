"""Tests for zip2info timezone lookup."""

from zoneinfo import ZoneInfo

import pytest

import zip2info
from zip2info._data import TIMEZONES, ZIP_INFO

# Stated here rather than imported from scripts/compile_data.py: importing the
# generator's own allowlist would make the assertion vacuous. This is the
# contract the package promises -- US zones only.
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


class TestStringInput:
    """Test timezone lookup with string zip codes."""

    def test_basic_lookup(self) -> None:
        """Basic string zip code lookup."""
        assert zip2info.timezone("90210") == "America/Los_Angeles"
        assert zip2info.timezone("10001") == "America/New_York"
        assert zip2info.timezone("60601") == "America/Chicago"

    def test_leading_zero_zipcode(self) -> None:
        """Zip codes with leading zeros (Northeast US)."""
        assert zip2info.timezone("01001") == "America/New_York"
        assert zip2info.timezone("06001") == "America/New_York"
        assert zip2info.timezone("07001") == "America/New_York"
        assert zip2info.timezone("00501") == "America/New_York"

    def test_not_found_returns_none(self) -> None:
        """Unknown zip codes return None."""
        assert zip2info.timezone("00000") is None
        assert zip2info.timezone("99999") is None


class TestIntegerInput:
    """Test timezone lookup with integer zip codes."""

    def test_basic_lookup(self) -> None:
        """Basic integer zip code lookup."""
        assert zip2info.timezone(90210) == "America/Los_Angeles"
        assert zip2info.timezone(10001) == "America/New_York"
        assert zip2info.timezone(60601) == "America/Chicago"

    def test_leading_zero_as_integer(self) -> None:
        """Integer zip codes that would have leading zeros as strings."""
        assert zip2info.timezone(1001) == "America/New_York"
        assert zip2info.timezone(6001) == "America/New_York"
        assert zip2info.timezone(501) == "America/New_York"

    def test_not_found_returns_none(self) -> None:
        """Unknown integer zip codes return None."""
        assert zip2info.timezone(0) is None
        assert zip2info.timezone(99999) is None


class TestIndianaTimezones:
    """Test Indiana's complex county-level timezone boundaries."""

    def test_indianapolis_eastern(self) -> None:
        """Indianapolis area - Eastern time."""
        assert zip2info.timezone("46201") == "America/Indiana/Indianapolis"
        assert zip2info.timezone("46204") == "America/Indiana/Indianapolis"

    def test_indiana_central_time_counties(self) -> None:
        """Northwest Indiana counties on Central time."""
        assert zip2info.timezone("46401") == "America/Chicago"

    def test_indiana_other_eastern_zones(self) -> None:
        """Other Indiana Eastern time zones."""
        result = zip2info.timezone("47591")
        assert result is not None
        assert "Indiana" in result or result == "America/Chicago"


class TestNorthDakotaTimezones:
    """Test North Dakota's split counties."""

    def test_north_dakota_central(self) -> None:
        """Most of North Dakota is Central time."""
        assert zip2info.timezone("58102") == "America/Chicago"

    def test_north_dakota_mountain(self) -> None:
        """Southwest ND counties on Mountain time."""
        result = zip2info.timezone("58645")
        assert result in ("America/Denver", "America/Chicago", None)


class TestAlaskaTimezones:
    """Test Alaska's multiple timezones."""

    def test_anchorage(self) -> None:
        """Anchorage area - Alaska time."""
        assert zip2info.timezone("99501") == "America/Anchorage"

    def test_juneau(self) -> None:
        """Juneau - Alaska time."""
        result = zip2info.timezone("99850")
        assert result in ("America/Juneau", "America/Anchorage", "America/Sitka")

    def test_adak(self) -> None:
        """Adak - Hawaii-Aleutian time."""
        assert zip2info.timezone("99546") == "America/Adak"


class TestHawaii:
    """Test Hawaii timezone."""

    def test_honolulu(self) -> None:
        """Honolulu - Hawaii time."""
        assert zip2info.timezone("96801") == "Pacific/Honolulu"

    def test_maui(self) -> None:
        """Maui - Hawaii time."""
        assert zip2info.timezone("96768") == "Pacific/Honolulu"


class TestArizona:
    """Test Arizona (no DST except Navajo Nation)."""

    def test_phoenix(self) -> None:
        """Phoenix - Mountain Standard (no DST)."""
        assert zip2info.timezone("85001") == "America/Phoenix"

    def test_phoenix_metro(self) -> None:
        """Phoenix metro area (Queen Creek) - Mountain Standard (no DST)."""
        assert zip2info.timezone("85142") == "America/Phoenix"

    def test_tucson(self) -> None:
        """Tucson - Mountain Standard (no DST)."""
        assert zip2info.timezone("85701") == "America/Phoenix"


class TestEdgeCases:
    """Test edge cases and invalid inputs."""

    def test_empty_string(self) -> None:
        """Empty string returns None."""
        assert zip2info.timezone("") is None

    def test_non_numeric_string(self) -> None:
        """Non-numeric strings return None."""
        assert zip2info.timezone("abcde") is None
        assert zip2info.timezone("hello") is None

    def test_float_input(self) -> None:
        """Float input should work (converted to int)."""
        assert zip2info.timezone(90210.0) == "America/Los_Angeles"

    def test_none_input(self) -> None:
        """None input returns None."""
        assert zip2info.timezone(None) is None  # type: ignore[arg-type]

    def test_negative_number(self) -> None:
        """Negative numbers return None."""
        assert zip2info.timezone(-12345) is None

    def test_too_long_zipcode(self) -> None:
        """Zip+4 format returns None (only 5-digit supported)."""
        assert zip2info.timezone("902100001") is None
        assert zip2info.timezone("90210-0001") is None


class TestAllTimezones:
    """Verify all returned timezones are valid IANA format."""

    def test_timezone_format(self) -> None:
        """All timezones should be in IANA format (contain '/')."""
        for tz in TIMEZONES:
            assert "/" in tz, f"Invalid timezone format: {tz}"
            assert tz.startswith(("America/", "Pacific/")), f"Unexpected timezone: {tz}"

    def test_only_us_timezones_are_shipped(self) -> None:
        """A centroid can land abroad; those ZIPs must not ship.

        ``America/`` is a continent, so the prefix check above would happily
        admit America/Toronto or America/Sao_Paulo.
        """
        assert set(TIMEZONES) <= US_TIMEZONES

    def test_every_timezone_index_is_in_range(self) -> None:
        """ZIP 00926 once carried index 37 against a 30-entry table."""
        for zipcode, (tz_idx, _, _) in ZIP_INFO.items():
            assert 0 <= tz_idx < len(TIMEZONES), f"{zipcode} has index {tz_idx}"

    def test_every_timezone_is_loadable(self) -> None:
        for tz in TIMEZONES:
            assert ZoneInfo(tz) is not None


class TestRegressions:
    """ZIPs that the pre-1.1.0 dataset got wrong."""

    def test_zips_absent_from_the_frozen_dataset(self) -> None:
        """The generator used to re-read its own output, so it never grew."""
        assert zip2info.timezone("78074") == "America/Chicago"

    def test_puerto_rico_no_longer_raises(self) -> None:
        """00926 used to raise IndexError; PR ships in its own GeoNames file."""
        assert zip2info.timezone("00926") == "America/Puerto_Rico"
        assert zip2info.timezone("00601") == "America/Puerto_Rico"

    @pytest.mark.parametrize(
        ("zipcode", "expected"),
        [
            ("00802", "America/St_Thomas"),
            ("96910", "Pacific/Guam"),
            ("96950", "Pacific/Saipan"),
            ("96799", "Pacific/Pago_Pago"),
        ],
    )
    def test_territories(self, zipcode: str, expected: str) -> None:
        assert zip2info.timezone(zipcode) == expected

    def test_overseas_military_zips_are_omitted(self) -> None:
        """APO/FPO centroids sit on the overseas base, not on US soil."""
        assert zip2info.timezone("09001") is None
