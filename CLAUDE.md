# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a KiCad Action Plugin that generates stackup table drawings on PCB documentation. The plugin uses the KiCad IPC API via the `kicad-python` library (v0.2.0+) to communicate with a running KiCad instance.

**Language**: Python 3.9+ (currently developed with Python 3.13.1)

**Key Features** (implemented):
- Generate stackup tables dynamically from PCB settings
- Three table styles: detailed, compact, minimal
- Graphical cross-section visualization with customizable scale
- Full customization of labels, formatting, and column visibility
- CLI and plugin interface support
- Export to JSON and SVG
- Comprehensive unit tests

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies (for testing)
pip install -r requirements-dev.txt
```

### Running the Plugin
```bash
# Basic plugin mode (requires KiCad 9.0+ running with API server enabled)
python3 stackup_generator.py

# Advanced CLI with options
python3 -m stackup.cli.main --style compact --units mils

# Graphical cross-section with custom scale (150mm tall)
python3 -m stackup.cli.main --visualization graphical --scale 150

# Different thickness modes with scale
python3 -m stackup.cli.main --visualization graphical --thickness-mode proportional --scale 100
python3 -m stackup.cli.main --visualization graphical --thickness-mode scaled --scale 200

# Export stackup data
python3 -m stackup.cli.main --export-json stackup.json --dry-run
```

### Testing
```bash
# Run all unit tests (no KiCad required)
pytest

# Run with coverage
pytest --cov=stackup --cov-report=html

# Run only unit tests
pytest -m "not integration"

# Run integration tests (requires KiCad running)
pytest -m integration
```

### Plugin Installation
Copy or symlink the plugin directory to:
- **macOS**: `~/Documents/KiCad/9.0/plugins/`
- **Linux**: `~/.local/share/KiCad/9.0/plugins/`
- **Windows**: `C:\Users\<username>\Documents\KiCad\9.0\plugins\`

KiCad will auto-create a virtualenv and install from `requirements.txt`.

## Architecture Overview

### IPC Communication Pattern
The plugin uses **Protocol Buffers over NNG sockets** to communicate with KiCad, not SWIG bindings. This means:
- KiCad must be running for the plugin to work
- Default socket: `/tmp/kicad/api.sock` (Unix) or named pipe (Windows)
- All board access is remote via IPC

### Core Classes (from kicad-python)
- **`KiCad`**: Main connection class to KiCad instance
- **`Board`**: Access to PCB board data and operations
- **`BoardStackup`**: Stackup layer information (copper layers, dielectrics, materials)
- **`BoardText`**: Text drawing primitive for labels
- **`FootprintInstance`**: Custom footprints for table graphics
- **`Vector2`**: Position and sizing coordinates
- **`BoardLayer`**: Layer enumeration and identification

### Transaction-Based Modifications
All board modifications must be wrapped in transactions:
```python
board = kicad.get_board()
board.BeginCommit("Add stackup table")
# ... make changes ...
board.EndCommit()
```

### Type Safety
The kicad-python library uses Python type hints throughout. Enable mypy for type checking.

## Plugin Structure

### Modular Architecture

The plugin follows a **layered architecture** for testability and extensibility:

```
kicad-stackup-generator/
├── plugin.json              # KiCad plugin manifest
├── stackup_generator.py     # Main plugin entry point (thin wrapper)
├── requirements.txt         # kicad-python>=0.2.0
├── requirements-dev.txt     # Dev dependencies (pytest, mypy, ruff)
├── pytest.ini              # Pytest configuration
│
├── stackup/                 # Core package
│   ├── __init__.py
│   ├── core/               # Business logic (KiCad-agnostic, testable)
│   │   ├── models.py       # Data classes (StackupData, TableLayout, etc.)
│   │   ├── layout.py       # Table layout algorithms (pure functions)
│   │   └── formatting.py   # Text formatting, unit conversions
│   │
│   ├── kicad_adapter/      # KiCad integration layer
│   │   ├── connection.py   # KiCad connection management
│   │   ├── extractor.py    # Extract stackup data from Board
│   │   └── renderer.py     # Render tables as FootprintInstance
│   │
│   └── cli/                # CLI interface
│       └── main.py         # argparse CLI with advanced options
│
├── tests/                  # Unit tests (no KiCad required)
│   ├── test_models.py
│   ├── test_layout.py
│   ├── test_formatting.py
│   └── test_integration.py # Integration tests (KiCad required)
│
└── icons/
    ├── stackup_24.png
    └── stackup_48.png
