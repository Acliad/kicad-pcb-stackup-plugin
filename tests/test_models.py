"""
Unit tests for core data models.
These tests don't require KiCad to be running.
"""
import pytest
from stackup.core.models import (
    LayerType,
    StackupLayer,
    StackupData,
    TableCell,
    TableLayout,
    TableConfig
)


class TestLayerType:
    """Tests for LayerType enum"""

    def test_layer_types_exist(self):
        """Test that all expected layer types exist"""
        assert LayerType.COPPER
        assert LayerType.DIELECTRIC
        assert LayerType.SOLDERMASK
        assert LayerType.SILKSCREEN

    def test_layer_type_values(self):
        """Test layer type string values"""
        assert LayerType.COPPER.value == "copper"
        assert LayerType.DIELECTRIC.value == "dielectric"
        assert LayerType.SOLDERMASK.value == "soldermask"
        assert LayerType.SILKSCREEN.value == "silkscreen"


class TestStackupLayer:
    """Tests for StackupLayer model"""

    def test_create_basic_layer(self):
        """Test creating a basic stackup layer"""
        layer = StackupLayer(
            name="F.Cu",
            layer_type=LayerType.COPPER,
            thickness=0.035,
            material="Copper"
        )
        assert layer.name == "F.Cu"
        assert layer.layer_type == LayerType.COPPER
        assert layer.thickness == 0.035
        assert layer.material == "Copper"

    def test_create_layer_with_optional_fields(self):
        """Test creating layer with all optional fields"""
        layer = StackupLayer(
            name="Core1",
            layer_type=LayerType.DIELECTRIC,
            thickness=1.2,
            material="FR4",
            color="Green",
            epsilon_r=4.5,
            loss_tangent=0.02
        )
        assert layer.color == "Green"
        assert layer.epsilon_r == 4.5
        assert layer.loss_tangent == 0.02

    def test_layer_optional_fields_default_to_none(self):
        """Test that optional fields default to None"""
        layer = StackupLayer(
            name="Test",
            layer_type=LayerType.COPPER,
            thickness=0.035,
            material="Copper"
        )
        assert layer.color is None
        assert layer.epsilon_r is None
        assert layer.loss_tangent is None


class TestStackupData:
    """Tests for StackupData model"""

    def test_create_stackup_data(self):
        """Test creating stackup data"""
        layers = [
            StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core", LayerType.DIELECTRIC, 1.2, "FR4"),
            StackupLayer("B.Cu", LayerType.COPPER, 0.035, "Copper"),
        ]

        stackup = StackupData(
            layers=layers,
            total_thickness=1.27,
            copper_layer_count=2,
            board_name="test.kicad_pcb"
        )

        assert len(stackup.layers) == 3
        assert stackup.total_thickness == 1.27
        assert stackup.copper_layer_count == 2
        assert stackup.board_name == "test.kicad_pcb"


class TestTableCell:
    """Tests for TableCell model"""

    def test_create_basic_cell(self):
        """Test creating a basic table cell"""
        cell = TableCell(
            text="F.Cu",
            row=0,
            col=0,
            width=15.0,
            height=5.0
        )
        assert cell.text == "F.Cu"
        assert cell.row == 0
        assert cell.col == 0
        assert cell.width == 15.0
        assert cell.height == 5.0

    def test_cell_defaults(self):
        """Test that cell has correct defaults"""
        cell = TableCell(
            text="Test",
            row=0,
            col=0,
            width=10.0,
            height=5.0
        )
        assert cell.align == "left"
        assert cell.is_header is False

    def test_create_header_cell(self):
        """Test creating a header cell"""
        cell = TableCell(
            text="Layer",
            row=0,
            col=0,
            width=15.0,
            height=5.0,
            align="center",
            is_header=True
        )
        assert cell.align == "center"
        assert cell.is_header is True


class TestTableLayout:
    """Tests for TableLayout model"""

    def test_create_table_layout(self):
        """Test creating a table layout"""
        cells = [
            TableCell("Layer", 0, 0, 15.0, 5.0, align="center", is_header=True),
            TableCell("F.Cu", 1, 0, 15.0, 5.0),
        ]

        layout = TableLayout(
            cells=cells,
            total_width=15.0,
            total_height=10.0,
            columns=["Layer"],
            row_height=5.0,
            cell_padding=1.0
        )

        assert len(layout.cells) == 2
        assert layout.total_width == 15.0
        assert layout.total_height == 10.0
        assert layout.columns == ["Layer"]
        assert layout.row_height == 5.0
        assert layout.cell_padding == 1.0

    def test_layout_defaults(self):
        """Test layout default values"""
        layout = TableLayout(
            cells=[],
            total_width=10.0,
            total_height=5.0
        )
        assert layout.columns == []
        assert layout.row_height == 5.0
        assert layout.cell_padding == 1.0


class TestTableConfig:
    """Tests for TableConfig model"""

    def test_config_defaults(self):
        """Test that config has sensible defaults"""
        config = TableConfig()

        assert config.style == "detailed"
        assert config.units == "mm"
        assert config.show_epsilon is True
        assert config.show_loss_tangent is False
        assert config.show_material is True
        assert config.show_color is False
        assert config.font_size == 3.0
        assert config.line_width == 0.15

    def test_create_custom_config(self):
        """Test creating a custom configuration"""
        config = TableConfig(
            style="compact",
            units="mils",
            show_epsilon=False,
            font_size=2.5
        )

        assert config.style == "compact"
        assert config.units == "mils"
        assert config.show_epsilon is False
        assert config.font_size == 2.5
