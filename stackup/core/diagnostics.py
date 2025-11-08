"""
Diagnostic utilities for debugging graphical layout spacing issues.
Captures detailed information about spacing calculations and collisions.
"""
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class SpacingDiagnostic:
    """Captures diagnostic information about spacing calculations."""
    scale_mm: float
    layer_count: int
    config_min_callout_spacing: float
    config_min_elbow_height: float
    config_text_size: float
    spacing_unit_used: float
    expected_spacing_unit: float
    calculated_positions: List[float]
    actual_spacings: List[float]
    violations: List[Dict[str, Any]]
    collision_indices: List[int]

    def has_spacing_violations(self) -> bool:
        """Check if spacing violates minimum callout spacing."""
        return len(self.violations) > 0

    def summary(self) -> str:
        """Return a human-readable summary of the diagnostic."""
        lines = [
            f"=== Spacing Diagnostic (Scale: {self.scale_mm}mm) ===",
            f"Layers: {self.layer_count}",
            f"Config min_callout_spacing_mm: {self.config_min_callout_spacing:.2f}mm",
            f"Config min_elbow_height_mm: {self.config_min_elbow_height:.2f}mm",
            f"Config text_size_mm: {self.config_text_size:.2f}mm",
            f"",
            f"Spacing Algorithm:",
            f"  spacing_unit_used: {self.spacing_unit_used:.2f}mm",
            f"  expected_spacing_unit: {self.expected_spacing_unit:.2f}mm",
            f"  MISMATCH: {self.spacing_unit_used != self.expected_spacing_unit}",
            f"",
            f"Calculated Positions: {[f'{y:.2f}' for y in self.calculated_positions]}",
            f"",
            f"Actual Spacings Between Callouts:",
        ]

        for i, spacing in enumerate(self.actual_spacings):
            min_allowed = self.config_min_callout_spacing
            violation = "❌ VIOLATION" if spacing < min_allowed else "✓ OK"
            lines.append(f"  Layer {i}→{i+1}: {spacing:.2f}mm {violation}")

        lines.extend([
            f"",
            f"Collisions Detected: {len(self.collision_indices)} layers",
            f"  Indices: {self.collision_indices}",
            f"",
            f"Total Violations: {len(self.violations)}",
        ])

        if self.violations:
            lines.append("  Violations:")
            for v in self.violations:
                lines.append(
                    f"    Layer {v['layer1']}→{v['layer2']}: "
                    f"{v['spacing']:.2f}mm < {v['min_allowed']:.2f}mm"
                )

        return "\n".join(lines)


def capture_spacing_diagnostic(
    scale_mm: float,
    layer_count: int,
    config_min_callout_spacing: float,
    config_min_elbow_height: float,
    config_text_size: float,
    calculated_positions: List[float],
    collision_indices: List[int],
) -> SpacingDiagnostic:
    """
    Capture diagnostic information about spacing calculations.

    Args:
        scale_mm: Scale value being used
        layer_count: Number of layers in stackup
        config_min_callout_spacing: Config min_callout_spacing_mm value
        config_min_elbow_height: Config min_elbow_height_mm value
        config_text_size: Config text_size_mm value
        calculated_positions: Y positions calculated for callouts
        collision_indices: Indices of colliding layers

    Returns:
        SpacingDiagnostic with captured information
    """
    # Calculate actual spacings between consecutive callouts
    actual_spacings = []
    for i in range(len(calculated_positions) - 1):
        spacing = abs(calculated_positions[i + 1] - calculated_positions[i])
        actual_spacings.append(spacing)

    # Identify violations
    violations = []
    for i, spacing in enumerate(actual_spacings):
        if spacing < config_min_callout_spacing:
            violations.append({
                "layer1": i,
                "layer2": i + 1,
                "spacing": spacing,
                "min_allowed": config_min_callout_spacing,
            })

    # Expected spacing unit should be min_callout_spacing (the fix)
    expected_spacing_unit = config_min_callout_spacing

    # Current spacing unit is min_elbow_height (the bug)
    spacing_unit_used = config_min_elbow_height

    return SpacingDiagnostic(
        scale_mm=scale_mm,
        layer_count=layer_count,
        config_min_callout_spacing=config_min_callout_spacing,
        config_min_elbow_height=config_min_elbow_height,
        config_text_size=config_text_size,
        spacing_unit_used=spacing_unit_used,
        expected_spacing_unit=expected_spacing_unit,
        calculated_positions=calculated_positions,
        actual_spacings=actual_spacings,
        violations=violations,
        collision_indices=collision_indices,
    )
