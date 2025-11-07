"""
Extract stackup data from KiCad Board.
This is the adapter layer - converts KiCad types to our models.
"""
from typing import TYPE_CHECKING

from ..core.models import StackupData, StackupLayer, LayerType

if TYPE_CHECKING:
    from kipy.board import Board, BoardStackup
    from kipy.board_types import BoardLayer

try:
    from kipy.board import Board
    from kipy.board_types import BoardLayer
    KICAD_AVAILABLE = True
except ImportError:
    KICAD_AVAILABLE = False
    Board = None  # type: ignore
    BoardLayer = None  # type: ignore


def extract_stackup_data(board: 'Board') -> StackupData:
    """
    Extract stackup information from KiCad board.

    Args:
        board: KiCad Board instance

    Returns:
        StackupData model (KiCad-agnostic)

    Raises:
        RuntimeError: If stackup data cannot be extracted
    """
    try:
        kicad_stackup = board.get_stackup()
    except Exception as e:
        raise RuntimeError(f"Cannot get stackup from board: {e}")

    layers = []
    total_thickness = 0.0
    copper_count = 0

    for kicad_layer in kicad_stackup.layers:
        # Convert KiCad layer to our model
        layer = _convert_layer(kicad_layer)

        # Filter out silkscreen and solderpaste layers by default
        # These are cosmetic layers that don't affect stackup structure
        if layer.layer_type in [LayerType.SILKSCREEN, LayerType.SOLDERPASTE]:
            continue

        layers.append(layer)

        if layer.layer_type == LayerType.COPPER:
            copper_count += 1

        total_thickness += layer.thickness

    # Get board name
    try:
        board_name = board.document.board_filename or "Unknown"
    except Exception:
        board_name = "Unknown"

    return StackupData(
        layers=layers,
        total_thickness=total_thickness,
        copper_layer_count=copper_count,
        board_name=board_name
    )


def _convert_layer(kicad_layer) -> StackupLayer:
    """
    Convert KiCad layer to our model.

    Args:
        kicad_layer: KiCad stackup layer object

    Returns:
        StackupLayer model
    """
    # Determine layer type based on layer ID or properties
    layer_type = _determine_layer_type(kicad_layer)

    # Get layer name
    try:
        name = kicad_layer.name or f"Layer {kicad_layer.layer}"
    except Exception:
        name = "Unknown"

    # Get thickness (KiCad stores in nanometers)
    try:
        thickness_nm = kicad_layer.thickness
        thickness_mm = thickness_nm / 1_000_000.0
    except Exception:
        thickness_mm = 0.0

    # Get material based on layer type
    # For copper, soldermask, silkscreen, solderpaste: always use default labels
    # For dielectric: look up material from KiCad stackup manager
    if layer_type == LayerType.COPPER:
        material = "COPPER"
    elif layer_type == LayerType.SOLDERMASK:
        material = "SOLDERMASK"
    elif layer_type == LayerType.SILKSCREEN:
        material = "SILKSCREEN"
    elif layer_type == LayerType.SOLDERPASTE:
        material = "SOLDERPASTE"
    elif layer_type == LayerType.DIELECTRIC:
        # Try to get material name from KiCad for dielectric layers
        # NOTE: As of KiCad 9.0.4, the IPC API does not expose dielectric material
        # properties even though they are stored in the .kicad_pcb file.
        material = None
        try:
            # Check if top-level material_name is populated
            if kicad_layer.material_name and kicad_layer.material_name.strip():
                material = kicad_layer.material_name.strip()

            # Check dielectric sublayers (where material info should be)
            if not material and hasattr(kicad_layer, 'dielectric') and kicad_layer.dielectric:
                dielectric_layers = kicad_layer.dielectric.layers
                if dielectric_layers and len(dielectric_layers) > 0:
                    # Get material from first non-empty sublayer
                    for sublayer in dielectric_layers:
                        if sublayer.material_name and sublayer.material_name.strip():
                            material = sublayer.material_name.strip()
                            break

            # Fallback to default if still empty
            if not material:
                material = "DIELECTRIC"

        except Exception:
            material = "DIELECTRIC"
    else:
        material = "Unknown"

    # Get color (optional)
    try:
        color = kicad_layer.color if hasattr(kicad_layer, 'color') else None
    except Exception:
        color = None

    # Get epsilon_r (dielectric constant, optional)
    try:
        epsilon_r = kicad_layer.epsilon_r if hasattr(kicad_layer, 'epsilon_r') else None
    except Exception:
        epsilon_r = None

    # Get loss_tangent (optional)
    try:
        loss_tangent = kicad_layer.loss_tangent if hasattr(kicad_layer, 'loss_tangent') else None
    except Exception:
        loss_tangent = None

    return StackupLayer(
        name=name,
        layer_type=layer_type,
        thickness=thickness_mm,
        material=material,
        color=color,
        epsilon_r=epsilon_r,
        loss_tangent=loss_tangent
    )


