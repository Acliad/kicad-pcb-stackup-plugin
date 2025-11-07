"""
Pure data models for stackup representation.
No KiCad imports - fully testable with mock data.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class LayerType(Enum):
    """Type of layer in PCB stackup"""
    COPPER = "copper"
    DIELECTRIC = "dielectric"
    SOLDERMASK = "soldermask"
    SILKSCREEN = "silkscreen"
    SOLDERPASTE = "solderpaste"


class VisualizationMode(Enum):
    """Mode for stackup visualization output"""
    TABLE = "table"  # Traditional table format
    GRAPHICAL = "graphical"  # Cross-section with leader callouts
    BOTH = "both"  # Generate both table and graphical visualization


@dataclass
class StackupLayer:
    """Generic stackup layer - not tied to KiCad types"""
    name: str
    layer_type: LayerType
    thickness: float  # in mm
    material: str
    color: Optional[str] = None
    epsilon_r: Optional[float] = None  # dielectric constant
    loss_tangent: Optional[float] = None


@dataclass
class StackupData:
    """Complete stackup information"""
    layers: List[StackupLayer]
    total_thickness: float
    copper_layer_count: int
    board_name: str


@dataclass
class TableCell:
    """Represents a single cell in the table"""
    text: str
    row: int
    col: int
    width: float  # in mm
    height: float  # in mm
    align: str = "left"  # "left", "center", "right"
    is_header: bool = False


@dataclass
class TableLayout:
    """Complete table layout with positioning"""
    cells: List[TableCell]
    total_width: float  # in mm
    total_height: float  # in mm
    columns: List[str] = field(default_factory=list)  # Column headers
    row_height: float = 5.0  # in mm
    cell_padding: float = 1.0  # in mm


@dataclass
class TableConfig:
    """Configuration for table generation"""
    style: str = "detailed"  # "detailed", "compact", "minimal"
    units: str = "mm"  # "mm", "mils"
    show_epsilon: bool = True
    show_loss_tangent: bool = False
    show_material: bool = True
    show_color: bool = False
    font_size: float = 3.0  # in mm
    line_width: float = 0.15  # in mm for grid lines
    row_height: float = 5.0  # in mm
    cell_padding: float = 1.0  # in mm
