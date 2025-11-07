"""
Render graphical stackup visualizations as KiCad graphics.
This is the adapter layer - converts our graphics models to KiCad primitives.
"""
import math
from typing import TYPE_CHECKING, List, Tuple, cast

from ..core.graphics_models import (
    StackupVisualization,
    GraphicalStackupConfig,
    LayerRectangle,
    LeaderLine,
    CalloutText,
)
from ..core.models import LayerType

if TYPE_CHECKING:
    from kipy.board import Board, BoardLayerClass
    from kipy.board_types import (
        FootprintInstance, BoardText, BoardSegment, BoardRectangle,
        BoardLayer, TextAttributes
    )
    from kipy.geometry import Vector2

try:
    from kipy.board import Board, BoardLayerClass
    from kipy.board_types import (
        FootprintInstance, BoardText, BoardSegment, BoardRectangle,
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
    BoardRectangle = None  # type: ignore
    BoardLayer = None  # type: ignore
    Vector2 = None  # type: ignore
    BoardLayerClass = None  # type: ignore
    from_mm = None  # type: ignore


def render_graphical_stackup(
    board: 'Board',
    visualization: StackupVisualization,
    config: GraphicalStackupConfig = None,
    layer: 'BoardLayer' = None
) -> 'FootprintInstance':
    """
    Render graphical stackup visualization as a KiCad footprint.

    Args:
        board: KiCad Board instance
        visualization: StackupVisualization to render
        config: Graphical stackup configuration (optional)
        layer: Target layer for graphics (defaults to Dwgs.User)

    Returns:
        Created FootprintInstance

    Raises:
        RuntimeError: If rendering fails
    """
    if not KICAD_AVAILABLE:
        raise ImportError("kicad-python is not available")

    if config is None:
        config = GraphicalStackupConfig()

    if layer is None:
        layer = BoardLayer.BL_Dwgs_User

    try:
        # Get default graphics settings
        defaults = board.get_graphics_defaults()[BoardLayerClass.BLC_COPPER]

        # Create footprint instance
        fpi = FootprintInstance()
        fpi.layer = BoardLayer.BL_F_Cu
        fpi.reference_field.text.value = "STACKUP_GRAPHIC"
        fpi.reference_field.visible = False
        fpi.value_field.visible = False
        fpi.attributes.not_in_schematic = True
        fpi.attributes.exclude_from_bill_of_materials = True
        fpi.attributes.exclude_from_position_files = True

        fp = fpi.definition

        # Render each graphical element
        for element in visualization.elements:
            if isinstance(element, LayerRectangle):
                _add_rectangle(fp, element, layer, config)
            elif isinstance(element, LeaderLine):
                _add_leader_line(fp, element, layer, config)
            elif isinstance(element, CalloutText):
                _add_callout_text(fp, element, layer, config, defaults)

        # Create on board
        created = board.create_items(fpi)

        if not created or len(created) == 0:
            raise RuntimeError("Failed to create graphical stackup on board")

        return cast(FootprintInstance, created[0])

    except Exception as e:
        raise RuntimeError(f"Failed to render graphical stackup to board: {e}")


def _generate_hatch_lines(
    x: float,
    y: float,
    width: float,
    height: float,
    spacing: float,
    angle_deg: float = 45.0
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Generate hatch pattern line segments within a rectangle.

    Args:
        x: Rectangle left x coordinate (mm)
        y: Rectangle top y coordinate (mm)
        width: Rectangle width (mm)
        height: Rectangle height (mm)
        spacing: Spacing between hatch lines (mm)
        angle_deg: Angle of hatch lines in degrees (default: 45)

    Returns:
        List of line segments as ((x1, y1), (x2, y2))
    """
    lines = []
    angle_rad = math.radians(angle_deg)

    # Calculate the diagonal extent to ensure full coverage
    diagonal = math.sqrt(width**2 + height**2)

    # For 45-degree hatching, we'll sweep lines across the rectangle
    # Start from top-left corner and work our way to bottom-right

    # Number of lines needed to cover the diagonal
    num_lines = int(diagonal / spacing) + 2

    # Generate lines by sweeping perpendicular to the hatch angle
    for i in range(-num_lines, num_lines + 1):
        # Calculate the offset perpendicular to the hatch direction
        offset = i * spacing

        # Start point on the left/top edge
        # For 45 degrees, we start from various points along the perimeter
        if angle_deg == 45.0:
            # Simplified calculation for 45-degree lines
            # Start from left edge or top edge
            if offset <= 0:
                # Start from left edge
                start_x = x
                start_y = y - offset
            else:
                # Start from top edge
                start_x = x + offset
                start_y = y

            # End point on the right/bottom edge
            # Line goes diagonally at 45 degrees
            end_x = start_x + diagonal
            end_y = start_y + diagonal

        else:
            # General case for arbitrary angles (future enhancement)
            dx = math.cos(angle_rad) * diagonal
            dy = math.sin(angle_rad) * diagonal

            # Calculate start point with perpendicular offset
            perp_dx = -math.sin(angle_rad) * offset
            perp_dy = math.cos(angle_rad) * offset

            start_x = x + perp_dx
            start_y = y + perp_dy

            end_x = start_x + dx
            end_y = start_y + dy

        # Clip line to rectangle bounds
        clipped = _clip_line_to_rect(start_x, start_y, end_x, end_y, x, y, width, height)

        if clipped:
            lines.append(clipped)

    return lines


def _clip_line_to_rect(
    x1: float, y1: float, x2: float, y2: float,
    rect_x: float, rect_y: float, rect_width: float, rect_height: float
) -> Tuple[Tuple[float, float], Tuple[float, float]] | None:
    """
    Clip a line segment to rectangle bounds using Cohen-Sutherland algorithm.

    Args:
        x1, y1: Line start point
        x2, y2: Line end point
        rect_x, rect_y: Rectangle top-left corner
        rect_width, rect_height: Rectangle dimensions

    Returns:
        Clipped line segment as ((x1, y1), (x2, y2)) or None if fully outside
    """
    # Rectangle bounds
    x_min = rect_x
    x_max = rect_x + rect_width
    y_min = rect_y
    y_max = rect_y + rect_height

    # Cohen-Sutherland outcodes
    INSIDE = 0  # 0000
    LEFT = 1    # 0001
    RIGHT = 2   # 0010
    BOTTOM = 4  # 0100
    TOP = 8     # 1000

    def compute_outcode(x: float, y: float) -> int:
        code = INSIDE
        if x < x_min:
            code |= LEFT
        elif x > x_max:
            code |= RIGHT
        if y < y_min:
            code |= TOP
        elif y > y_max:
            code |= BOTTOM
        return code

    outcode1 = compute_outcode(x1, y1)
    outcode2 = compute_outcode(x2, y2)

    while True:
        # Both points inside - accept line
        if outcode1 == 0 and outcode2 == 0:
            return ((x1, y1), (x2, y2))

        # Both points share an outside region - reject line
        if (outcode1 & outcode2) != 0:
            return None

        # Line needs clipping
        # Pick a point that's outside
        outcode = outcode1 if outcode1 != 0 else outcode2

        # Find intersection point
        if outcode & TOP:
            x = x1 + (x2 - x1) * (y_min - y1) / (y2 - y1)
            y = y_min
        elif outcode & BOTTOM:
            x = x1 + (x2 - x1) * (y_max - y1) / (y2 - y1)
            y = y_max
        elif outcode & RIGHT:
            y = y1 + (y2 - y1) * (x_max - x1) / (x2 - x1)
            x = x_max
        elif outcode & LEFT:
            y = y1 + (y2 - y1) * (x_min - x1) / (x2 - x1)
            x = x_min

        # Replace the outside point with the intersection point
        if outcode == outcode1:
            x1, y1 = x, y
            outcode1 = compute_outcode(x1, y1)
        else:
            x2, y2 = x, y
            outcode2 = compute_outcode(x2, y2)


def _add_rectangle(
    fp,
    rect: LayerRectangle,
    layer: 'BoardLayer',
    config: GraphicalStackupConfig
) -> None:
    """
    Add a layer rectangle to the footprint with optional copper hatching.

    Args:
        fp: Footprint definition
        rect: LayerRectangle element
        layer: Target layer
        config: Configuration
    """
    # Add rectangle border
    kicad_rect = BoardRectangle()
    kicad_rect.layer = layer

    # Set rectangle corners
    x, y = rect.position_mm
    kicad_rect.top_left = Vector2.from_xy(from_mm(x), from_mm(y))
    kicad_rect.bottom_right = Vector2.from_xy(
        from_mm(x + rect.width_mm),
        from_mm(y + rect.height_mm)
    )

    # Set line width for the border
    kicad_rect.attributes.width = from_mm(config.leader_line_width_mm)

    # Note: Fill is not settable via the API - rectangles will be unfilled (outline only)
    # This is perfect for our stackup visualization

    fp.add_item(kicad_rect)

    # Add copper hatching if enabled and this is a copper layer
    if (config.copper_hatch_enabled and
        rect.layer_type == LayerType.COPPER.value):
        hatch_lines = _generate_hatch_lines(
            x, y, rect.width_mm, rect.height_mm,
            config.copper_hatch_spacing_mm,
            config.copper_hatch_angle_deg
        )

        # Add each hatch line as a BoardSegment
        for line_start, line_end in hatch_lines:
            segment = BoardSegment()
            segment.layer = layer
            segment.start = Vector2.from_xy(from_mm(line_start[0]), from_mm(line_start[1]))
            segment.end = Vector2.from_xy(from_mm(line_end[0]), from_mm(line_end[1]))
            segment.width = from_mm(config.leader_line_width_mm)
            fp.add_item(segment)


def _add_leader_line(
    fp,
    leader: LeaderLine,
    layer: 'BoardLayer',
    config: GraphicalStackupConfig
) -> None:
    """
    Add leader line segments to the footprint.

    Leader lines are composed of multiple BoardSegment primitives.

    Args:
        fp: Footprint definition
        leader: LeaderLine element
        layer: Target layer
        config: Configuration
    """
    # Add each segment of the leader line
    for segment_start, segment_end in leader.segments:
        segment = BoardSegment()
        segment.layer = layer

        start_x, start_y = segment_start
        end_x, end_y = segment_end

        segment.start = Vector2.from_xy(from_mm(start_x), from_mm(start_y))
        segment.end = Vector2.from_xy(from_mm(end_x), from_mm(end_y))
        segment.width = from_mm(config.leader_line_width_mm)

        fp.add_item(segment)


def _add_callout_text(
    fp,
    callout: CalloutText,
    layer: 'BoardLayer',
    config: GraphicalStackupConfig,
    defaults
) -> None:
    """
    Add callout text to the footprint.

    Args:
        fp: Footprint definition
        callout: CalloutText element
        layer: Target layer
        config: Configuration
        defaults: Default graphics settings from board
    """
    text = BoardText()
    text.layer = layer
    text.value = callout.text

    x, y = callout.position_mm
    text.position = Vector2.from_xy(from_mm(x), from_mm(y))

    # Clone defaults for text attributes
    text.attributes = defaults.text.clone() if hasattr(defaults.text, 'clone') else defaults.text

    # Set font size first
    try:
        text.attributes.size.x = from_mm(callout.font_size_mm)
        text.attributes.size.y = from_mm(callout.font_size_mm)
    except Exception as e:
        print(f"Warning: Could not set text size: {e}")

    # Set thickness
    try:
        text.attributes.stroke_width = from_mm(0.1)  # 0.1mm line thickness
    except:
        pass

    # Ensure text is not mirrored or rotated
    try:
        text.attributes.mirrored = False
        text.attributes.angle = 0.0
        text.attributes.keep_upright = True
    except:
        pass

    # Set alignment - CRITICAL: Use correct enum values!
    # HorizontalAlignment: HA_UNKNOWN=0, HA_LEFT=1, HA_CENTER=2, HA_RIGHT=3
    # VerticalAlignment: VA_UNKNOWN=0, VA_TOP=1, VA_CENTER=2, VA_BOTTOM=3
    try:
        # Set horizontal alignment explicitly
        if callout.horizontal_align == "center":
            h_align = 2  # HA_CENTER
        elif callout.horizontal_align == "right":
            h_align = 3  # HA_RIGHT
        else:
            # Left alignment - text starts at the position we specified
            h_align = 1  # HA_LEFT (NOT 0!)

        text.attributes.horizontal_alignment = h_align

        # Set vertical alignment
        if callout.vertical_align == "center":
            v_align = 2  # VA_CENTER (NOT 1!)
        elif callout.vertical_align == "bottom":
            v_align = 3  # VA_BOTTOM
        else:
            v_align = 1  # VA_TOP

        text.attributes.vertical_alignment = v_align

    except Exception as e:
        print(f"Warning: Could not set text alignment: {e}")
        import traceback
        traceback.print_exc()

    fp.add_item(text)


def render_graphical_stackup_to_svg(
    visualization: StackupVisualization,
    config: GraphicalStackupConfig = None
) -> str:
    """
    Render graphical stackup visualization as SVG (for testing or export).

    Args:
        visualization: StackupVisualization to render
        config: Graphical stackup configuration (optional)

    Returns:
        SVG string
    """
    if config is None:
        config = GraphicalStackupConfig()

    svg_parts = [
        f'<svg width="{visualization.total_width_mm}mm" height="{visualization.total_height_mm}mm" '
        f'viewBox="0 0 {visualization.total_width_mm} {visualization.total_height_mm}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    # Render each element
    for element in visualization.elements:
        if isinstance(element, LayerRectangle):
            x, y = element.position_mm
            svg_parts.append(
                f'  <rect x="{x}" y="{y}" width="{element.width_mm}" height="{element.height_mm}" '
                f'fill="none" stroke="black" stroke-width="{config.leader_line_width_mm}"/>'
            )

            # Add copper hatching if enabled
            if (config.copper_hatch_enabled and
                element.layer_type == LayerType.COPPER.value):
                hatch_lines = _generate_hatch_lines(
                    x, y, element.width_mm, element.height_mm,
                    config.copper_hatch_spacing_mm,
                    config.copper_hatch_angle_deg
                )

                for line_start, line_end in hatch_lines:
                    svg_parts.append(
                        f'  <line x1="{line_start[0]}" y1="{line_start[1]}" '
                        f'x2="{line_end[0]}" y2="{line_end[1]}" '
                        f'stroke="black" stroke-width="{config.leader_line_width_mm}"/>'
                    )

        elif isinstance(element, LeaderLine):
            # Render each segment of the leader line
            for segment_start, segment_end in element.segments:
                start_x, start_y = segment_start
                end_x, end_y = segment_end
                svg_parts.append(
                    f'  <line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" '
                    f'stroke="black" stroke-width="{config.leader_line_width_mm}"/>'
                )

        elif isinstance(element, CalloutText):
            x, y = element.position_mm

            # Adjust text-anchor based on alignment
            text_anchor = "start"
            if element.horizontal_align == "center":
                text_anchor = "middle"
            elif element.horizontal_align == "right":
                text_anchor = "end"

            # Adjust dominant-baseline based on vertical alignment
            baseline = "middle"
            if element.vertical_align == "top":
                baseline = "hanging"
            elif element.vertical_align == "bottom":
                baseline = "baseline"

            svg_parts.append(
                f'  <text x="{x}" y="{y}" font-size="{element.font_size_mm}" '
                f'text-anchor="{text_anchor}" dominant-baseline="{baseline}">{element.text}</text>'
            )

    svg_parts.append('</svg>')

    return '\n'.join(svg_parts)
