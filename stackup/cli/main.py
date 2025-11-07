"""
Command-line interface for stackup generator.
Provides advanced options for standalone execution.
"""
import argparse
import json
import sys
from typing import Optional

from ..kicad_adapter.connection import connect_to_kicad, check_kicad_available
from ..kicad_adapter.extractor import extract_stackup_data
from ..core.models import TableConfig, VisualizationMode
from ..core.layout import calculate_table_layout
from ..core.graphics_models import (
    GraphicalStackupConfig, ThicknessMode, DEFAULT_BASE_HEIGHT_MM
)
from ..core.graphics_layout import calculate_graphical_layout, adjust_leader_lines
from ..kicad_adapter.renderer import render_table_to_board, render_table_to_svg
from ..kicad_adapter.graphics_renderer import render_graphical_stackup, render_graphical_stackup_to_svg


def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser for CLI.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="stackup-generator",
        description="Generate stackup visualization on KiCad PCB",
        epilog="Requires KiCad running with API server enabled"
    )

    parser.add_argument(
        "--visualization",
        choices=["table", "graphical", "both"],
        default="graphical",
        help="Visualization type (default: graphical)"
    )

    parser.add_argument(
        "--style",
        choices=["detailed", "compact", "minimal"],
        default="detailed",
        help="Table style for 'table' mode (default: detailed)"
    )

    parser.add_argument(
        "--units",
        choices=["mm", "mils"],
        default="mm",
        help="Units for thickness display (default: mm)"
    )

    parser.add_argument(
        "--layer",
        default="Dwgs.User",
        help="Target layer for table (default: Dwgs.User)"
    )

    parser.add_argument(
        "--font-size",
        type=float,
        default=2.5,
        help="Font size in mm (default: 2.5)"
    )

    parser.add_argument(
        "--line-width",
        type=float,
        default=0.15,
        help="Grid line width in mm (default: 0.15)"
    )

    # Column visibility options
    parser.add_argument(
        "--no-epsilon",
        action="store_true",
        help="Hide epsilon_r column"
    )

    parser.add_argument(
        "--show-loss-tangent",
        action="store_true",
        help="Show loss tangent column"
    )

    parser.add_argument(
        "--no-material",
        action="store_true",
        help="Hide material column"
    )

    parser.add_argument(
        "--show-color",
        action="store_true",
        help="Show color column"
    )

    # Graphical visualization options
    parser.add_argument(
        "--thickness-mode",
        choices=["uniform", "proportional", "scaled"],
        default="proportional",
        help="Layer thickness rendering mode (default: proportional). "
             "uniform: all layers same height, "
             "proportional: fixed ratios (copper=1.0x baseline [3.0mm], dielectric=1.55x, soldermask=0.5x), "
             "scaled: use actual thickness ratios from stackup"
    )

    parser.add_argument(
        "--no-copper-hatch",
        action="store_true",
        help="Disable 45° hatch pattern on copper layers"
    )

    parser.add_argument(
        "--soldermask-gap",
        type=float,
        default=1.0,
        help="Gap spacing above/below soldermask layers in mm (default: 1.0)"
    )

    parser.add_argument(
        "--copper-hatch-spacing",
        type=float,
        default=1.0,
        help="Spacing between copper hatch lines in mm (default: 1.0)"
    )

    # Export options
    parser.add_argument(
        "--export-json",
        metavar="FILE",
        help="Export stackup data to JSON file"
    )

    parser.add_argument(
        "--export-svg",
        metavar="FILE",
        help="Export table as SVG file"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and display table info without creating it"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )

    return parser


def export_stackup_json(stackup_data, filename: str) -> None:
    """
    Export stackup data to JSON file.

    Args:
        stackup_data: StackupData model
        filename: Output filename
    """
    def serialize_color(color):
        """Convert Color object to hex string or None"""
        if color is None:
            return None
        try:
            # Color object has red, green, blue, alpha attributes
            r = int(color.red * 255) if hasattr(color, 'red') else 0
            g = int(color.green * 255) if hasattr(color, 'green') else 0
            b = int(color.blue * 255) if hasattr(color, 'blue') else 0
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return None

    data = {
        "board_name": stackup_data.board_name,
        "total_thickness": stackup_data.total_thickness,
        "copper_layer_count": stackup_data.copper_layer_count,
        "layers": [
            {
                "name": layer.name,
                "type": layer.layer_type.value,
                "thickness": layer.thickness,
                "material": layer.material,
                "color": serialize_color(layer.color),
                "epsilon_r": layer.epsilon_r,
                "loss_tangent": layer.loss_tangent
            }
            for layer in stackup_data.layers
        ]
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✓ Exported stackup data to {filename}")


def main(argv: Optional[list] = None):
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (for testing)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Convert visualization arg to enum
    viz_mode_map = {
        "table": VisualizationMode.TABLE,
        "graphical": VisualizationMode.GRAPHICAL,
        "both": VisualizationMode.BOTH,
    }
    viz_mode = viz_mode_map[args.visualization]

    print(f"KiCad Stackup Generator CLI ({args.visualization} mode)")
    print("-" * 40)

    # Check if kicad-python is available
    if not check_kicad_available():
        print("ERROR: kicad-python is not installed.")
        print("Install it with: pip install kicad-python>=0.2.0")
        sys.exit(1)

    try:
        # Connect to KiCad
        print("Connecting to KiCad...")
        kicad, board = connect_to_kicad()
        print("✓ Connected successfully")

        # Extract stackup data
        print("\nExtracting stackup data...")
        stackup_data = extract_stackup_data(board)
        print(f"✓ Found {len(stackup_data.layers)} layers")
        print(f"  - Copper layers: {stackup_data.copper_layer_count}")
        print(f"  - Total thickness: {stackup_data.total_thickness:.3f}mm")

        # Export JSON if requested
        if args.export_json:
            export_stackup_json(stackup_data, args.export_json)
            if not args.export_svg and args.dry_run:
                return  # Exit if only exporting JSON

        # Process based on visualization mode
        footprints_to_place = []
        svg_exports = []

        # TABLE MODE
        if viz_mode in [VisualizationMode.TABLE, VisualizationMode.BOTH]:
            # Configure table
            table_config = TableConfig(
                style=args.style,
                units=args.units,
                show_epsilon=not args.no_epsilon,
                show_loss_tangent=args.show_loss_tangent,
                show_material=not args.no_material,
                show_color=args.show_color,
                font_size=args.font_size,
                line_width=args.line_width
            )

            # Calculate layout
            print("\nCalculating table layout...")
            table_layout = calculate_table_layout(stackup_data, table_config)
            print(f"✓ Table size: {table_layout.total_width:.1f}mm × {table_layout.total_height:.1f}mm")
            print(f"  - Style: {args.style}")
            print(f"  - Cells: {len(table_layout.cells)}")
            print(f"  - Columns: {', '.join(table_layout.columns)}")

            # Export SVG if requested
            if args.export_svg:
                svg_content = render_table_to_svg(table_layout, table_config)
                svg_exports.append(("table", svg_content, args.export_svg))

            # Render to board (unless dry run)
            if not args.dry_run:
                print("\nRendering table to board...")
                table_footprint = render_table_to_board(board, table_layout, table_config)
                print("✓ Table created successfully")
                footprints_to_place.append(("table", table_footprint))

        # GRAPHICAL MODE
        if viz_mode in [VisualizationMode.GRAPHICAL, VisualizationMode.BOTH]:
            # Map thickness mode string to enum
            thickness_mode_map = {
                "uniform": ThicknessMode.UNIFORM,
                "proportional": ThicknessMode.PROPORTIONAL,
                "scaled": ThicknessMode.SCALED,
            }

            # Configure graphical visualization
            graphics_config = GraphicalStackupConfig(
                thickness_mode=thickness_mode_map[args.thickness_mode],
                # uniform_layer_height_mm uses DEFAULT_BASE_HEIGHT_MM by default
                layer_width_mm=50.0,
                soldermask_gap_mm=args.soldermask_gap,
                copper_hatch_enabled=not args.no_copper_hatch,
                copper_hatch_spacing_mm=args.copper_hatch_spacing,
                leader_line_length_mm=20.0,
                leader_line_width_mm=0.15,
                text_size_mm=1.5,
                min_callout_spacing_mm=8.0,
                origin_x_mm=50.0,
                origin_y_mm=50.0,
            )

            # Calculate graphical layout
            print("\nCalculating graphical cross-section layout...")
            graphics_layout = calculate_graphical_layout(stackup_data, graphics_config)
            print(f"✓ Visualization size: {graphics_layout.total_width_mm:.1f}mm × {graphics_layout.total_height_mm:.1f}mm")
            print(f"  - Layer count: {graphics_layout.layer_count}")
            print(f"  - Graphical elements: {len(graphics_layout.elements)}")

            # Adjust leader lines for collision avoidance
            print("\nAdjusting leader lines for optimal spacing...")
            graphics_layout = adjust_leader_lines(graphics_layout, graphics_config)
            print("✓ Leader lines optimized")

            # Export SVG if requested
            if args.export_svg:
                svg_content = render_graphical_stackup_to_svg(graphics_layout, graphics_config)
                # If both modes, modify filename to differentiate
                svg_filename = args.export_svg
                if viz_mode == VisualizationMode.BOTH:
                    svg_filename = svg_filename.replace('.svg', '_graphical.svg')
                svg_exports.append(("graphical", svg_content, svg_filename))

            # Render to board (unless dry run)
            if not args.dry_run:
                print("\nRendering graphical stackup to board...")
                graphics_footprint = render_graphical_stackup(board, graphics_layout, graphics_config)
                print("✓ Graphical stackup created successfully")
                footprints_to_place.append(("graphical", graphics_footprint))

        # Write SVG exports
        for viz_type, svg_content, filename in svg_exports:
            with open(filename, 'w') as f:
                f.write(svg_content)
            print(f"✓ Exported {viz_type} SVG to {filename}")

        # Exit if dry run
        if args.dry_run:
            print("\n✓ Dry run complete (no changes made to board)")
            return

        # Let user place visualizations interactively
        if footprints_to_place:
            print("\n✓ Visualization(s) created! Please place on your board:")
            for viz_type, footprint in footprints_to_place:
                print(f"  - Placing {viz_type} visualization...")
                board.interactive_move(footprint.id)

        print("\nDone!")

    except ImportError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    except ConnectionError as e:
        print(f"\nCONNECTION ERROR: {e}")
        print("\nMake sure:")
        print("  1. KiCad is running")
        print("  2. A PCB file is open")
        print("  3. API server is enabled (Preferences > Plugins)")
        sys.exit(1)

    except RuntimeError as e:
        print(f"\nRUNTIME ERROR: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