```

### Architecture Layers

1. **Core Layer** (`stackup/core/`)
   - Pure Python business logic
   - No KiCad imports
   - Fully unit testable with mock data
   - Contains: data models, layout algorithms, formatting utilities

2. **Adapter Layer** (`stackup/kicad_adapter/`)
   - Converts between KiCad types and domain models
   - `extractor.py`: Board → StackupData
   - `renderer.py`: TableLayout → FootprintInstance
   - All KiCad API interaction happens here

3. **Entry Points**
   - `stackup_generator.py`: Simple plugin entry point
   - `stackup/cli/main.py`: Advanced CLI with options
   - Both work in plugin mode and standalone mode

### Example Flow
```python
# Entry point orchestrates the layers
kicad, board = connect_to_kicad()              # Adapter
stackup_data = extract_stackup_data(board)      # Adapter → Core model
layout = calculate_table_layout(stackup_data)  # Pure business logic
footprint = render_table_to_board(board, layout) # Core model → Adapter
```

### Aligned Text Column Feature

When multiple callouts have varying vertical displacements (especially in dense stackups), the plugin automatically calculates the appropriate leader line length to create an aligned text column. This prevents horizontal crowding of 45° elbows while maintaining a professional, organized appearance.

**How It Works**:
1. Scan all callout positions and calculate vertical displacements
2. For each callout, calculate required leader length:
   - Straight lines (small displacement): use base length
   - Elbow lines (large displacement): `initial_segment (40%) + diagonal (45°) + final_segment (5.0mm)`
3. Find maximum required length across all callouts
4. Use this maximum uniformly for all callouts
5. Result: Text aligns at consistent X position, elbows have comfortable spacing

**Key Formulas**:
- Elbow required length = `0.4 × base_length + vertical_displacement + 5.0mm`
- All callouts use: `effective_length = max(required_length for all callouts, base_length)`

**Configuration**: No user-facing parameters needed (smart defaults). The base `leader_line_length_mm` (20.0mm default) serves as the minimum; actual length extends as needed based on callout displacements.

## Reference Documentation

The `docs/kicad-python/` directory (gitignored) contains the complete kicad-python library source for reference:
- **`docs/kicad-python/examples/layer_indicator/`**: Example plugin creating layer indicator footprints
- **`docs/kicad-python/examples/round_tracks/`**: Example plugin rounding track corners
- **Online docs**: https://docs.kicad.org/kicad-python-main

Study these examples for patterns on:
- Creating and placing footprints
- Drawing graphics on board layers
- Handling user interaction
- Error handling with IPC

## Dependencies

### Required
- `kicad-python>=0.2.0` (includes protobuf 5.29+, pynng 0.8.0+)

### Development (if adding tests/linting)
Reference kicad-python's setup:
- **Testing**: pytest
- **Linting**: ruff
- **Type checking**: mypy
- **Task runner**: nox

## Development Requirements

1. **KiCad Installation**: Must have KiCad 9.0 or higher installed
2. **API Server**: Enable in KiCad: Preferences > Plugins > "Enable API server"
3. **Runtime Dependency**: Unlike SWIG bindings, IPC API requires KiCad to be actively running
4. **Socket Permissions**: Ensure Python has access to the IPC socket path

## Recent Improvements

### Scale-Independent Callout Spacing (IMPLEMENTED)

**Feature**: Callout spacing remains constant in absolute units regardless of visualization scale.

**Problem Solved**: Previously, `min_callout_spacing_mm` scaled linearly with the visualization scale, causing excessive spacing at large scales (e.g., 17.6mm at 200mm scale instead of 8.8mm).

**Implementation**:
- Removed scaling from `min_callout_spacing_mm`, `leader_line_length_mm`, and `min_elbow_height_mm` in `_scale_config()`
- These parameters now remain at their base values (8.8mm, 20.0mm, 0.5mm) regardless of scale
- Visual line widths still scale for consistent appearance
- Text size scaling preserved for future font size feature compatibility

**Benefits**:
- Consistent, professional appearance across all scales (50mm-500mm range)
- No excessive spacing at large scales
- No crowding at small scales
- Predictable behavior for users

**Configuration**:
```python
config = GraphicalStackupConfig(
    scale_mm=200.0,  # Large scale
    min_callout_spacing_mm=8.8,  # Stays 8.8mm, doesn't scale to 17.6mm
    leader_line_length_mm=20.0,  # Stays 20mm, doesn't scale
)
```

**Testing**: Comprehensive test suite in `tests/test_graphics_layout.py::TestScaleIndependentSpacing`

### Dynamic Leader Direction (IMPLEMENTED)

**Feature**: Leader lines automatically adapt direction based on available space, or can be manually controlled.

**Problem Solved**: At small scales with many layers, callout columns can exceed visualization bounds. At large scales, all callouts pointing outward is always optimal.

**Implementation**:
- New `_determine_leader_direction()` algorithm dynamically detects optimal direction
- Decision criteria:
  - If callout column height > 120% of visualization height → point inward
  - If leader length > 50% of layer width → point inward
  - Otherwise → point outward (default)
- New `leader_direction` config field: `"auto"` (default), `"outward"`, or `"inward"`
- **Important**: Both inward and outward leaders start from the right edge of the cross-section to avoid collision with the drawing
- Aligned text column feature preserved for both directions

**Benefits**:
- Robust rendering across all scales and layer counts
- Professional appearance maintained automatically
- User can override automatic detection when needed
- Prevents callouts from extending far beyond visualization bounds

**Configuration**:
```python
# Automatic detection (recommended)
config = GraphicalStackupConfig(
    leader_direction="auto",  # Default: dynamically detects optimal direction
)

