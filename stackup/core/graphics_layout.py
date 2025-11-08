"""
Layout algorithms for graphical stackup visualization.
Pure functions - no KiCad dependencies, fully testable.
"""
from typing import List, Tuple, Dict, Literal
from dataclasses import replace
from .models import StackupData, StackupLayer, LayerType
from .graphics_models import (
    StackupVisualization,
    GraphicalStackupConfig,
    LayerRectangle,
    LeaderLine,
    CalloutText,
    LeaderLineStyle,
    GraphicalElement,
    ThicknessMode,
    CALLOUT_TEXT_PADDING_MM,
    MIN_CALLOUT_SPACING_MM,
    MIN_ELBOW_HEIGHT_MM,
)
from .formatting import format_thickness

# Minimum comfortable horizontal space after elbow endpoint (mm)
# This ensures elbows have visual breathing room
MIN_FINAL_SEGMENT_MM = 5.0


def calculate_tolerance(thickness_mm: float, tolerance_percent: float = 10.0) -> float:
    """
    Calculate thickness tolerance.

    Args:
        thickness_mm: Nominal thickness in mm
        tolerance_percent: Tolerance as percentage (default 10%)

    Returns:
        Tolerance value in mm
    """
    return thickness_mm * (tolerance_percent / 100.0)


def format_callout_text(layer: StackupLayer, config: GraphicalStackupConfig) -> str:
    """
    Format callout text for a layer according to user specification.
    Format: "Material - Thickness ± Tolerance"

    Args:
        layer: StackupLayer to format
        config: Configuration with format template

    Returns:
        Formatted callout string (e.g., "FR4 - 760µm ±5.0µm")
    """
    # Calculate tolerance (assume 10% for now, could be configurable per layer)
    tolerance = calculate_tolerance(layer.thickness, tolerance_percent=10.0)

    # Format thickness and tolerance using the formatting utility
    thickness_str = format_thickness(layer.thickness, precision=1)
    tolerance_str = format_thickness(tolerance, precision=1)

    # Build the callout string: "Material - Thickness ±Tolerance"
    return f"{layer.material} - {thickness_str} ±{tolerance_str}"


def _calculate_layer_heights(
    stackup: StackupData,
    config: GraphicalStackupConfig
) -> List[float]:
    """
    Calculate visual height for each layer based on thickness mode.

    Args:
        stackup: Stackup data with layers and actual thicknesses
        config: Configuration with thickness mode and ratios

    Returns:
        List of heights in mm, one per layer
    """
    if config.thickness_mode == ThicknessMode.UNIFORM:
        # All layers same height
        return [config.uniform_layer_height_mm] * len(stackup.layers)

    elif config.thickness_mode == ThicknessMode.PROPORTIONAL:
        # Fixed ratios: copper=1.0, dielectric=2.0, soldermask=0.3
        heights = []
        for layer in stackup.layers:
            if layer.layer_type == LayerType.COPPER:
                heights.append(config.uniform_layer_height_mm * config.copper_height_ratio)
            elif layer.layer_type == LayerType.DIELECTRIC:
                heights.append(config.uniform_layer_height_mm * config.dielectric_height_ratio)
            elif layer.layer_type == LayerType.SOLDERMASK:
                heights.append(config.uniform_layer_height_mm * config.soldermask_height_ratio)
            else:
                # Fallback for silkscreen, solderpaste, etc.
                heights.append(config.uniform_layer_height_mm * 0.5)
        return heights

    elif config.thickness_mode == ThicknessMode.SCALED:
        # Use actual thickness ratios, scaled to fit within max height
        if not stackup.layers or stackup.total_thickness == 0:
            return [config.uniform_layer_height_mm] * len(stackup.layers)

        # Calculate scale factor to fit within max height
        scale_factor = config.max_total_height_mm / stackup.total_thickness

        # Scale each layer proportionally
        heights = [layer.thickness * scale_factor for layer in stackup.layers]
        return heights

    else:
        # Fallback: uniform
        return [config.uniform_layer_height_mm] * len(stackup.layers)


