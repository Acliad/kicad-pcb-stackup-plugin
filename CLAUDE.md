# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a KiCad Action Plugin that generates stackup table drawings on PCB documentation. The plugin uses the KiCad IPC API via the `kicad-python` library (v0.2.0+) to communicate with a running KiCad instance.

**Language**: Python 3.9+ (currently developed with Python 3.13.1)

**Key Features** (implemented):
- Generate stackup tables dynamically from PCB settings
- Three table styles: detailed, compact, minimal
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