def _determine_layer_type(kicad_layer) -> LayerType:
    """
    Determine layer type from KiCad layer.

    Args:
        kicad_layer: KiCad stackup layer object

    Returns:
        LayerType enum
    """
    if not KICAD_AVAILABLE:
        return LayerType.DIELECTRIC

    try:
        # Try using the proper API type enum first
        from kipy.proto.board.board_pb2 import BoardStackupLayerType as BSLT

        layer_type = kicad_layer.type
        if layer_type == BSLT.BSLT_COPPER:
            return LayerType.COPPER
        elif layer_type == BSLT.BSLT_SOLDERMASK:
            return LayerType.SOLDERMASK
        elif layer_type == BSLT.BSLT_SILKSCREEN:
            return LayerType.SILKSCREEN
        elif layer_type == BSLT.BSLT_SOLDERPASTE:
            return LayerType.SOLDERPASTE
        elif layer_type == BSLT.BSLT_DIELECTRIC:
            return LayerType.DIELECTRIC

        # Fallback to heuristics if type is unknown/undefined
        # Check if it's a copper layer based on layer ID
        # BoardLayer.BL_F_Cu = 0, BoardLayer.BL_B_Cu = 31
        # Inner layers are 1-30
        layer_id = kicad_layer.layer
        if layer_id <= BoardLayer.BL_B_Cu and layer_id >= BoardLayer.BL_F_Cu:
            # Check if it's actually a copper layer or a dielectric
            # Copper layers typically have "Cu" in the name
            name = getattr(kicad_layer, 'name', '')
            if 'Cu' in name or 'copper' in name.lower():
                return LayerType.COPPER

        # Check material name for clues
        material = getattr(kicad_layer, 'material_name', '').lower()
        if 'copper' in material or 'cu' == material:
            return LayerType.COPPER
        elif 'fr4' in material or 'prepreg' in material or 'core' in material:
            return LayerType.DIELECTRIC
        elif 'soldermask' in material or 'mask' in material:
            return LayerType.SOLDERMASK
        elif 'silk' in material:
            return LayerType.SILKSCREEN

        # Default to dielectric for unknown
        return LayerType.DIELECTRIC

    except Exception:
        return LayerType.DIELECTRIC


def _get_default_material(kicad_layer) -> str:
    """
    Get default material name based on layer type.

    Note: Copper and soldermask always return fixed labels.
    Only dielectric layers look up material from KiCad stackup manager.

    Args:
        kicad_layer: KiCad stackup layer object

    Returns:
        Default material name string
    """
    if not KICAD_AVAILABLE:
        return "Unknown"

    try:
        from kipy.proto.board.board_pb2 import BoardStackupLayerType as BSLT

        layer_type = kicad_layer.type

        if layer_type == BSLT.BSLT_COPPER:
            return "COPPER"
        elif layer_type == BSLT.BSLT_SOLDERMASK:
            return "SOLDERMASK"
        elif layer_type == BSLT.BSLT_SILKSCREEN:
            return "SILKSCREEN"
        elif layer_type == BSLT.BSLT_SOLDERPASTE:
            return "SOLDERPASTE"
        elif layer_type == BSLT.BSLT_DIELECTRIC:
            # For dielectric: try to get material from KiCad, fallback to "DIELECTRIC"
            # Check main layer material_name
            material = getattr(kicad_layer, 'material_name', '')
            if material:
                return material
            # Check if dielectric has material_name in sublayers
            if hasattr(kicad_layer, 'dielectric') and kicad_layer.dielectric.layers:
                for sublayer in kicad_layer.dielectric.layers:
                    if sublayer.material_name:
                        return sublayer.material_name
            return "DIELECTRIC"
        else:
            return "Unknown"
    except Exception:
        return "Unknown"