def _scale_config(config: GraphicalStackupConfig, scale_factor: float) -> GraphicalStackupConfig:
    """
    Create a new config with all dimensions scaled by factor.

    Args:
        config: Original configuration
        scale_factor: Multiplier to apply to all dimensions

    Returns:
        New GraphicalStackupConfig with scaled dimensions
    """
    return GraphicalStackupConfig(
        # Overall scaling - set to None to prevent recursive scaling
        scale_mm=None,

        # Layer sizing
        thickness_mode=config.thickness_mode,
        uniform_layer_height_mm=config.uniform_layer_height_mm * scale_factor,
        layer_width_mm=config.layer_width_mm * scale_factor,
        max_total_height_mm=config.max_total_height_mm * scale_factor,

        # Proportional mode ratios (these are unitless, don't scale)
        copper_height_ratio=config.copper_height_ratio,
        dielectric_height_ratio=config.dielectric_height_ratio,
        soldermask_height_ratio=config.soldermask_height_ratio,

        # Visual spacing
        soldermask_gap_mm=config.soldermask_gap_mm * scale_factor,

        # Copper hatching
        copper_hatch_enabled=config.copper_hatch_enabled,
        copper_hatch_spacing_mm=config.copper_hatch_spacing_mm * scale_factor,
        copper_hatch_angle_deg=config.copper_hatch_angle_deg,

        # Leader lines
        # NOTE: leader_line_length_mm remains constant in absolute units for consistent
        # readability regardless of scale. Only the visual line width scales.
        leader_line_length_mm=config.leader_line_length_mm,
        leader_line_width_mm=config.leader_line_width_mm * scale_factor,

        # Callout text
        callout_format=config.callout_format,
        text_size_mm=config.text_size_mm * scale_factor,
        # NOTE: Callout spacing and elbow thresholds remain constant in absolute units
        # to ensure consistent, professional appearance at all scales. This prevents
        # excessive spacing at large scales and crowding at small scales.
        min_callout_spacing_mm=config.min_callout_spacing_mm,
        min_elbow_height_mm=config.min_elbow_height_mm,

        # Positioning (don't scale origin)
        origin_x_mm=config.origin_x_mm,
        origin_y_mm=config.origin_y_mm,

        # Target layer
        target_layer=config.target_layer,
    )


def _calculate_layout_internal(
    stackup: StackupData,
    config: GraphicalStackupConfig
) -> StackupVisualization:
    """
    Internal function to calculate layout with given config.

    This is separated from calculate_graphical_layout to support two-pass
    scaling calculation.

    Args:
        stackup: Stackup data with layers
        config: Configuration for sizing and positioning

    Returns:
        StackupVisualization with all graphical elements
    """
    elements: List[GraphicalElement] = []
    y_offset = config.origin_y_mm

    # Calculate layer heights based on thickness mode
    layer_heights = _calculate_layer_heights(stackup, config)

    # Create rectangles and initial callouts for each layer
    for idx, layer in enumerate(stackup.layers):
        layer_height = layer_heights[idx]

        # Add gap before soldermask layers (but not before the first layer)
        if idx > 0 and layer.layer_type == LayerType.SOLDERMASK and config.soldermask_gap_mm > 0:
            y_offset += config.soldermask_gap_mm

        # Create layer rectangle with calculated height
        rect = LayerRectangle(
            position_mm=(config.origin_x_mm, y_offset),
            width_mm=config.layer_width_mm,
            height_mm=layer_height,
            layer_name=layer.name,
            layer_type=layer.layer_type.value,  # Store layer type for rendering
            fill=False,
        )
        elements.append(rect)

        # Calculate leader line start point (middle-right of rectangle)
        leader_start_x = config.origin_x_mm + config.layer_width_mm
        leader_start_y = y_offset + (layer_height / 2.0)

        # Initial leader line (straight horizontal)
        leader_end_x = leader_start_x + config.leader_line_length_mm
        leader_end_y = leader_start_y

        leader = LeaderLine(
            position_mm=(leader_start_x, leader_start_y),
            end_position_mm=(leader_end_x, leader_end_y),
            style=LeaderLineStyle.STRAIGHT,
            segments=[
                ((leader_start_x, leader_start_y), (leader_end_x, leader_end_y))
            ],
        )
        elements.append(leader)

        # Create callout text at end of leader line
        callout = CalloutText(
            position_mm=(leader_end_x + CALLOUT_TEXT_PADDING_MM, leader_end_y),
            text=format_callout_text(layer, config),
            font_size_mm=config.text_size_mm,
            horizontal_align="left",
            vertical_align="center",
        )
        elements.append(callout)

        # Move to next layer
        y_offset += layer_height

        # Add gap after soldermask layers
        if layer.layer_type == LayerType.SOLDERMASK and config.soldermask_gap_mm > 0:
            y_offset += config.soldermask_gap_mm

    # Calculate total dimensions (content only, excluding origin offset)
    # Estimate text space proportional to text size (default 1.5mm text → 50mm space, ratio ~33)
    text_space_mm = config.text_size_mm * 33.3
    content_width = config.layer_width_mm + config.leader_line_length_mm + text_space_mm
    content_height = y_offset - config.origin_y_mm

    visualization = StackupVisualization(
        elements=elements,
        total_width_mm=content_width,
        total_height_mm=content_height,
        layer_count=len(stackup.layers),
        bounds_mm=(config.origin_x_mm, config.origin_y_mm, content_width, content_height)
    )

    return visualization


