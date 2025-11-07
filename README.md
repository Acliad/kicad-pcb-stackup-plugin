# KiCad Stackup Table Generator

A modular, testable KiCad plugin that generates stackup table drawings on PCB documentation. The plugin uses the KiCad IPC API to create dynamic tables with customizable styles and formatting, helping designers produce better fabrication documentation.

## Features

- **Automatic extraction** of stackup data from KiCad board settings
- **Multiple table styles**: Detailed, Compact, and Minimal views
- **Customizable formatting**: Font size, line width, units (mm/mils)
- **Column visibility control**: Show/hide epsilon_r, loss tangent, material, color
- **Modular architecture**: Testable core logic separated from KiCad integration
- **CLI support**: Run as plugin or standalone command-line tool
- **Export capabilities**: JSON and SVG export for external use

## Architecture

The project follows a layered architecture for testability and extensibility:

```
stackup/
├── core/                    # Business logic (KiCad-agnostic, fully testable)
│   ├── models.py           # Data models
│   ├── layout.py           # Table layout algorithms
│   └── formatting.py       # Formatting utilities
├── kicad_adapter/          # KiCad integration layer
│   ├── connection.py       # Connection management
│   ├── extractor.py        # Extract data from KiCad
│   └── renderer.py         # Render tables to KiCad
└── cli/                    # Command-line interface
    └── main.py
```

## Installation

### As a KiCad Plugin

1. Copy the entire plugin directory to your KiCad plugins folder:
   - **macOS**: `~/Documents/KiCad/9.0/plugins/kicad-stackup-generator/`
   - **Linux**: `~/.local/share/KiCad/9.0/plugins/kicad-stackup-generator/`
   - **Windows**: `C:\Users\<username>\Documents\KiCad\9.0\plugins\kicad-stackup-generator\`

2. KiCad will automatically create a virtual environment and install dependencies from `requirements.txt`

3. Enable the API server in KiCad: **Preferences > Plugins > Enable API server**

4. The plugin button will appear in the PCB Editor toolbar

### For Development

```bash
# Clone the repository
git clone <repository-url>
cd kicad-stackup-generator

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements-dev.txt
```

## Usage

### As a Plugin

1. Open a PCB file in KiCad PCB Editor
2. Click the "Generate Stackup Table" button in the toolbar
3. The plugin will create a stackup table footprint
4. Place the table on your board using the interactive move tool

### As a CLI Tool

```bash
# Basic usage (with KiCad running)
python3 stackup_generator.py

# Advanced CLI with options
python3 -m stackup.cli.main --style compact --units mils --font-size 3.0

# Export stackup data to JSON
python3 -m stackup.cli.main --export-json stackup.json --dry-run

# Export table as SVG
python3 -m stackup.cli.main --export-svg table.svg --style detailed

# Show all options
python3 -m stackup.cli.main --help
```

### CLI Options

```
--style {detailed,compact,minimal}   Table style (default: detailed)
--units {mm,mils}                    Units for thickness (default: mm)
--font-size FLOAT                    Font size in mm (default: 2.5)
--line-width FLOAT                   Grid line width in mm (default: 0.15)
--no-epsilon                         Hide epsilon_r column
--show-loss-tangent                  Show loss tangent column
--no-material                        Hide material column
--show-color                         Show color column
--export-json FILE                   Export stackup data to JSON
--export-svg FILE                    Export table as SVG
--dry-run                            Calculate without creating on board
```

## Table Styles

### Detailed
Shows all available information: Layer, Type, Thickness, Material, εᵣ, tan δ (configurable)

### Compact
Essential information only: Layer, Thickness, Material

### Minimal
Copper layers only: Layer, Thickness

## Testing

The project includes comprehensive unit tests that don't require KiCad:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=stackup --cov-report=html

# Run only unit tests (no KiCad required)
pytest -m "not integration"

# Run integration tests (KiCad required)
pytest -m integration
```

## Development

### Project Structure

- `stackup_generator.py` - Main plugin entry point
- `plugin.json` - KiCad plugin manifest
- `stackup/core/` - Business logic (pure Python, testable)
- `stackup/kicad_adapter/` - KiCad API integration
- `stackup/cli/` - Command-line interface
- `tests/` - Unit and integration tests

### Adding New Features

1. **New table styles**: Add layout functions to `stackup/core/layout.py`
2. **New formatters**: Add utilities to `stackup/core/formatting.py`
3. **New data sources**: Create extractors in `stackup/kicad_adapter/`
4. **New renderers**: Add backends to `stackup/kicad_adapter/renderer.py`

## Requirements

- KiCad 9.0 or higher
- Python 3.9 or higher
- kicad-python >= 0.2.0

## License

[Add license information]

## Contributing

[Add contribution guidelines] 