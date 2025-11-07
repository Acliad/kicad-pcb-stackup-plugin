"""
Render table layouts as KiCad graphics.
This is the adapter layer - converts our models to KiCad types.
"""
from typing import TYPE_CHECKING, List, cast

from ..core.models import TableLayout, TableCell, TableConfig
from ..core.layout import calculate_cell_position

if TYPE_CHECKING:
    from kipy.board import Board, BoardLayerClass
    from kipy.board_types import (
        FootprintInstance, BoardText, BoardSegment,
        BoardLayer, TextAttributes
    )
    from kipy.geometry import Vector2

try:
    from kipy.board import Board, BoardLayerClass
    from kipy.board_types import (
        FootprintInstance, BoardText, BoardSegment,
        BoardLayer
    )
    from kipy.geometry import Vector2
    from kipy.util import from_mm
    KICAD_AVAILABLE = True
except ImportError:
    KICAD_AVAILABLE = False
    Board = None  # type: ignore
    FootprintInstance = None  # type: ignore
    BoardText = None  # type: ignore
    BoardSegment = None  # type: ignore
    BoardLayer = None  # type: ignore
    Vector2 = None  # type: ignore
    BoardLayerClass = None  # type: ignore
    from_mm = None  # type: ignore


def render_table_to_board(
    board: 'Board',
    layout: TableLayout,
    config: TableConfig = None,
    layer: 'BoardLayer' = None
) -> 'FootprintInstance':
    """
    Render table layout as a KiCad footprint.

    Args:
        board: KiCad Board instance
        layout: TableLayout to render
        config: Table configuration (optional)
        layer: Target layer for graphics (defaults to Dwgs.User)

    Returns:
        Created FootprintInstance

    Raises:
        RuntimeError: If rendering fails
    """
    if not KICAD_AVAILABLE:
        raise ImportError("kicad-python is not available")

    if config is None:
        config = TableConfig()

    if layer is None:
        layer = BoardLayer.BL_Dwgs_User

    try:
        # Get default graphics settings
        defaults = board.get_graphics_defaults()[BoardLayerClass.BLC_COPPER]

        # Create footprint instance
        fpi = FootprintInstance()
        fpi.layer = BoardLayer.BL_F_Cu
        fpi.reference_field.text.value = "STACKUP"
        fpi.reference_field.visible = False
        fpi.value_field.visible = False
        fpi.attributes.not_in_schematic = True
        fpi.attributes.exclude_from_bill_of_materials = True
        fpi.attributes.exclude_from_position_files = True

        fp = fpi.definition

        # Add text cells
        _add_text_cells(fp, layout, config, layer, defaults)

        # Add grid lines
        _add_grid_lines(fp, layout, config, layer)

        # Create on board
        created = board.create_items(fpi)

        if not created or len(created) == 0:
            raise RuntimeError("Failed to create footprint on board")

        return cast(FootprintInstance, created[0])

    except Exception as e:
        raise RuntimeError(f"Failed to render table to board: {e}")


def _add_text_cells(
    fp,
    layout: TableLayout,
    config: TableConfig,
    layer: 'BoardLayer',
    defaults
) -> None:
    """
    Add text cells to footprint.

    Args:
        fp: Footprint definition
        layout: Table layout
        config: Table configuration
        layer: Target layer
        defaults: Default graphics settings from board
    """
    for cell in layout.cells:
        text = BoardText()
        text.layer = layer
        text.value = cell.text

        # Calculate position
        x, y = calculate_cell_position(cell, layout)

        # Adjust for alignment within cell
        if cell.align == "center":
            x += cell.width / 2
        elif cell.align == "right":
            x += cell.width - config.cell_padding

        # Add padding from top
        y += config.cell_padding

        text.position = Vector2.from_xy(from_mm(x), from_mm(y))

        # Text attributes
        text.attributes = defaults.text.clone() if hasattr(defaults.text, 'clone') else defaults.text

        # Override with our settings
        try:
            # Set font size
            text.attributes.size.x = from_mm(config.font_size)
            text.attributes.size.y = from_mm(config.font_size)

            # Set alignment
            if cell.align == "center":
                text.attributes.horizontal_alignment = 1  # Center
            elif cell.align == "right":
                text.attributes.horizontal_alignment = 2  # Right
            else:
                text.attributes.horizontal_alignment = 0  # Left

            # Make headers bold if possible
            if cell.is_header:
                text.attributes.bold = True

        except Exception as e:
            print(f"Warning: Could not set text attributes: {e}")

        fp.add_item(text)