def calculate_graphical_layout(
    stackup: StackupData,
    config: GraphicalStackupConfig
) -> Tuple[StackupVisualization, GraphicalStackupConfig]:
    """
    Calculate graphical cross-section layout with configurable layer heights.

    Creates:
    - Rectangles for each layer (heights based on thickness mode)
    - Straight horizontal leader lines (initially)
    - Text callouts with layer info
    - Optional spacing for soldermask layers

    If config.scale_mm is specified, all dimensions are scaled proportionally
    to achieve the desired total height while maintaining aspect ratio.

    Collision detection and leader line adjustment happen in a separate pass.

    Args:
        stackup: Stackup data with layers
        config: Configuration for sizing and positioning

    Returns:
        Tuple of (StackupVisualization, effective_config) where effective_config
        is the scaled config if scaling was applied, or the original config otherwise.
        The effective_config should be used for subsequent operations like adjust_leader_lines.
    """
    # If scale is not specified, use default dimensions
    if config.scale_mm is None:
        return _calculate_layout_internal(stackup, config), config

    # Two-pass calculation for scaling:
    # 1. Calculate with default dimensions to get base height
    base_layout = _calculate_layout_internal(stackup, config)

    # 2. Calculate scale factor and recalculate with scaled config
    scale_factor = config.scale_mm / base_layout.total_height_mm
    scaled_config = _scale_config(config, scale_factor)

    return _calculate_layout_internal(stackup, scaled_config), scaled_config


def detect_callout_collisions(visualization: StackupVisualization, config: GraphicalStackupConfig) -> List[int]:
    """
    Detect which callout text elements would collide vertically.

    Args:
        visualization: Current stackup visualization
        config: Configuration with min_callout_spacing_mm threshold

    Returns:
        List of element indices that have collisions
    """
    collision_indices = []

    # Extract all callout text elements with their indices
    callouts = [
        (idx, elem)
        for idx, elem in enumerate(visualization.elements)
        if isinstance(elem, CalloutText)
    ]

    # Check vertical spacing between adjacent callouts
    for i in range(len(callouts) - 1):
        idx1, callout1 = callouts[i]
        idx2, callout2 = callouts[i + 1]

        y1 = callout1.position_mm[1]
        y2 = callout2.position_mm[1]
        vertical_gap = abs(y2 - y1)

        # If gap is too small, mark both as collision candidates
        if vertical_gap < config.min_callout_spacing_mm:
            if idx1 not in collision_indices:
                collision_indices.append(idx1)
            if idx2 not in collision_indices:
                collision_indices.append(idx2)

    return collision_indices


