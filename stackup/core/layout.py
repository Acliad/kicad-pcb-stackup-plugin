"""
Table layout algorithms.
Pure functions - no side effects, no KiCad imports.
"""
from typing import List, Tuple, Dict
from .models import StackupData, TableLayout, TableCell, TableConfig, LayerType
from .formatting import format_thickness, format_epsilon, format_loss_tangent, format_layer_name


def calculate_table_layout(
    stackup: StackupData,
    config: TableConfig = None
) -> TableLayout:
    """
    Calculate table layout from stackup data.

    Args:
        stackup: Stackup data model
        config: Table configuration (uses defaults if None)

    Returns:
        TableLayout with cell positions and sizes
    """
    if config is None:
        config = TableConfig()

    if config.style == "detailed":
        return _detailed_layout(stackup, config)
    elif config.style == "compact":
        return _compact_layout(stackup, config)
    else:
        return _minimal_layout(stackup, config)


def _detailed_layout(stackup: StackupData, config: TableConfig) -> TableLayout:
    """
    Full table with all properties.

    Columns: Layer | Type | Thickness | Material | εᵣ | tan δ

    Args:
        stackup: Stackup data
        config: Table configuration

    Returns:
        TableLayout for detailed view
    """
    cells = []
    row = 0

    # Build column list based on config
    columns = ["Layer", "Type", "Thickness"]
    if config.show_material:
        columns.append("Material")
    if config.show_epsilon:
        columns.append("εᵣ")
    if config.show_loss_tangent:
        columns.append("tan δ")
    if config.show_color:
        columns.append("Color")

    # Header row
    for col, header in enumerate(columns):
        cells.append(TableCell(
            text=header,
            row=row,
            col=col,
            width=15.0,  # Will be recalculated
            height=config.row_height,
            align="center",
            is_header=True
        ))

    # Data rows
    row = 1
    for layer in stackup.layers:
        col = 0

        # Layer name
        cells.append(TableCell(
            text=format_layer_name(layer.name),
            row=row,
            col=col,
            width=15.0,
            height=config.row_height,
            align="left"
        ))
        col += 1

        # Layer type
        cells.append(TableCell(
            text=layer.layer_type.value.capitalize(),
            row=row,
            col=col,
            width=15.0,
            height=config.row_height,
            align="center"
        ))
        col += 1

        # Thickness
        cells.append(TableCell(
            text=format_thickness(layer.thickness, unit=config.units),
            row=row,
            col=col,
            width=15.0,
            height=config.row_height,
            align="right"
        ))
        col += 1

        # Material (optional)
        if config.show_material:
            cells.append(TableCell(
                text=layer.material,
                row=row,
                col=col,
                width=15.0,
                height=config.row_height,
                align="left"
            ))
            col += 1

        # Epsilon (optional)
        if config.show_epsilon:
            epsilon_text = format_epsilon(layer.epsilon_r) if layer.epsilon_r else "—"
            cells.append(TableCell(
                text=epsilon_text,
                row=row,
                col=col,
                width=10.0,
                height=config.row_height,
                align="center"
            ))
            col += 1

        # Loss tangent (optional)
        if config.show_loss_tangent:
            tan_delta_text = format_loss_tangent(layer.loss_tangent) if layer.loss_tangent else "—"
            cells.append(TableCell(
                text=tan_delta_text,
                row=row,
                col=col,
                width=10.0,
                height=config.row_height,
                align="center"
            ))
            col += 1

        # Color (optional)
        if config.show_color:
            color_text = layer.color if layer.color else "—"
            cells.append(TableCell(
                text=color_text,
                row=row,
                col=col,
                width=10.0,
                height=config.row_height,
                align="center"
            ))
            col += 1

        row += 1

    # Calculate optimal column widths
    column_widths = _calculate_optimal_widths(cells, config)

    # Update cell widths and calculate total width
    total_width = 0.0
    for cell in cells:
        cell.width = column_widths[cell.col]
    total_width = sum(column_widths)

    total_height = row * config.row_height

    return TableLayout(
        cells=cells,
        total_width=total_width,
        total_height=total_height,
        columns=columns,
        row_height=config.row_height,
        cell_padding=config.cell_padding
    )