def _add_grid_lines(
    fp,
    layout: TableLayout,
    config: TableConfig,
    layer: 'BoardLayer'
) -> None:
    """
    Add border and grid lines to footprint.

    Args:
        fp: Footprint definition
        layout: Table layout
        config: Table configuration
        layer: Target layer
    """
    # Calculate number of rows
    max_row = max(cell.row for cell in layout.cells)
    num_rows = max_row + 1

    # Calculate cumulative column widths for vertical lines
    col_widths = []
    max_col = max(cell.col for cell in layout.cells)
    for col_idx in range(max_col + 1):
        for cell in layout.cells:
            if cell.col == col_idx:
                col_widths.append(cell.width)
                break

    # Horizontal lines (including top and bottom borders)
    for row in range(num_rows + 1):
        line = BoardSegment()
        line.layer = layer
        y = row * layout.row_height
        line.start = Vector2.from_xy(0, from_mm(y))
        line.end = Vector2.from_xy(from_mm(layout.total_width), from_mm(y))
        line.width = from_mm(config.line_width)
        fp.add_item(line)

    # Vertical lines (including left and right borders)
    x_pos = 0.0
    for col_idx in range(len(col_widths) + 1):
        line = BoardSegment()
        line.layer = layer
        line.start = Vector2.from_xy(from_mm(x_pos), 0)
        line.end = Vector2.from_xy(from_mm(x_pos), from_mm(layout.total_height))
        line.width = from_mm(config.line_width)
        fp.add_item(line)

        if col_idx < len(col_widths):
            x_pos += col_widths[col_idx]


def render_table_to_svg(layout: TableLayout, config: TableConfig = None) -> str:
    """
    Render table layout as SVG (for testing or export).

    Args:
        layout: Table layout
        config: Table configuration (optional)

    Returns:
        SVG string
    """
    if config is None:
        config = TableConfig()

    svg_parts = [
        f'<svg width="{layout.total_width}mm" height="{layout.total_height}mm" '
        f'viewBox="0 0 {layout.total_width} {layout.total_height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    # Add grid lines
    max_row = max(cell.row for cell in layout.cells)
    num_rows = max_row + 1

    # Horizontal lines
    for row in range(num_rows + 1):
        y = row * layout.row_height
        svg_parts.append(
            f'  <line x1="0" y1="{y}" x2="{layout.total_width}" y2="{y}" '
            f'stroke="black" stroke-width="{config.line_width}"/>'
        )

    # Vertical lines
    col_widths = []
    max_col = max(cell.col for cell in layout.cells)
    for col_idx in range(max_col + 1):
        for cell in layout.cells:
            if cell.col == col_idx:
                col_widths.append(cell.width)
                break

    x_pos = 0.0
    for col_idx in range(len(col_widths) + 1):
        svg_parts.append(
            f'  <line x1="{x_pos}" y1="0" x2="{x_pos}" y2="{layout.total_height}" '
            f'stroke="black" stroke-width="{config.line_width}"/>'
        )
        if col_idx < len(col_widths):
            x_pos += col_widths[col_idx]

    # Add text
    for cell in layout.cells:
        x, y = calculate_cell_position(cell, layout)

        # Adjust for alignment
        text_anchor = "start"
        if cell.align == "center":
            x += cell.width / 2
            text_anchor = "middle"
        elif cell.align == "right":
            x += cell.width - config.cell_padding
            text_anchor = "end"
        else:
            x += config.cell_padding

        y += config.cell_padding + config.font_size * 0.75  # Approximate baseline

        weight = "bold" if cell.is_header else "normal"

        svg_parts.append(
            f'  <text x="{x}" y="{y}" font-size="{config.font_size}" '
            f'font-weight="{weight}" text-anchor="{text_anchor}">{cell.text}</text>'
        )

    svg_parts.append('</svg>')

    return '\n'.join(svg_parts)