def _calculate_elbow_heights(
    groups_to_adjust: List[Tuple[int, int, int]],
    new_callout_positions: List[float],
    elements: List[GraphicalElement],
    config: GraphicalStackupConfig
) -> List[float]:
    """
    Calculate vertical displacement (elbow height) for each adjusted leader.

    Args:
        groups_to_adjust: List of (rect_idx, leader_idx, callout_idx) tuples
        new_callout_positions: Proposed Y positions for callouts
        elements: Current visualization elements
        config: Configuration with layer heights

    Returns:
        List of elbow heights (absolute vertical displacement) for each group
    """
    elbow_heights = []
    for i, (rect_idx, _, _) in enumerate(groups_to_adjust):
        rect = elements[rect_idx]
        rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
        rect_center_y = rect.position_mm[1] + (rect_height / 2.0)
        new_callout_y = new_callout_positions[i]
        elbow_height = abs(new_callout_y - rect_center_y)
        elbow_heights.append(elbow_height)
    return elbow_heights


def _should_use_straight_line(elbow_height: float, config: GraphicalStackupConfig) -> bool:
    """
    Determine if a leader line should remain straight instead of creating an elbow.

    Args:
        elbow_height: Calculated vertical displacement for this leader
        config: Configuration with min_elbow_height_mm threshold

    Returns:
        True if line should be straight (elbow too small), False if elbow should be created
    """
    return elbow_height < config.min_elbow_height_mm


def _adjust_spacing_for_minimum_elbows(
    groups_to_adjust: List[Tuple[int, int, int]],
    new_callout_positions: List[float],
    elbow_heights: List[float],
    elements: List[GraphicalElement],
    config: GraphicalStackupConfig
) -> List[float]:
    """
    Adjust callout positions to ensure elbows meet minimum height threshold.

    Strategy:
    - If elbow < MIN_ELBOW_HEIGHT_MM: Force spacing to create MIN_ELBOW_HEIGHT_MM elbow
    - Expand spacing symmetrically from center to maintain visual balance

    Args:
        groups_to_adjust: List of (rect_idx, leader_idx, callout_idx) tuples
        new_callout_positions: Initial proposed Y positions
        elbow_heights: Calculated elbow heights for each group
        elements: Current visualization elements
        config: Configuration with min_elbow_height_mm threshold

    Returns:
        Adjusted Y positions with minimum elbow heights enforced
    """
    adjusted_positions = list(new_callout_positions)

    for i, (rect_idx, _, _) in enumerate(groups_to_adjust):
        if elbow_heights[i] < config.min_elbow_height_mm:
            # Force minimum elbow height
            rect = elements[rect_idx]
            rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
            rect_center_y = rect.position_mm[1] + (rect_height / 2.0)

            # Determine direction (up or down from layer center)
            if adjusted_positions[i] > rect_center_y:
                # Callout below layer → push down
                adjusted_positions[i] = rect_center_y + config.min_elbow_height_mm
            else:
                # Callout above layer → push up
                adjusted_positions[i] = rect_center_y - config.min_elbow_height_mm

    return adjusted_positions


def _calculate_symmetric_positions(
    groups_to_adjust: List[Tuple[int, int, int]],
    elements: List[GraphicalElement],
    config: GraphicalStackupConfig
) -> List[float]:
    """
    Calculate symmetric callout positions with consistent spacing.

    Strategy:
    - Find the vertical center of all layer rectangles
    - Place callouts symmetrically around that center
    - Use exactly min_callout_spacing_mm between adjacent callouts
    - This ensures consistent spacing regardless of layer positions or visualization scale

    Args:
        groups_to_adjust: List of (rect_idx, leader_idx, callout_idx) tuples
        elements: Current visualization elements
        config: Configuration with min_callout_spacing_mm threshold

    Returns:
        List of Y positions for callouts (evenly spaced in absolute coordinates)
    """
    total_groups = len(groups_to_adjust)
    positions = []

    # Find the vertical center of all layers
    layer_y_positions = []
    for rect_idx, _, _ in groups_to_adjust:
        rect = elements[rect_idx]
        rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
        rect_center_y = rect.position_mm[1] + (rect_height / 2.0)
        layer_y_positions.append(rect_center_y)

    # Center position of the entire stackup
    min_y = min(layer_y_positions)
    max_y = max(layer_y_positions)
    center_y = (min_y + max_y) / 2.0

    # Calculate absolute positions with consistent spacing
    center_idx = total_groups // 2
    spacing_unit = config.min_callout_spacing_mm

    for i in range(total_groups):
        # Calculate displacement from center
        if i == center_idx:
            displacement = 0.0
        elif i < center_idx:
            units_from_center = center_idx - i
            displacement = -units_from_center * spacing_unit
        else:
            units_from_center = i - center_idx
            displacement = units_from_center * spacing_unit

        # Calculate absolute Y position (independent of individual layer positions)
        callout_y = center_y + displacement
        positions.append(callout_y)

    return positions