# Manual override
config = GraphicalStackupConfig(
    leader_direction="inward",  # Force inward direction
)

config = GraphicalStackupConfig(
    leader_direction="outward",  # Force outward direction
)
```

**CLI Usage**:
```bash
# Automatic (default)
python3 -m stackup.cli.main --visualization graphical --scale 50

# Currently no CLI flag for manual override (future enhancement)
```

**Examples**:
- 50mm scale, 8 layers: Callouts exceed bounds → **automatic inward**
- 200mm scale, 8 layers: Callouts fit well → **automatic outward**
- 100mm scale, 4 layers: Callouts fit well → **automatic outward**

**Testing**: Comprehensive test suite in `tests/test_graphics_layout.py::TestDynamicLeaderDirection`

**Technical Details**:
- Direction detection occurs in `adjust_leader_lines()` after visualization creation
- All leaders (both inward and outward) start from the right edge of the cross-section
- This prevents collision with the cross-section drawing itself
- When collisions detected, elbow creation respects the detected/configured direction
- Both straight and elbow leaders start from the same edge (right side)

## Known Issues & Limitations

### Dielectric Material Extraction (KiCad 9.0.4)

**Issue**: The plugin cannot extract custom material names from dielectric layers (e.g., "FR4", "JLC7628 FR4", "Prepreg").

**Root Cause**: KiCad's IPC API does not expose dielectric material properties (`material_name`, `epsilon_r`, `loss_tangent`) even though this data is stored in the `.kicad_pcb` file. The `proto.dielectric.layer` field is empty when accessed via `board.get_stackup()`.

**Current Behavior**:
- Copper layers: Display "COPPER"
- Soldermask layers: Display "SOLDERMASK"
- Dielectric layers: Display "DIELECTRIC" (fallback, since material data is unavailable)

**Workaround**: None available until KiCad API is updated to expose dielectric material properties.

**Expected Fix**: This should be resolved in a future KiCad release when the API is enhanced to include stackup material data in the protobuf messages.

### Text Spacing at Small Scales (FIXED)

**Previous Issue**: When generating stackup visualizations at very small scales (e.g., `--scale 50`), text callouts could overlap severely.

**Root Cause**: The spacing algorithm was using `min_elbow_height_mm` (0.3mm) as the spacing unit instead of `min_callout_spacing_mm` (4.0mm+), creating a fundamental mismatch with collision detection. At small scales, this resulted in spacing ~17x too small.

**Fix Applied**: Updated `_calculate_symmetric_positions()` in `stackup/core/graphics_layout.py` to use the correct spacing value. All callouts now respect the minimum spacing threshold regardless of scale.

**Verification**:
- Diagnostic tests confirm zero spacing violations at 50mm scale
- All 111 unit tests pass
- Text spacing is now scale-invariant and guaranteed to meet minimums

**See also**: `stackup/core/diagnostics.py` for detailed analysis and diagnostic utilities.

### Callout Horizontal Spacing (FIXED)

**Previous Issue**: When many callouts required large vertical displacements (e.g., dense stackups with 10+ layers), the 45° elbows would bunch together horizontally because leader line length was fixed at 20mm.

**Root Cause**: Fixed `leader_line_length_mm` meant that large diagonal segments consumed most of the horizontal budget, leaving little space for the final horizontal segment. This caused elbow endpoints to be very close horizontally (2-3mm), creating visual crowding.

**Fix Applied**: Implemented **dynamic leader length calculation with aligned text column approach**:
- Before adjusting leader lines, scans all callout vertical displacements
- Calculates maximum required leader length based on displacement formula: `initial_segment (40%) + diagonal_segment (45°) + final_segment (5.0mm minimum)`
- Uses this maximum uniformly for all callouts to ensure aligned text column
- Result: All callout text aligns at consistent X position, professional appearance, no horizontal crowding

**Implementation**:
- Added `_calculate_required_leader_length()` helper function in `stackup/core/graphics_layout.py`
- Added `MIN_FINAL_SEGMENT_MM = 5.0` constant for comfortable horizontal spacing
- Modified `adjust_leader_lines()` to calculate and apply maximum leader length
- Used dataclasses.replace() to create effective_config with adjusted dimensions

**Verification**:
- 70 unit tests pass (63 existing + 7 new aligned column tests)
- New tests verify: aligned text column, leader length extension, final segment spacing, layout symmetry
- Feature works consistently across all scales and thickness modes
- No performance regression

**See also**:
- `stackup/core/graphics_layout.py:_calculate_required_leader_length()` for calculation logic
- `stackup/core/graphics_layout.py:adjust_leader_lines()` for implementation
- `tests/test_graphics_layout.py:TestAlignedTextColumn` for comprehensive test coverage

## Project Status

**Current state**: Core implementation complete ✓
- ✓ Modular architecture implemented
- ✓ Core business logic (models, layout, formatting)
- ✓ KiCad adapter layer (connection, extractor, renderer)
- ✓ Main plugin entry point
- ✓ CLI interface with advanced options
- ✓ Comprehensive unit tests
- ✓ plugin.json manifest
- ✓ requirements.txt and requirements-dev.txt

**Still needed**:
1. Plugin icons (24x24 and 48x48 PNG) - placeholder needed
2. Testing with live KiCad instance
3. Integration tests
4. License and contribution guidelines

## Scale Feature

The graphical cross-section visualization supports a `--scale` parameter to control the overall size of the generated drawing.

### How It Works

- **Scale Parameter**: Specifies the desired total **height** of the cross-section in millimeters
- **Proportional Scaling**: All dimensions (width, height, text size, line widths, spacing) scale uniformly to maintain aspect ratio
- **Applies To**: Graphical mode only (cross-section drawings)

### Configuration

**CLI Usage**:
```bash
# 150mm tall cross-section
python3 -m stackup.cli.main --visualization graphical --scale 150