def _compact_layout(stackup: StackupData, config: TableConfig) -> TableLayout:
    """
    Compact table with essential information only.

    Columns: Layer | Thickness | Material

    Args:
        stackup: Stackup data
        config: Table configuration

    Returns:
        TableLayout for compact view
    """
    cells = []
    row = 0

    columns = ["Layer", "Thickness", "Material"]

    # Header row
    for col, header in enumerate(columns):
        cells.append(TableCell(
            text=header,
            row=row,
            col=col,
            width=15.0,
            height=config.row_height,
            align="center",
            is_header=True
        ))

    # Data rows
    row = 1
    for layer in stackup.layers:
        # Layer name
        cells.append(TableCell(
            text=format_layer_name(layer.name),
            row=row,
            col=0,
            width=15.0,
            height=config.row_height,
            align="left"
        ))

        # Thickness
        cells.append(TableCell(
            text=format_thickness(layer.thickness, unit=config.units),
            row=row,
            col=1,
            width=15.0,
            height=config.row_height,
            align="right"
        ))

        # Material
        cells.append(TableCell(
            text=layer.material,
            row=row,
            col=2,
            width=15.0,
            height=config.row_height,
            align="left"
        ))

        row += 1

    # Calculate optimal column widths
    column_widths = _calculate_optimal_widths(cells, config)

    # Update cell widths
    for cell in cells:
        cell.width = column_widths[cell.col]

    total_width = sum(column_widths)
    total_height = row * config.row_height

    return TableLayout(
        cells=cells,
        total_width=total_width,
        total_height=total_height,
        columns=columns,
        row_height=config.row_height,
        cell_padding=config.cell_padding
    )


def _minimal_layout(stackup: StackupData, config: TableConfig) -> TableLayout:
    """
    Minimal table showing only copper layers.

    Columns: Layer | Thickness

    Args:
        stackup: Stackup data
        config: Table configuration

    Returns:
        TableLayout for minimal view
    """
    cells = []
    row = 0

    columns = ["Layer", "Thickness"]

    # Header row
    for col, header in enumerate(columns):
        cells.append(TableCell(
            text=header,
            row=row,
            col=col,
            width=15.0,
            height=config.row_height,
            align="center",
            is_header=True
        ))

    # Data rows - copper layers only
    row = 1
    for layer in stackup.layers:
        if layer.layer_type == LayerType.COPPER:
            # Layer name
            cells.append(TableCell(
                text=format_layer_name(layer.name),
                row=row,
                col=0,
                width=15.0,
                height=config.row_height,
                align="left"
            ))

            # Thickness
            cells.append(TableCell(
                text=format_thickness(layer.thickness, unit=config.units),
                row=row,
                col=1,
                width=15.0,
                height=config.row_height,
                align="right"
            ))

            row += 1

    # Calculate optimal column widths
    column_widths = _calculate_optimal_widths(cells, config)

    # Update cell widths
    for cell in cells:
        cell.width = column_widths[cell.col]

    total_width = sum(column_widths)
    total_height = row * config.row_height

    return TableLayout(
        cells=cells,
        total_width=total_width,
        total_height=total_height,
        columns=columns,
        row_height=config.row_height,
        cell_padding=config.cell_padding
    )


def _calculate_optimal_widths(cells: List[TableCell], config: TableConfig) -> List[float]:
    """
    Calculate optimal column widths based on content.

    Args:
        cells: List of all cells
        config: Table configuration

    Returns:
        List of column widths in mm
    """
    # Group cells by column
    columns: Dict[int, List[TableCell]] = {}
    for cell in cells:
        if cell.col not in columns:
            columns[cell.col] = []
        columns[cell.col].append(cell)

    # Calculate max width per column
    widths = []
    for col_idx in sorted(columns.keys()):
        max_width = 0.0
        for cell in columns[col_idx]:
            # Estimate text width (approximate: ~0.6mm per character at 3mm font)
            char_width = config.font_size * 0.6
            text_width = len(cell.text) * char_width
            cell_width = text_width + (config.cell_padding * 2)
            max_width = max(max_width, cell_width)

        # Minimum width of 10mm
        max_width = max(max_width, 10.0)
        widths.append(max_width)

    return widths


def calculate_cell_position(
    cell: TableCell,
    layout: TableLayout,
    origin_x: float = 0.0,
    origin_y: float = 0.0
) -> Tuple[float, float]:
    """
    Calculate absolute position of a cell.

    Args:
        cell: Table cell
        layout: Complete table layout
        origin_x: X origin offset in mm
        origin_y: Y origin offset in mm

    Returns:
        Tuple of (x, y) position in mm
    """
    # Calculate X position (sum of all previous column widths)
    x = origin_x
    for col_idx in range(cell.col):
        # Find width of that column
        for c in layout.cells:
            if c.col == col_idx:
                x += c.width
                break

    # Calculate Y position
    y = origin_y + (cell.row * layout.row_height)

    return (x, y)