def _calculate_required_leader_length(
    vertical_displacement: float,
    base_leader_length: float,
    min_elbow_height: float,
    min_final_segment: float = MIN_FINAL_SEGMENT_MM
) -> float:
    """
    Calculate the leader line length required for a callout with given vertical displacement.

    For straight lines (displacement < min_elbow_height), returns base length.
    For elbow lines, calculates total length needed for:
      - Initial horizontal segment (40% of base)
      - 45° diagonal segment (length = vertical displacement)
      - Comfortable final horizontal segment (min_final_segment)

    This ensures that all callouts, regardless of their vertical displacement,
    have aligned text endpoints and comfortable horizontal spacing between elbows.

    Args:
        vertical_displacement: Absolute vertical distance from layer center to callout position (mm)
        base_leader_length: Base leader line length from config (20.0mm default)
        min_elbow_height: Minimum vertical displacement to create elbow (0.5mm default)
        min_final_segment: Minimum comfortable horizontal space after elbow (5.0mm default)

    Returns:
        Required leader line length in mm
    """
    if vertical_displacement < min_elbow_height:
        # Straight line - just use base length
        return base_leader_length
    else:
        # Elbow line - need space for all three segments
        # Segment 1: Initial horizontal (40% of base)
        initial_horizontal = base_leader_length * 0.4
        # Segment 2: 45° diagonal (horizontal component = vertical component)
        diagonal = vertical_displacement
        # Segment 3: Final horizontal (comfortable spacing)
        final_horizontal = min_final_segment
        return initial_horizontal + diagonal + final_horizontal


def _determine_leader_direction(
    total_height_mm: float,
    num_callouts: int,
    min_spacing_mm: float,
    leader_length_mm: float,
    layer_width_mm: float
) -> Literal["outward", "inward"]:
    """
    Determines whether leaders should point inward or outward based on available space.

    This algorithm dynamically decides leader direction to ensure professional appearance
    across all scales:
    - Outward: Leaders extend away from the cross-section (current default behavior)
    - Inward: Leaders point toward the center (for dense or large visualizations)

    Args:
        total_height_mm: Total height of the cross-section visualization
        num_callouts: Number of callouts to be placed
        min_spacing_mm: Minimum spacing between callouts
        leader_length_mm: Base leader line length
        layer_width_mm: Width of the cross-section layers

    Returns:
        "outward" if leaders should point away from center, "inward" if toward center

    Decision logic:
        1. Calculate required vertical space for callouts: (num_callouts - 1) * min_spacing_mm
        2. If callout column height > 120% of visualization height: point inward
           (prevents callouts from extending far beyond the visualization bounds)
        3. If leader length > 50% of layer width: point inward
           (prevents leaders from being disproportionately long)
        4. Otherwise: point outward (default, most readable for typical cases)

    Examples:
        - 50mm scale, 8 layers: callout height = 7 * 8.8 = 61.6mm > 50 * 1.2 = 60mm → inward
        - 200mm scale, 8 layers: callout height = 61.6mm < 200 * 1.2 = 240mm → outward
        - 100mm scale, 4 layers, 25mm leader, 40mm width: 25 > 40*0.5 = 20 → inward
    """
    # Edge case: single callout or no callouts
    if num_callouts <= 1:
        return "outward"  # Default for simple cases

    # Calculate required vertical space for callout column
    # (Using n-1 because spacing is between callouts, not including endpoints)
    required_callout_height_mm = (num_callouts - 1) * min_spacing_mm

    # Criterion 1: Check if callouts would extend too far beyond visualization
    # Use 1.2x threshold to allow some reasonable overflow
    max_allowed_height = total_height_mm * 1.2
    if required_callout_height_mm > max_allowed_height:
        return "inward"

    # Criterion 2: Check if leaders are disproportionately long relative to width
    # Use 0.5x threshold (50% of width)
    max_allowed_leader_length = layer_width_mm * 0.5
    if leader_length_mm > max_allowed_leader_length:
        return "inward"

    # Default: point outward (most common and readable)
    return "outward"