# Works with all thickness modes
python3 -m stackup.cli.main --scale 100 --thickness-mode uniform
python3 -m stackup.cli.main --scale 200 --thickness-mode proportional
python3 -m stackup.cli.main --scale 150 --thickness-mode scaled
```

**Programmatic Usage**:
```python
from stackup.core.graphics_models import GraphicalStackupConfig
from stackup.core.graphics_layout import calculate_graphical_layout, adjust_leader_lines

# Create config with desired scale
config = GraphicalStackupConfig(
    scale_mm=150.0,  # 150mm total height
    thickness_mode=ThicknessMode.PROPORTIONAL,
    # ... other options ...
)

# calculate_graphical_layout returns (layout, effective_config) tuple
# The effective_config has scaled dimensions and should be used for subsequent operations
layout, effective_config = calculate_graphical_layout(stackup_data, config)

# Use effective_config for leader line adjustment
layout = adjust_leader_lines(layout, effective_config)
```

**GUI Integration** (for future GUI):
```python
# Example GUI control
scale_input = wx.SpinCtrlDouble(
    parent,
    value=100.0,      # Default
    min=10.0,         # Minimum
    max=1000.0,       # Maximum
    inc=10.0,         # Increment
    name="Cross-section Height (mm)"
)

config = GraphicalStackupConfig(
    scale_mm=scale_input.GetValue()
)
```

### Technical Details

**Implementation**:
- Two-pass calculation: First pass with default dimensions determines base height, second pass applies scale factor
- Scale factor = `desired_height / base_height`
- All dimensional fields in `GraphicalStackupConfig` are multiplied by scale factor:
  - `layer_width_mm`
  - `uniform_layer_height_mm`
  - `max_total_height_mm`
  - `leader_line_length_mm`
  - `text_size_mm`
  - `soldermask_gap_mm`
  - `copper_hatch_spacing_mm`
  - `line_width_mm`
  - `min_callout_spacing_mm`
  - `min_elbow_height_mm`

**Positioning**:
- The origin (`origin_x_mm`, `origin_y_mm`) is NOT scaled - only the content dimensions scale
- For footprint rendering (plugin mode), use `origin_x_mm=0.0, origin_y_mm=0.0` so the visualization starts at the footprint's origin
- Non-zero origins are useful for SVG export or when positioning multiple visualizations manually

**Ratios Preserved**: Unitless ratios like `copper_height_ratio`, `dielectric_height_ratio`, and `soldermask_height_ratio` remain unchanged.

### Edge Cases

- **Very Small Scale** (< 10mm): Text may become illegible, lines too thin
- **Very Large Scale** (> 1000mm): May exceed KiCad board bounds
- **Default Behavior**: If `scale_mm=None`, uses default dimensions based on thickness mode

### Testing

The scale feature includes comprehensive unit tests (see `tests/test_graphics_layout.py::TestScaleFeature`):
- Verifies proportional scaling of all dimensions
- Tests with all three thickness modes (UNIFORM, PROPORTIONAL, SCALED)
- Validates aspect ratio preservation
- Tests edge cases (small/large scales)
- Confirms exact height matching

## Extending the Plugin

### Adding New Table Styles
Add a new layout function to `stackup/core/layout.py`:
```python
def _custom_layout(stackup: StackupData, config: TableConfig) -> TableLayout:
    # Your layout algorithm here
    cells = [...]
    return TableLayout(cells, total_width, total_height, columns)
```

### Adding New Formatters
Add utilities to `stackup/core/formatting.py`:
```python
def format_impedance(impedance_ohm: float) -> str:
    return f"{impedance_ohm:.1f}Ω"
```

### Adding New Data Sources
Create new extractors in `stackup/kicad_adapter/`:
```python
# extractor_impedance.py
def extract_impedance_data(board: Board) -> ImpedanceData:
    # Extract impedance-related data
    pass
```

### Adding New Renderers
Add rendering backends to `stackup/kicad_adapter/renderer.py`:
```python
def render_table_to_pdf(layout: TableLayout) -> bytes:
    # Render as PDF
    pass
```

# Special Instructions For Claude
- DO NOT EVERY, UNDER ANY CIRCUMSTANCE ADD OR COMMIT ANYTHING VIA GIT!