"""
Unit tests for formatting utilities.
These tests don't require KiCad to be running.
"""
import pytest
from stackup.core.formatting import (
    format_thickness,
    format_epsilon,
    format_loss_tangent,
    truncate_text,
    mils_to_mm,
    mm_to_mils,
    oz_to_mm,
    mm_to_oz,
    format_layer_name
)


class TestFormatThickness:
    """Tests for thickness formatting"""

    def test_format_small_thickness_in_microns(self):
        """Small values should be formatted in µm"""
        assert format_thickness(0.035) == "35.000µm"
        assert format_thickness(0.001) == "1.000µm"

    def test_format_large_thickness_in_mm(self):
        """Large values should be formatted in mm"""
        assert format_thickness(1.6) == "1.600mm"
        assert format_thickness(2.0) == "2.000mm"

    def test_format_thickness_in_mils(self):
        """Should format in mils when requested"""
        result = format_thickness(1.59, unit="mils")
        assert "mil" in result
        # 1.59mm ≈ 62.6 mils
        # Check that the value is approximately correct (62-63 range)
        assert "62" in result or "63" in result

    def test_format_thickness_precision(self):
        """Should respect precision parameter"""
        assert format_thickness(1.234567, precision=2) == "1.23mm"
        assert format_thickness(0.234567, precision=1) == "234.6µm"


class TestFormatEpsilon:
    """Tests for epsilon_r formatting"""

    def test_format_typical_epsilon(self):
        assert format_epsilon(4.5) == "4.50"
        assert format_epsilon(3.2) == "3.20"

    def test_format_epsilon_precision(self):
        """Should format with 2 decimal places"""
        assert format_epsilon(4.123456) == "4.12"


class TestFormatLossTangent:
    """Tests for loss tangent formatting"""

    def test_format_typical_loss_tangent(self):
        assert format_loss_tangent(0.02) == "0.0200"
        assert format_loss_tangent(0.015) == "0.0150"

    def test_format_loss_tangent_precision(self):
        """Should format with 4 decimal places"""
        assert format_loss_tangent(0.123456) == "0.1235"


class TestTruncateText:
    """Tests for text truncation"""

    def test_truncate_long_text(self):
        result = truncate_text("Very Long Layer Name", 10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_dont_truncate_short_text(self):
        text = "Short"
        result = truncate_text(text, 10)
        assert result == text

    def test_truncate_exact_length(self):
        text = "Exact"
        result = truncate_text(text, 5)
        assert result == text


class TestUnitConversions:
    """Tests for unit conversion functions"""

    def test_mils_to_mm(self):
        # 1000 mils = 1 inch = 25.4mm
        assert abs(mils_to_mm(1000) - 25.4) < 0.01
        # 62.6 mils ≈ 1.59mm
        assert abs(mils_to_mm(62.6) - 1.59) < 0.01

    def test_mm_to_mils(self):
        # 25.4mm = 1 inch = 1000 mils
        assert abs(mm_to_mils(25.4) - 1000) < 0.1
        # 1.59mm ≈ 62.6 mils
        assert abs(mm_to_mils(1.59) - 62.6) < 0.1

    def test_oz_to_mm(self):
        # 1 oz/ft² ≈ 35µm ≈ 0.035mm
        assert abs(oz_to_mm(1.0) - 0.035) < 0.001
        # 2 oz/ft² ≈ 70µm ≈ 0.070mm
        assert abs(oz_to_mm(2.0) - 0.070) < 0.001

    def test_mm_to_oz(self):
        # 0.035mm ≈ 1 oz/ft²
        assert abs(mm_to_oz(0.035) - 1.0) < 0.01
        # 0.070mm ≈ 2 oz/ft²
        assert abs(mm_to_oz(0.070) - 2.0) < 0.01

    def test_conversion_round_trip(self):
        """Converting back and forth should preserve value"""
        original = 50.0  # mils
        assert abs(mm_to_mils(mils_to_mm(original)) - original) < 0.01

        original = 2.5  # mm
        assert abs(mils_to_mm(mm_to_mils(original)) - original) < 0.01


class TestFormatLayerName:
    """Tests for layer name formatting"""

    def test_format_layer_name_removes_prefix(self):
        assert format_layer_name("layer_F.Cu") == "F.Cu"
        assert format_layer_name("Layer1") == "1"

    def test_format_layer_name_truncates(self):
        result = format_layer_name("Very Long Layer Name", max_length=10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_format_layer_name_short(self):
        result = format_layer_name("F.Cu")
        assert result == "F.Cu"