def adjust_leader_lines(
    visualization: StackupVisualization,
    config: GraphicalStackupConfig
) -> StackupVisualization:
    """
    Adjust leader lines to prevent callout collisions and create aligned text column.

    This function:
    1. Calculates maximum required leader length based on all callout vertical
       displacements to ensure aligned text column
    2. Detects collisions between callouts (spacing < min_callout_spacing_mm)
    3. Groups colliding callouts by proximity
    4. Redistributes callouts symmetrically around center with minimum spacing
    5. Recreates leader lines with adjusted positions (straight or 45° elbow)

    The leader length calculation ensures all callout text aligns at the same
    X position, creating a professional appearance and preventing horizontal
    crowding of elbow endpoints.

    Strategy: When callouts are too close together, use angled leader lines
    to spread them out vertically. Top half angles up, bottom half angles down.

    Args:
        visualization: Current visualization with straight leaders
        config: Configuration with spacing parameters

    Returns:
        Updated visualization with adjusted leader lines
    """
    if not visualization.elements:
        return visualization

    # Determine leader direction based on config or dynamic detection
    num_layers = visualization.layer_count
    if config.leader_direction == "auto":
        # Dynamic detection based on available space
        leader_direction = _determine_leader_direction(
            total_height_mm=visualization.total_height_mm,
            num_callouts=num_layers,
            min_spacing_mm=config.min_callout_spacing_mm,
            leader_length_mm=config.leader_line_length_mm,
            layer_width_mm=config.layer_width_mm
        )
    elif config.leader_direction in ("outward", "inward"):
        # User-specified direction
        leader_direction = config.leader_direction
    else:
        # Invalid value - fall back to outward
        leader_direction = "outward"

    # Find all callout/leader groups
    callout_groups: List[Tuple[int, int, int]] = []  # (rect_idx, leader_idx, callout_idx)

    for i in range(0, len(visualization.elements), 3):
        if i + 2 < len(visualization.elements):
            callout_groups.append((i, i + 1, i + 2))

    # PHASE 1: Detect collisions with original straight leaders (for diagnostic purposes)
    collision_indices = detect_callout_collisions(visualization, config)

    # PHASE 2: Always apply symmetric positioning to ensure consistent spacing
    # This ensures callouts are evenly spaced at min_callout_spacing_mm intervals
    # regardless of underlying layer spacing or visualization scale.
    groups_to_adjust = callout_groups

    # Calculate symmetric Y positions for all callouts with consistent spacing
    updated_elements = list(visualization.elements)
    new_callout_positions = _calculate_symmetric_positions(groups_to_adjust, updated_elements, config)

    # PHASE 3: Calculate maximum required leader length based on ADJUSTED positions
    max_required_length = config.leader_line_length_mm  # Start with configured minimum

    for i, (rect_idx, leader_idx, callout_idx) in enumerate(groups_to_adjust):
        rect = updated_elements[rect_idx]
        rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
        rect_center_y = rect.position_mm[1] + (rect_height / 2.0)

        # Use the ADJUSTED Y position (after collision resolution)
        new_callout_y = new_callout_positions[i]
        vertical_displacement = abs(new_callout_y - rect_center_y)

        required_length = _calculate_required_leader_length(
            vertical_displacement,
            config.leader_line_length_mm,
            config.min_elbow_height_mm,
            min_final_segment=MIN_FINAL_SEGMENT_MM
        )
        max_required_length = max(max_required_length, required_length)

    # Create effective config with adjusted leader length for aligned column
    effective_config = replace(config, leader_line_length_mm=max_required_length)

    # PHASE 4: Create leader lines with elbows using the extended length
    # (new_callout_positions already calculated above)

    # Calculate elbow heights (should already be >= MIN_ELBOW_HEIGHT_MM by design)
    elbow_heights = _calculate_elbow_heights(groups_to_adjust, new_callout_positions, updated_elements, effective_config)

    for i, (rect_idx, leader_idx, callout_idx) in enumerate(groups_to_adjust):
        rect = updated_elements[rect_idx]
        rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
        rect_center_y = rect.position_mm[1] + (rect_height / 2.0)

        new_callout_y = new_callout_positions[i]
        elbow_height = elbow_heights[i]

        # Get existing callout for text properties
        callout = updated_elements[callout_idx]

        # Decide: straight or elbow?
        if _should_use_straight_line(elbow_height, effective_config):
            # Create straight line (keep original horizontal leader)
            # Both inward and outward start from right edge and extend right
            leader_start_x = effective_config.origin_x_mm + effective_config.layer_width_mm
            leader_start_y = rect_center_y
            leader_end_x = leader_start_x + effective_config.leader_line_length_mm
            leader_end_y = rect_center_y  # Same Y = straight line
            callout_x = leader_end_x + CALLOUT_TEXT_PADDING_MM

            new_leader = LeaderLine(
                position_mm=(leader_start_x, leader_start_y),
                end_position_mm=(leader_end_x, leader_end_y),
                style=LeaderLineStyle.STRAIGHT,
                segments=[((leader_start_x, leader_start_y), (leader_end_x, leader_end_y))],
            )

            # Callout stays at layer center Y
            updated_callout = CalloutText(
                position_mm=(callout_x, rect_center_y),
                text=callout.text,
                font_size_mm=callout.font_size_mm,
                horizontal_align=callout.horizontal_align,
                vertical_align=callout.vertical_align,
            )
        else:
            # Create elbow line
            # Determine if we need to angle up or down
            if new_callout_y > rect_center_y:
                style = LeaderLineStyle.ANGLED_DOWN
            else:
                style = LeaderLineStyle.ANGLED_UP

            # Both inward and outward start from right edge
            leader_start_x = effective_config.origin_x_mm + effective_config.layer_width_mm
            leader_start_y = rect_center_y

            # Calculate segments: horizontal → 45° angle → horizontal
            # All callouts use the SAME total length (effective_config.leader_line_length_mm)
            # which was calculated as the maximum required across all callouts.
            # This ensures all text endpoints align at the same X position.

            # Use 40% of BASE length for initial segment (consistent with _calculate_required_leader_length)
            vertical_displacement = abs(new_callout_y - rect_center_y)
            horizontal_len = config.leader_line_length_mm * 0.4  # 40% of BASE length, not extended
            angle_len = vertical_displacement  # 45° diagonal (horizontal = vertical)

            # Final segment uses whatever horizontal space remains from the MAXIMUM total length
            # For callouts with small vertical displacement, this will be > MIN_FINAL_SEGMENT_MM
            # For callouts with large vertical displacement, this will be = MIN_FINAL_SEGMENT_MM
            remaining_horizontal = effective_config.leader_line_length_mm - horizontal_len - angle_len

            # Calculate segment positions (direction affects X calculations)
            mid1_x = leader_start_x + horizontal_len
            mid1_y = leader_start_y

            mid2_x = mid1_x + angle_len
            mid2_y = new_callout_y

            end_x = mid2_x + remaining_horizontal
            end_y = new_callout_y

            new_leader = LeaderLine(
                position_mm=(leader_start_x, leader_start_y),
                end_position_mm=(end_x, end_y),
                style=style,
                segments=[
                    ((leader_start_x, leader_start_y), (mid1_x, mid1_y)),  # Horizontal
                    ((mid1_x, mid1_y), (mid2_x, mid2_y)),  # Angled
                    ((mid2_x, mid2_y), (end_x, end_y)),  # Horizontal
                ],
            )

            # Update callout position
            updated_callout = CalloutText(
                position_mm=(end_x + CALLOUT_TEXT_PADDING_MM, end_y),
                text=callout.text,
                font_size_mm=callout.font_size_mm,
                horizontal_align=callout.horizontal_align,
                vertical_align=callout.vertical_align,
            )

        updated_elements[leader_idx] = new_leader
        updated_elements[callout_idx] = updated_callout

    # Return updated visualization
    return StackupVisualization(
        elements=updated_elements,
        total_width_mm=visualization.total_width_mm,
        total_height_mm=visualization.total_height_mm,
        layer_count=visualization.layer_count,
        bounds_mm=visualization.bounds_mm,
    )
