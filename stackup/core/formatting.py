"""
Text formatting and unit conversion utilities.
Pure functions - easily testable.
"""


def format_thickness(thickness_mm: float, precision: int = 3, unit: str = "mm") -> str:
    """
    Format thickness with appropriate units.

    Args:
        thickness_mm: Thickness in millimeters
        precision: Number of decimal places
        unit: Output unit ("mm" or "mils")

    Returns:
        Formatted string with units
    """
    if unit == "mils":
        mils = mm_to_mils(thickness_mm)
        return f"{mils:.{precision}f}mil"

    # Auto-select µm for small values
    if thickness_mm < 1.0:
        return f"{thickness_mm * 1000:.{precision}f}µm"
    else:
        return f"{thickness_mm:.{precision}f}mm"


def format_epsilon(epsilon_r: float) -> str:
    """
    Format dielectric constant.

    Args:
        epsilon_r: Relative permittivity

    Returns:
        Formatted string
    """
    return f"{epsilon_r:.2f}"


def format_loss_tangent(loss_tangent: float) -> str:
    """
    Format loss tangent.

    Args:
        loss_tangent: Loss tangent value

    Returns:
        Formatted string
    """
    return f"{loss_tangent:.4f}"


def truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text with ellipsis if too long.

    Args:
        text: Input text
        max_length: Maximum length

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-1] + "…"


def mils_to_mm(mils: float) -> float:
    """
    Convert mils (thousandths of an inch) to millimeters.

    Args:
        mils: Value in mils

    Returns:
        Value in millimeters
    """
    return mils * 0.0254


def mm_to_mils(mm: float) -> float:
    """
    Convert millimeters to mils.

    Args:
        mm: Value in millimeters

    Returns:
        Value in mils
    """
    return mm / 0.0254


def oz_to_mm(oz: float) -> float:
    """
    Convert copper weight (oz/ft²) to thickness (mm).

    Args:
        oz: Copper weight in oz/ft²

    Returns:
        Thickness in millimeters

    Note:
        1 oz/ft² ≈ 35µm ≈ 0.035mm
        2 oz/ft² ≈ 70µm ≈ 0.070mm
    """
    return oz * 0.035


def mm_to_oz(mm: float) -> float:
    """
    Convert copper thickness (mm) to weight (oz/ft²).

    Args:
        mm: Thickness in millimeters

    Returns:
        Weight in oz/ft²
    """
    return mm / 0.035


def format_layer_name(name: str, max_length: int = 20) -> str:
    """
    Format layer name for display in table.

    Args:
        name: Raw layer name
        max_length: Maximum length

    Returns:
        Formatted layer name
    """
    # Remove common prefixes
    name = name.replace("layer_", "").replace("Layer", "")

    # Truncate if needed
    return truncate_text(name, max_length)
