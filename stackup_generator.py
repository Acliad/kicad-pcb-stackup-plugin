#!/usr/bin/env python3
"""
KiCad Stackup Table Generator Plugin

Entry point for both standalone and plugin execution.
Generates stackup table drawings on PCB documentation.
"""

import sys
from stackup.kicad_adapter.connection import connect_to_kicad, check_kicad_available
from stackup.kicad_adapter.extractor import extract_stackup_data
from stackup.core.models import TableConfig, VisualizationMode
from stackup.core.layout import calculate_table_layout
from stackup.core.graphics_models import GraphicalStackupConfig
from stackup.core.graphics_layout import calculate_graphical_layout, adjust_leader_lines
from stackup.kicad_adapter.renderer import render_table_to_board
from stackup.kicad_adapter.graphics_renderer import render_graphical_stackup


def main(visualization_mode: VisualizationMode = VisualizationMode.GRAPHICAL):
    """
    Main plugin execution.

    Args:
        visualization_mode: Type of visualization to generate (TABLE, GRAPHICAL, or BOTH)

    This function:
    1. Connects to KiCad via IPC
    2. Extracts stackup data from the current board
    3. Calculates layout (table or graphical)
    4. Renders as a footprint
    5. Allows user to place it interactively
    """
    mode_name = visualization_mode.value
    print(f"KiCad Stackup Generator ({mode_name} mode)")
    print("-" * 40)

    # Check if kicad-python is available
    if not check_kicad_available():
        print("ERROR: kicad-python is not installed.")
        print("Install it with: pip install kicad-python>=0.2.0")
        sys.exit(1)

    try:
        # Step 1: Connect to KiCad
        print("Connecting to KiCad...")
        kicad, board = connect_to_kicad()
        print("✓ Connected successfully")

        # Step 2: Extract stackup data
        print("\nExtracting stackup data...")
        stackup_data = extract_stackup_data(board)
        print(f"✓ Found {len(stackup_data.layers)} layers")
        print(f"  - Copper layers: {stackup_data.copper_layer_count}")
        print(f"  - Total thickness: {stackup_data.total_thickness:.3f}mm")

        # Step 3: Generate visualization based on mode
        footprints_to_place = []

        if visualization_mode in [VisualizationMode.TABLE, VisualizationMode.BOTH]:
            # Configure table
            table_config = TableConfig(
                style="detailed",  # Options: "detailed", "compact", "minimal"
                units="mm",        # Options: "mm", "mils"
                show_epsilon=True,
                show_loss_tangent=False,
                show_material=True,
                font_size=2.5,
                line_width=0.15
            )

            # Calculate table layout
            print("\nCalculating table layout...")
            table_layout = calculate_table_layout(stackup_data, table_config)
            print(f"✓ Table size: {table_layout.total_width:.1f}mm × {table_layout.total_height:.1f}mm")
            print(f"  - Cells: {len(table_layout.cells)}")
            print(f"  - Columns: {', '.join(table_layout.columns)}")

            # Render table to board
            print("\nRendering table to board...")
            table_footprint = render_table_to_board(board, table_layout, table_config)
            print("✓ Table created successfully")
            footprints_to_place.append(("table", table_footprint))

        if visualization_mode in [VisualizationMode.GRAPHICAL, VisualizationMode.BOTH]:
            # Configure graphical visualization
            # uniform_layer_height_mm defaults to DEFAULT_BASE_HEIGHT_MM (3.0mm)
            graphics_config = GraphicalStackupConfig(
                layer_width_mm=50.0,
                leader_line_length_mm=20.0,
                leader_line_width_mm=0.15,
                text_size_mm=1.5,
                min_callout_spacing_mm=2.0,
                origin_x_mm=0.0,
                origin_y_mm=0.0,
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

            # Render graphical stackup to board
            print("\nRendering graphical stackup to board...")
            graphics_footprint = render_graphical_stackup(board, graphics_layout, graphics_config)
            print("✓ Graphical stackup created successfully")
            footprints_to_place.append(("graphical", graphics_footprint))

        # Step 4: Let user place it interactively
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
