"""Tests for zip2info coordinate and info lookups."""

import pytest

import zip2info
from zip2info import ZipInfo


class TestCoordinates:
    def test_basic_lookup(self) -> None:
        lat, lon = zip2info.coordinates("90210")
        assert lat == pytest.approx(34.09, abs=0.1)
        assert lon == pytest.approx(-118.41, abs=0.1)

    def test_integer_zipcode(self) -> None:
        coords = zip2info.coordinates(10001)
        assert coords is not None
        lat, lon = coords
        assert lat == pytest.approx(40.75, abs=0.1)
        assert lon == pytest.approx(-73.99, abs=0.1)

    def test_leading_zero_zipcode(self) -> None:
        coords = zip2info.coordinates("01001")
        assert coords is not None

    def test_unknown_zipcode(self) -> None:
        assert zip2info.coordinates("00000") is None

    def test_invalid_input(self) -> None:
        assert zip2info.coordinates("abcde") is None
        assert zip2info.coordinates(None) is None  # type: ignore[arg-type]


class TestInfo:
    def test_basic_lookup(self) -> None:
        record = zip2info.info("90210")
        assert record is not None
        assert isinstance(record, ZipInfo)
        assert record.zipcode == 90210
        assert record.timezone == "America/Los_Angeles"
        assert record.latitude == pytest.approx(34.09, abs=0.1)
        assert record.longitude == pytest.approx(-118.41, abs=0.1)

    def test_unknown_zipcode(self) -> None:
        assert zip2info.info("00000") is None

    def test_generated_zip_info_has_full_coverage(self) -> None:
        from zip2info._data import ZIP_INFO

        # A floor, not an exact count: coverage should be free to grow as the
        # upstream feeds do, but never silently shrink the way it used to when
        # the generator re-read its own output.
        assert len(ZIP_INFO) >= 41_000
        assert 90210 in ZIP_INFO

    def test_generated_zip_info_entry_shape(self) -> None:
        from zip2info._data import ZIP_INFO

        tz_idx, latitude, longitude = ZIP_INFO[90210]
        assert isinstance(tz_idx, int)
        assert isinstance(latitude, float)
        assert isinstance(longitude, float)

    def test_previously_missing_zip_has_coordinates(self) -> None:
        """ZIPs absent from GeoNames should still resolve via fallback sources."""
        coords = zip2info.coordinates("01133")
        assert coords is not None
        lat, lon = coords
        assert lat == pytest.approx(42.17, abs=0.2)
        assert lon == pytest.approx(-72.60, abs=0.2)
