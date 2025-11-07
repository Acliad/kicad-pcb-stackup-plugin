"""
Layout algorithms for graphical stackup visualization.
Pure functions - no KiCad dependencies, fully testable.
"""
from typing import List, Tuple, Dict
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


def calculate_graphical_layout(
    stackup: StackupData,
    config: GraphicalStackupConfig
) -> StackupVisualization:
    """
    Calculate graphical cross-section layout with configurable layer heights.

    Creates:
    - Rectangles for each layer (heights based on thickness mode)
    - Straight horizontal leader lines (initially)
    - Text callouts with layer info
    - Optional spacing for soldermask layers

    Collision detection and leader line adjustment happen in a separate pass.

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

        # Add gap before soldermask layers
        if layer.layer_type == LayerType.SOLDERMASK and config.soldermask_gap_mm > 0:
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

    # Calculate total dimensions
    total_width = config.origin_x_mm + config.layer_width_mm + config.leader_line_length_mm + 50.0  # 50mm for text
    total_height = y_offset - config.origin_y_mm

    visualization = StackupVisualization(
        elements=elements,
        total_width_mm=total_width,
        total_height_mm=total_height,
        layer_count=len(stackup.layers),
    )

    return visualization


def detect_callout_collisions(visualization: StackupVisualization) -> List[int]:
    """
    Detect which callout text elements would collide vertically.

    Args:
        visualization: Current stackup visualization

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
        if vertical_gap < MIN_CALLOUT_SPACING_MM:
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
    Calculate symmetric callout positions from center layer.

    Strategy:
    - Find center index (total_groups // 2)
    - Center layer gets 0 displacement (straight line)
    - Layers above center: +1, +2, +3... units * spacing
    - Layers below center: -1, -2, -3... units * spacing
    - Spacing = MIN_ELBOW_HEIGHT_MM (0.5mm default) for consistent, symmetric appearance

    This creates visually balanced leader lines with the center layer always straight
    and matching elbows above/below center.

    Args:
        groups_to_adjust: List of (rect_idx, leader_idx, callout_idx) tuples
        elements: Current visualization elements
        config: Configuration with min_elbow_height_mm threshold

    Returns:
        List of Y positions for callouts (symmetric about center)
    """
    total_groups = len(groups_to_adjust)
    positions = []

    # Find center index
    center_idx = total_groups // 2

    # Calculate base spacing unit (ensure >= MIN_ELBOW_HEIGHT_MM)
    spacing_unit = config.min_elbow_height_mm

    # Calculate positions relative to each layer's center
    for i, (rect_idx, _, _) in enumerate(groups_to_adjust):
        rect = elements[rect_idx]
        rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
        rect_center_y = rect.position_mm[1] + (rect_height / 2.0)

        # Calculate displacement from center
        if i == center_idx:
            # Center layer: 0 displacement (straight line)
            displacement = 0.0
        elif i < center_idx:
            # Above center: negative displacement (callout goes up)
            units_from_center = center_idx - i
            displacement = -units_from_center * spacing_unit  # Negative = up
        else:
            # Below center: positive displacement (callout goes down)
            units_from_center = i - center_idx
            displacement = units_from_center * spacing_unit  # Positive = down

        # Calculate absolute Y position
        callout_y = rect_center_y + displacement
        positions.append(callout_y)

    return positions


def adjust_leader_lines(
    visualization: StackupVisualization,
    config: GraphicalStackupConfig
) -> StackupVisualization:
    """
    Adjust leader lines to prevent callout collisions.

    Strategy: When callouts are too close together, use angled leader lines
    to spread them out vertically. Top half angles up, bottom half angles down.

    Args:
        visualization: Current visualization with straight leaders
        config: Configuration with spacing parameters

    Returns:
        Updated visualization with adjusted leader lines
    """
    # Detect collisions
    collision_indices = detect_callout_collisions(visualization)

    if not collision_indices:
        return visualization  # No collisions, return as-is

    # Find all callout/leader groups
    callout_groups: List[Tuple[int, int, int]] = []  # (rect_idx, leader_idx, callout_idx)

    for i in range(0, len(visualization.elements), 3):
        if i + 2 < len(visualization.elements):
            callout_groups.append((i, i + 1, i + 2))

    # Determine which groups need adjustment
    groups_to_adjust = [
        group for group in callout_groups
        if group[2] in collision_indices  # If callout index is in collision list
    ]

    if not groups_to_adjust:
        return visualization

    # Update leader lines and callouts
    updated_elements = list(visualization.elements)

    # Calculate symmetric callout positions from center layer
    # This creates balanced, professional appearance with center layer straight
    new_callout_positions = _calculate_symmetric_positions(groups_to_adjust, updated_elements, config)

    # Calculate elbow heights (should already be >= MIN_ELBOW_HEIGHT_MM by design)
    elbow_heights = _calculate_elbow_heights(groups_to_adjust, new_callout_positions, updated_elements, config)

    for i, (rect_idx, leader_idx, callout_idx) in enumerate(groups_to_adjust):
        rect = updated_elements[rect_idx]
        rect_height = rect.height_mm if isinstance(rect, LayerRectangle) else config.uniform_layer_height_mm
        rect_center_y = rect.position_mm[1] + (rect_height / 2.0)

        new_callout_y = new_callout_positions[i]
        elbow_height = elbow_heights[i]

        # Get existing callout for text properties
        callout = updated_elements[callout_idx]

        # Decide: straight or elbow?
        if _should_use_straight_line(elbow_height, config):
            # Create straight line (keep original horizontal leader)
            leader_start_x = config.origin_x_mm + config.layer_width_mm
            leader_start_y = rect_center_y
            leader_end_x = leader_start_x + config.leader_line_length_mm
            leader_end_y = rect_center_y  # Same Y = straight line

            new_leader = LeaderLine(
                position_mm=(leader_start_x, leader_start_y),
                end_position_mm=(leader_end_x, leader_end_y),
                style=LeaderLineStyle.STRAIGHT,
                segments=[((leader_start_x, leader_start_y), (leader_end_x, leader_end_y))],
            )

            # Callout stays at layer center Y
            updated_callout = CalloutText(
                position_mm=(leader_end_x + CALLOUT_TEXT_PADDING_MM, rect_center_y),
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

            # Create angled leader line
            leader_start_x = config.origin_x_mm + config.layer_width_mm
            leader_start_y = rect_center_y

            # Calculate segments: horizontal → 45° angle → horizontal
            horizontal_len = config.leader_line_length_mm * 0.4  # 40% horizontal at start
            angle_len = abs(new_callout_y - rect_center_y)  # Vertical distance
            remaining_horizontal = config.leader_line_length_mm - horizontal_len - angle_len

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
