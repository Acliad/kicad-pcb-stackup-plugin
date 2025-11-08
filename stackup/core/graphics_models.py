"""
Data models for graphical stackup visualization.
Pure Python classes with no KiCad dependencies.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


# Proportional thickness mode ratios (relative to base unit)
# Copper is always the baseline at 1.0
COPPER_HEIGHT_RATIO = 1.0
DIELECTRIC_HEIGHT_RATIO = 1.55  # 1.55x copper thickness
SOLDERMASK_HEIGHT_RATIO = 0.5   # Thin soldermask layer

# Default base height (in mm) - scaled to give copper layers a reasonable visual size
# With 3.0mm base: Copper=3.0mm, Dielectric=4.65mm, Soldermask=1.5mm
DEFAULT_BASE_HEIGHT_MM = 3.0

# Text label padding from leader line endpoint (in mm)
CALLOUT_TEXT_PADDING_MM = 1.0

# Minimum vertical spacing between callout text labels (in mm)
MIN_CALLOUT_SPACING_MM = 2.0  # Compact spacing for professional appearance

# Minimum vertical displacement for elbows (smaller = straight line)
MIN_ELBOW_HEIGHT_MM = 0.5  # Elbows with less than 0.5mm vertical displacement become straight lines


class LeaderLineStyle(Enum):
    """Style of leader line connecting layer to callout"""
    STRAIGHT = "straight"  # Horizontal line only
    ANGLED_UP = "angled_up"  # Horizontal → 45° up → horizontal
    ANGLED_DOWN = "angled_down"  # Horizontal → 45° down → horizontal


class ThicknessMode(Enum):
    """Mode for calculating layer heights in visualization"""
    UNIFORM = "uniform"  # All layers same height (legacy behavior)
    PROPORTIONAL = "proportional"  # Fixed ratios: copper=1.0, dielectric=2.0, soldermask=0.3
    SCALED = "scaled"  # Use actual thickness ratios from stackup data


@dataclass
class GraphicalElement:
    """Base class for all graphical elements in the visualization"""
    position_mm: Tuple[float, float]  # (x, y) in mm


@dataclass
class LayerRectangle(GraphicalElement):
    """Rectangle representing a single layer in the stackup"""
    width_mm: float
    height_mm: float
    layer_name: str
    layer_type: Optional[str] = None  # LayerType name for visual styling
    fill: bool = False
    element_type: str = "rectangle"


@dataclass
class LeaderLine(GraphicalElement):
    """Leader line connecting a layer to its callout text"""
    end_position_mm: Tuple[float, float]  # End point of leader
    style: LeaderLineStyle = LeaderLineStyle.STRAIGHT
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = field(default_factory=list)
    element_type: str = "leader_line"
    # Each segment is ((x1, y1), (x2, y2)) in mm


@dataclass
class CalloutText(GraphicalElement):
    """Text callout with layer information"""
    text: str = ""
    font_size_mm: float = 0.5
    horizontal_align: str = "left"  # "left", "center", "right"
    vertical_align: str = "center"  # "top", "center", "bottom"
    element_type: str = "text"


@dataclass
class StackupVisualization:
    """Complete graphical stackup layout with all elements"""
    elements: List[GraphicalElement]
    total_width_mm: float
    total_height_mm: float
    layer_count: int
    bounds_mm: Tuple[float, float, float, float] = field(default=(0.0, 0.0, 0.0, 0.0))
    # bounds_mm = (x, y, width, height)

    def __post_init__(self):
        # Calculate bounds if not provided
        if self.bounds_mm == (0.0, 0.0, 0.0, 0.0):
            self.bounds_mm = (0.0, 0.0, self.total_width_mm, self.total_height_mm)


@dataclass
class GraphicalStackupConfig:
    """Configuration for graphical stackup rendering"""
    # Overall scaling
    scale_mm: Optional[float] = None  # Desired total height of cross-section in mm. If None, uses default dimensions. All dimensions scale proportionally to achieve this height while maintaining aspect ratio.

    # Layer sizing
    thickness_mode: ThicknessMode = ThicknessMode.PROPORTIONAL  # How to calculate layer heights
    uniform_layer_height_mm: float = DEFAULT_BASE_HEIGHT_MM  # Base height (uniform mode or proportional base)
    layer_width_mm: float = 50.0  # Width of the layer stack visualization
    max_total_height_mm: float = 100.0  # Max height for scaled mode (will compress if needed)

    # Proportional mode thickness ratios (relative to base unit)
    # Copper is always 1.0 (baseline), adjust base height instead
    copper_height_ratio: float = COPPER_HEIGHT_RATIO
    dielectric_height_ratio: float = DIELECTRIC_HEIGHT_RATIO
    soldermask_height_ratio: float = SOLDERMASK_HEIGHT_RATIO

    # Visual spacing
    soldermask_gap_mm: float = 1.0  # Gap above/below soldermask layers

    # Copper hatching
    copper_hatch_enabled: bool = True  # Draw 45° hatch lines on copper layers
    copper_hatch_spacing_mm: float = 1.0  # Distance between hatch lines
    copper_hatch_angle_deg: float = 45.0  # Angle of hatch lines

    # Leader lines
    leader_line_length_mm: float = 20.0  # Length of horizontal leader segment
    leader_line_width_mm: float = 0.15  # Line thickness
    leader_direction: str = "auto"  # Direction for leader lines: "auto" (dynamic), "outward", or "inward"

    # Callout text
    callout_format: str = "{material} - {thickness} ±{tolerance}"
    text_size_mm: float = 1.5  # Text height (increased from 0.5mm for visibility)
    min_callout_spacing_mm: float = MIN_CALLOUT_SPACING_MM  # Minimum vertical spacing between callouts
    min_elbow_height_mm: float = MIN_ELBOW_HEIGHT_MM  # Minimum elbow height threshold (smaller = straight line)

    # Positioning
    origin_x_mm: float = 50.0  # X position to place the visualization
    origin_y_mm: float = 50.0  # Y position to place the visualization

    # Target layer for drawing
    target_layer: str = "Dwgs.User"  # KiCad layer name
