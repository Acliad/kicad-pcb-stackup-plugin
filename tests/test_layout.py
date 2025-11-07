"""
Unit tests for table layout algorithms.
These tests don't require KiCad to be running.
"""
import pytest
from stackup.core.models import (
    StackupData, StackupLayer, LayerType,
    TableConfig
)
from stackup.core.layout import (
    calculate_table_layout,
    calculate_cell_position
)


@pytest.fixture
def sample_stackup():
    """Create a sample stackup for testing"""
    return StackupData(
        layers=[
            StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core1", LayerType.DIELECTRIC, 0.2, "FR4", epsilon_r=4.5, loss_tangent=0.02),
            StackupLayer("In1.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core2", LayerType.DIELECTRIC, 1.2, "FR4", epsilon_r=4.5, loss_tangent=0.02),
            StackupLayer("B.Cu", LayerType.COPPER, 0.035, "Copper"),
        ],
        total_thickness=1.505,
        copper_layer_count=3,
        board_name="test.kicad_pcb"
    )


class TestDetailedLayout:
    """Tests for detailed table layout"""

    def test_detailed_layout_basic(self, sample_stackup):
        """Test basic detailed layout generation"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="detailed"))

        assert layout is not None
        assert len(layout.cells) > 0
        assert layout.total_width > 0
        assert layout.total_height > 0

    def test_detailed_layout_columns(self, sample_stackup):
        """Test that detailed layout has correct columns"""
        config = TableConfig(
            style="detailed",
            show_epsilon=True,
            show_loss_tangent=False,
            show_material=True
        )
        layout = calculate_table_layout(sample_stackup, config)

        assert "Layer" in layout.columns
        assert "Type" in layout.columns
        assert "Thickness" in layout.columns
        assert "Material" in layout.columns
        assert "εᵣ" in layout.columns
        assert "tan δ" not in layout.columns  # Disabled in config

    def test_detailed_layout_row_count(self, sample_stackup):
        """Test that layout has correct number of rows"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="detailed"))

        # Should have header + one row per layer
        expected_rows = 1 + len(sample_stackup.layers)
        rows = set(cell.row for cell in layout.cells)
        assert len(rows) == expected_rows

    def test_detailed_layout_header_cells(self, sample_stackup):
        """Test that header cells are marked correctly"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="detailed"))

        header_cells = [cell for cell in layout.cells if cell.is_header]
        assert len(header_cells) > 0
        assert all(cell.row == 0 for cell in header_cells)
        assert all(cell.align == "center" for cell in header_cells)


class TestCompactLayout:
    """Tests for compact table layout"""

    def test_compact_layout_basic(self, sample_stackup):
        """Test basic compact layout generation"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="compact"))

        assert layout is not None
        assert len(layout.cells) > 0

    def test_compact_layout_columns(self, sample_stackup):
        """Test that compact layout has fewer columns"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="compact"))

        assert layout.columns == ["Layer", "Thickness", "Material"]


class TestMinimalLayout:
    """Tests for minimal table layout"""

    def test_minimal_layout_basic(self, sample_stackup):
        """Test basic minimal layout generation"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="minimal"))

        assert layout is not None
        assert len(layout.cells) > 0

    def test_minimal_layout_copper_only(self, sample_stackup):
        """Test that minimal layout shows only copper layers"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="minimal"))

        # Should have header + one row per copper layer
        expected_rows = 1 + sample_stackup.copper_layer_count
        rows = set(cell.row for cell in layout.cells)
        assert len(rows) == expected_rows

    def test_minimal_layout_columns(self, sample_stackup):
        """Test that minimal layout has minimal columns"""
        layout = calculate_table_layout(sample_stackup, TableConfig(style="minimal"))

        assert layout.columns == ["Layer", "Thickness"]


class TestTableConfiguration:
    """Tests for table configuration options"""

    def test_config_show_epsilon(self, sample_stackup):
        """Test epsilon column visibility"""
        config_with = TableConfig(show_epsilon=True)
        layout_with = calculate_table_layout(sample_stackup, config_with)
        assert "εᵣ" in layout_with.columns

        config_without = TableConfig(show_epsilon=False)
        layout_without = calculate_table_layout(sample_stackup, config_without)
        assert "εᵣ" not in layout_without.columns

    def test_config_show_loss_tangent(self, sample_stackup):
        """Test loss tangent column visibility"""
        config_with = TableConfig(show_loss_tangent=True)
        layout_with = calculate_table_layout(sample_stackup, config_with)
        assert "tan δ" in layout_with.columns

        config_without = TableConfig(show_loss_tangent=False)
        layout_without = calculate_table_layout(sample_stackup, config_without)
        assert "tan δ" not in layout_without.columns

    def test_config_show_material(self, sample_stackup):
        """Test material column visibility"""
        config_with = TableConfig(show_material=True)
        layout_with = calculate_table_layout(sample_stackup, config_with)
        assert "Material" in layout_with.columns

        config_without = TableConfig(show_material=False)
        layout_without = calculate_table_layout(sample_stackup, config_without)
        assert "Material" not in layout_without.columns


class TestCellPositioning:
    """Tests for cell position calculations"""

    def test_calculate_cell_position_origin(self, sample_stackup):
        """Test position calculation at origin"""
        layout = calculate_table_layout(sample_stackup, TableConfig())

        # First cell should be at origin
        first_cell = [c for c in layout.cells if c.row == 0 and c.col == 0][0]
        x, y = calculate_cell_position(first_cell, layout, 0, 0)
        assert x == 0
        assert y == 0

    def test_calculate_cell_position_offset(self, sample_stackup):
        """Test position calculation with offset"""
        layout = calculate_table_layout(sample_stackup, TableConfig())

        first_cell = [c for c in layout.cells if c.row == 0 and c.col == 0][0]
        x, y = calculate_cell_position(first_cell, layout, 10, 20)
        assert x == 10
        assert y == 20

    def test_calculate_cell_position_second_row(self, sample_stackup):
        """Test position calculation for second row"""
        config = TableConfig(row_height=5.0)
        layout = calculate_table_layout(sample_stackup, config)

        second_row_cell = [c for c in layout.cells if c.row == 1 and c.col == 0][0]
        x, y = calculate_cell_position(second_row_cell, layout, 0, 0)
        assert x == 0
        assert y == 5.0  # row_height


class TestEmptyStackup:
    """Tests for edge cases"""

    def test_empty_layers(self):
        """Test layout with no layers"""
        empty_stackup = StackupData(
            layers=[],
            total_thickness=0,
            copper_layer_count=0,
            board_name="empty.kicad_pcb"
        )

        layout = calculate_table_layout(empty_stackup, TableConfig())

        # Should still have headers
        assert len(layout.cells) > 0
        header_cells = [c for c in layout.cells if c.is_header]
        assert len(header_cells) > 0
