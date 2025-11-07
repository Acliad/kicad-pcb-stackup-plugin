# Visual Enhancements for Graphical Stackup - Implementation Plan

## Overview
This document describes the implementation of visual enhancements to the KiCad stackup generator plugin's graphical cross-section mode. The enhancements add realistic visual representation of PCB stackups with proportional layer thickness, soldermask spacing, and copper hatching patterns.

## Requirements (User Specifications)
1. **Soldermask Layer Spacing**: Soldermask layers should appear visually separated from other layers with a configurable gap
2. **Copper Layer Hatching**: Copper layers should have 45-degree diagonal hatch lines for visual distinction
3. **Proportional Layer Thickness**: Three thickness modes:
   - **Uniform** (legacy): All layers same height
   - **Proportional** (default): Fixed ratios - copper baseline (1.0x = 3.0mm), dielectric (1.55x = 4.65mm), soldermask (0.5x = 1.5mm)
   - **Scaled**: Use actual thickness data from stackup, scaled to fit max height
4. **CLI Control**: User-configurable via command-line arguments
5. **Constants**: No magic numbers - all ratios defined as constants

## Implementation Summary

### 1. Configuration Models (`stackup/core/graphics_models.py`)
**Status**: ✅ Completed

**Changes**:
- Added module-level constants (no magic numbers):
  - `COPPER_HEIGHT_RATIO = 1.0` - Copper is always the baseline
  - `DIELECTRIC_HEIGHT_RATIO = 1.55` - 1.55x copper thickness
  - `SOLDERMASK_HEIGHT_RATIO = 0.5` - Thin soldermask layer
  - `DEFAULT_BASE_HEIGHT_MM = 3.0` - Base height for proportional mode (copper = 3.0mm)
  - `CALLOUT_TEXT_PADDING_MM = 1.1` - Padding between leader line endpoint and text label
- Added `ThicknessMode` enum with three modes: `UNIFORM`, `PROPORTIONAL`, `SCALED`
- Extended `GraphicalStackupConfig` dataclass with:
  - `thickness_mode`: Controls layer height calculation (default: PROPORTIONAL)
  - `uniform_layer_height_mm`: Base height (defaults to `DEFAULT_BASE_HEIGHT_MM`)
  - Ratio fields use constants: `copper_height_ratio=COPPER_HEIGHT_RATIO`, etc.
  - `max_total_height_mm`: Max height constraint for scaled mode (100mm default)
  - `soldermask_gap_mm`: Gap spacing above/below soldermask layers (1.0mm default)
  - `copper_hatch_enabled`: Enable/disable copper hatching (True default)
  - `copper_hatch_spacing_mm`: Distance between hatch lines (1.0mm default)
  - `copper_hatch_angle_deg`: Angle of hatch lines (45° default)
- Extended `LayerRectangle` to store `layer_type` for rendering decisions

**Architecture**: Copper is always 1.0 baseline; adjust base height (3.0mm) instead of copper ratio

### 2. CLI Interface (`stackup/cli/main.py`)
**Status**: ✅ Completed

**Changes**:
- Added `--thickness-mode` argument: choices `[uniform, proportional, scaled]`, default `proportional`
- Added `--no-copper-hatch` flag: Disable hatching on copper layers
- Added `--soldermask-gap` argument: Custom gap size in mm (default: 1.0)
- Added `--copper-hatch-spacing` argument: Hatch line density in mm (default: 1.0)
- Imported `ThicknessMode` enum and mapped CLI string args to enum values
- Updated graphical config instantiation to pass new parameters

**Example Usage**:
```bash
# Default proportional mode with hatching
python -m stackup.cli.main --visualization graphical

# Uniform thickness (legacy behavior)
python -m stackup.cli.main --visualization graphical --thickness-mode uniform

# Scaled mode with custom gap
python -m stackup.cli.main --visualization graphical --thickness-mode scaled --soldermask-gap 2.0

# Disable copper hatching
python -m stackup.cli.main --visualization graphical --no-copper-hatch
```

### 3. Layer Height Calculation (`stackup/core/graphics_layout.py`)
**Status**: ✅ Completed

**Changes**:
- Created `_calculate_layer_heights()` helper function:
  - **Uniform mode**: Returns list of uniform heights
  - **Proportional mode**: Applies fixed ratios based on layer type
  - **Scaled mode**: Calculates actual thickness ratios, scales to fit max height
- Updated `calculate_graphical_layout()`:
  - Calls `_calculate_layer_heights()` instead of using uniform height directly
  - Uses per-layer height from calculated list
  - Stores `layer_type` in `LayerRectangle` for downstream rendering
- Updated `adjust_leader_lines()`:
  - Reads actual rectangle height instead of assuming uniform
  - Handles variable layer heights in collision detection and adjustment

### 4. Soldermask Gap Spacing (`stackup/core/graphics_layout.py`)
**Status**: ✅ Completed

**Changes**:
- Modified `calculate_graphical_layout()` to insert gaps:
  - Before soldermask layer: `y_offset += config.soldermask_gap_mm`
  - After soldermask layer: `y_offset += config.soldermask_gap_mm`
- Gap is only added if `config.soldermask_gap_mm > 0`
- Total height calculation accounts for gaps

**Visual Result**:
```
[Other layers]
    <-- Gap (1mm) -->
[Soldermask - thin]
    <-- Gap (1mm) -->
[Copper]
```

### 5. Copper Hatching Renderer (`stackup/kicad_adapter/graphics_renderer.py`)
**Status**: ✅ Completed

**Changes**:
- Created `_generate_hatch_lines()` function:
  - Generates 45-degree diagonal lines across rectangle bounds
  - Configurable spacing between lines
  - Supports arbitrary angles (extensible for future)
- Created `_clip_line_to_rect()` helper:
  - Cohen-Sutherland line clipping algorithm
  - Clips hatch lines to rectangle boundaries for clean rendering
- Modified `_add_rectangle()`:
  - Checks if layer is copper: `rect.layer_type == LayerType.COPPER.value`
  - If copper and hatching enabled, generates hatch lines
  - Adds each hatch line as `BoardSegment` primitive
- Updated `render_graphical_stackup_to_svg()`:
  - Added hatching support to SVG export for consistency

**Rendering Flow**:
```
For each LayerRectangle:
  1. Draw rectangle border (BoardRectangle)
  2. If copper layer and hatching enabled:
     a. Generate hatch line coordinates
     b. Clip lines to rectangle bounds
     c. Draw each line as BoardSegment
```

### 6. Unit Tests (`tests/test_graphics_layout.py`)
**Status**: ✅ Completed (34 tests passing)

**New Test Coverage**:
- `TestThicknessModes` class:
  - `test_uniform_thickness_mode`: All layers same height
  - `test_proportional_thickness_mode`: Fixed ratios applied correctly
  - `test_scaled_thickness_mode`: Actual thickness scaled to max height
  - `test_calculate_layer_heights_uniform`: Helper function with uniform mode
  - `test_calculate_layer_heights_proportional`: Helper with proportional mode
- `TestSoldermaskGapSpacing` class:
  - `test_soldermask_gap_disabled`: No gaps when set to 0
  - `test_soldermask_gap_enabled`: Total height includes gaps
  - `test_soldermask_rectangles_have_gaps`: Rectangle positions account for gaps
- `TestLayerTypeStorage` class:
  - `test_layer_type_stored_in_rectangles`: Layer type propagated to rectangles
  - `test_copper_layers_identified`: Copper layers identifiable for hatching
  - `test_soldermask_layers_identified`: Soldermask layers identifiable for gaps

**Updated Tests**:
- Fixed existing tests to explicitly set `thickness_mode=ThicknessMode.UNIFORM` (since default changed to PROPORTIONAL)

## Architecture Decisions

### 1. Separation of Concerns
- **Core layer** (`graphics_layout.py`): Pure business logic, no KiCad dependencies
- **Adapter layer** (`graphics_renderer.py`): KiCad-specific rendering code
- **Models** (`graphics_models.py`): Data structures shared between layers

### 2. Constants Over Magic Numbers
- All ratios defined as module-level constants: `COPPER_HEIGHT_RATIO`, `DIELECTRIC_HEIGHT_RATIO`, `SOLDERMASK_HEIGHT_RATIO`
- Default base height as constant: `DEFAULT_BASE_HEIGHT_MM`
- Makes code self-documenting and maintainable
- Easy to adjust all values from one location

### 3. Copper as Baseline (1.0)
- **Design principle**: Copper thickness is always the reference (ratio = 1.0)
- To adjust visual size: change `DEFAULT_BASE_HEIGHT_MM` (3.0mm), NOT copper ratio
- Other layers scale relative to copper baseline
- Example: dielectric = 1.55x copper means 1.55 × 3.0mm = 4.65mm
- **Benefit**: Intuitive ratios - "dielectric is 1.55x copper" is clearer than arbitrary fractional ratios

### 4. Backward Compatibility
- Added `ThicknessMode.UNIFORM` to preserve legacy behavior
- All new config parameters have sensible defaults
- Existing tests updated, but old behavior still accessible

### 5. Extensibility
- Hatch pattern generator supports arbitrary angles (not just 45°)
- Gap spacing can be applied to any layer type (not just soldermask)
- Ratios are configurable via config object

### 6. Testability
- Pure functions in core layer → easy to unit test
- Mock data fixtures for different stackup types
- Tests use constants instead of hardcoded values
- Tests verify both visual calculations and integration

## Before & After Comparison

### Before
```
All layers uniform height (5mm):
┌─────────────────┐
│   F.Cu (5mm)    │
├─────────────────┤
│   Core (5mm)    │
├─────────────────┤
│   B.Cu (5mm)    │
└─────────────────┘
```

### After (Proportional Mode)
```
Realistic proportions + gaps + hatching (with 3.0mm copper):
     <-- Gap -->
┌─────────────────┐ Soldermask (1.5mm = 0.5 × 3.0)
│   F.Mask        │
└─────────────────┘
     <-- Gap -->
┌─────────────────┐ Copper (3.0mm = 1.0 × 3.0)
│ / F.Cu / / / /  │ ← Hatched
└─────────────────┘
┌─────────────────┐ Dielectric (4.65mm = 1.55 × 3.0)
│      Core       │
└─────────────────┘
┌─────────────────┐ Copper (3.0mm = 1.0 × 3.0)
│ / B.Cu / / / /  │ ← Hatched
└─────────────────┘
     <-- Gap -->
┌─────────────────┐ Soldermask (1.5mm = 0.5 × 3.0)
│   B.Mask        │
└─────────────────┘
     <-- Gap -->
```

## Technical Details

### Thickness Mode Calculations

#### Uniform Mode
```python
heights = [config.uniform_layer_height_mm] * len(layers)
```

#### Proportional Mode
```python
# Constants defined at module level (no magic numbers)
COPPER_HEIGHT_RATIO = 1.0      # Baseline
DIELECTRIC_HEIGHT_RATIO = 1.55  # 1.55x copper
SOLDERMASK_HEIGHT_RATIO = 0.5   # Thin layer
DEFAULT_BASE_HEIGHT_MM = 3.0    # Base height (copper = 3.0mm)

# Calculation
for layer in layers:
    if layer.type == COPPER:
        height = base_height * COPPER_HEIGHT_RATIO  # 3.0mm (1.0 × 3.0)
    elif layer.type == DIELECTRIC:
        height = base_height * DIELECTRIC_HEIGHT_RATIO  # 4.65mm (1.55 × 3.0)
    elif layer.type == SOLDERMASK:
        height = base_height * SOLDERMASK_HEIGHT_RATIO  # 1.5mm (0.5 × 3.0)
```

#### Scaled Mode
```python
scale_factor = max_height / total_actual_thickness
heights = [layer.thickness * scale_factor for layer in layers]
```

### Hatch Pattern Algorithm

1. **Calculate coverage area**: `diagonal = sqrt(width² + height²)`
2. **Determine line count**: `num_lines = diagonal / spacing + 2`
3. **Generate parallel lines** at 45° offset by `i * spacing`
4. **Clip to rectangle bounds** using Cohen-Sutherland algorithm
5. **Render as segments**: Each clipped line → `BoardSegment`

### Gap Insertion Logic
```python
for idx, layer in enumerate(layers):
    if layer.type == SOLDERMASK:
        y_offset += gap_mm  # Before

    draw_rectangle(y_offset, height)
    y_offset += height

    if layer.type == SOLDERMASK:
        y_offset += gap_mm  # After
```

## Performance Considerations

- **Hatch line generation**: O(n) where n = diagonal/spacing (~50 lines for typical PCB)
- **Line clipping**: O(1) per line (Cohen-Sutherland iterative algorithm)
- **Layout calculation**: O(m) where m = layer count (typically <20 layers)
- **Overall complexity**: Linear, no performance concerns for typical stackups

## Future Enhancements (Out of Scope)

1. **Cross-hatching**: Add perpendicular hatch lines for denser pattern
2. **Custom layer colors**: Color-code layers by type (green soldermask, copper color, etc.)
3. **Layer labels**: Overlay text directly on layers
4. **3D extrusion**: Export to 3D format for visualization
5. **Interactive mode**: Click layers to see properties

## Testing Strategy

### Unit Tests (No KiCad Required)
- Pure business logic in `graphics_layout.py`
- Mock data with `StackupData` fixtures
- Test each mode independently
- Test edge cases (single layer, empty stackup, etc.)

### Integration Tests (Future - Requires KiCad)
- Full rendering pipeline with real KiCad board
- Verify footprint creation on board
- Test interactive placement
- SVG export validation

## Files Modified

1. ✅ `stackup/core/graphics_models.py` - Data models and config
2. ✅ `stackup/cli/main.py` - CLI argument parsing
3. ✅ `stackup/core/graphics_layout.py` - Layout algorithms
4. ✅ `stackup/kicad_adapter/graphics_renderer.py` - KiCad rendering
5. ✅ `tests/test_graphics_layout.py` - Unit tests

## Validation

### Test Results
```
34 tests passed in 0.06s
- 23 existing tests (updated for new default)
- 11 new tests for visual features
```

### Code Quality
- Type hints throughout
- Comprehensive docstrings
- Pure functions where possible
- No KiCad dependencies in core layer

## Final Configuration Summary

### Default Visual Proportions (Proportional Mode)
With `DEFAULT_BASE_HEIGHT_MM = 3.0`:

| Layer Type   | Ratio Constant              | Calculated Height | Visual Appearance |
|--------------|-----------------------------|--------------------|-------------------|
| Copper       | `COPPER_HEIGHT_RATIO = 1.0` | 3.0mm (1.0 × 3.0) | Baseline with 45° hatching |
| Dielectric   | `DIELECTRIC_HEIGHT_RATIO = 1.55` | 4.65mm (1.55 × 3.0) | 1.55x thicker than copper |
| Soldermask   | `SOLDERMASK_HEIGHT_RATIO = 0.5` | 1.5mm (0.5 × 3.0) | Thin layer with 1mm gaps above/below |

**Key Design Points**:
- Copper is always the baseline (1.0) at 3.0mm - adjust `DEFAULT_BASE_HEIGHT_MM` to change all proportional sizes
- No magic numbers - all values defined as constants at module level
- Ratios are intuitive: "dielectric is 1.55x copper thickness", "soldermask is 0.5x (half)"
- Soldermask appears thin and visually separated with gaps

## Intelligent Elbow Generation (Enhancement)

### Problem
Small elbows (< 0.5mm vertical displacement) in leader lines look silly and unprofessional. When layers are closely spaced, the collision avoidance algorithm would create tiny elbows that are visually unappealing.

### Solution: Smart Elbow Size Management
**Status**: ✅ Completed (December 2024)

**Implementation Strategy**:
1. **Elbow size threshold**: MIN_ELBOW_HEIGHT_MM = 0.5mm
2. **Decision logic**: If calculated elbow height < 0.5mm → use straight line, else → use elbow
3. **Spacing enforcement**: When callouts are too close AND would create small elbows → increase spacing to force minimum 0.5mm elbow

### Technical Implementation

#### 1. New Constant (`stackup/core/graphics_models.py:27`)
```python
MIN_ELBOW_HEIGHT_MM = 0.5  # Elbows with less than 0.5mm vertical displacement become straight lines
```

#### 2. Configuration Field (`stackup/core/graphics_models.py:128`)
```python
min_elbow_height_mm: float = MIN_ELBOW_HEIGHT_MM  # Minimum elbow height threshold
```

#### 3. Helper Functions (`stackup/core/graphics_layout.py`)

**`_calculate_elbow_heights()` (lines 244-270)**
- Calculates vertical displacement for each proposed leader line adjustment
- Returns list of elbow heights (one per adjusted leader)

**`_should_use_straight_line()` (lines 273-284)**
- Decision function: elbow_height < min_elbow_height_mm → straight line
- Centralizes threshold comparison logic

**`_adjust_spacing_for_minimum_elbows()` (lines 287-328)**
- Enforces minimum elbow height by adjusting callout positions
- If elbow < threshold: push callout to create minimum displacement
- Direction-aware: pushes up or down based on which side of layer center

#### 4. Updated Algorithm Flow (`adjust_leader_lines()`, lines 331-497)

**Before**:
```
1. Detect collisions
2. Calculate even distribution of callouts
3. Create elbows for all adjusted leaders
```

**After (intelligent)**:
```
1. Detect collisions
2. Calculate even distribution of callouts
3. Calculate elbow heights for proposed positions
4. Adjust spacing to enforce minimum elbow heights
5. Recalculate elbow heights after adjustment
6. For each leader:
   - If elbow < 0.5mm: Create straight line (STRAIGHT style)
   - Else: Create elbow (ANGLED_UP or ANGLED_DOWN style)
```

### Visual Examples

**Before (with tiny elbows)**:
```
Layer 1 ──────┐╱  ← 0.2mm elbow (looks silly)
Layer 2 ──────┘   Text
```

**After (intelligent - straight lines)**:
```
Layer 1 ───────── Text (straight, clean)
Layer 2 ───────── Text (straight, clean)
```

**After (intelligent - enforced minimum)**:
```
Layer 1 ──────┐
              │  ← 0.5mm+ elbow (looks professional)
              └── Text
```

### Test Coverage

**New Test Class**: `TestIntelligentElbowGeneration` (7 tests)
- `test_min_elbow_height_constant_used`: Verify constant is respected
- `test_should_use_straight_line_logic`: Test decision function threshold
- `test_elbow_height_calculation`: Test displacement calculation helper
- `test_adjust_spacing_for_minimum_elbows`: Test enforcement logic
- `test_small_elbows_become_straight`: Verify < 0.5mm → straight
- `test_large_elbows_remain_elbows`: Verify >= 0.5mm → elbow
- `test_minimum_elbow_enforcement`: Verify spacing adjustment works end-to-end

**Test Results**: 89 tests passing (82 existing + 7 new)

### Files Modified

1. ✅ `stackup/core/graphics_models.py`:
   - Added MIN_ELBOW_HEIGHT_MM constant
   - Added min_elbow_height_mm field to GraphicalStackupConfig

2. ✅ `stackup/core/graphics_layout.py`:
   - Added _calculate_elbow_heights() helper
   - Added _should_use_straight_line() helper
   - Added _adjust_spacing_for_minimum_elbows() helper
   - Updated adjust_leader_lines() to use intelligent elbow logic
   - Added straight line creation path in adjustment loop

3. ✅ `tests/test_graphics_layout.py`:
   - Added TestIntelligentElbowGeneration class with 7 tests
   - Updated imports to include new constants and helpers

### Benefits

1. **Professional appearance**: No more silly-looking tiny elbows
2. **Automatic optimization**: Algorithm decides straight vs elbow based on size
3. **Configurable threshold**: min_elbow_height_mm can be adjusted per use case
4. **Clean visual hierarchy**: Leader lines are either clearly straight or clearly angled
5. **Maintained compatibility**: Existing layouts work unchanged (default 0.5mm threshold)

## Symmetric Elbow Spacing (Enhancement)

### Problem
The original intelligent elbow generation used linear distribution (top to bottom), which created asymmetric layouts. This looked unbalanced. Professional technical drawings should have symmetric, visually balanced leader lines.

### Solution: Symmetric Distribution from Center Layer
**Status**: ✅ Completed (December 2024)

**Implementation Strategy**:
1. **Find center layer**: `center_idx = total_groups // 2`
2. **Center layer gets 0 displacement**: Always straight line (visual anchor)
3. **Symmetric spacing**: Layers above/below center mirror each other
4. **Consistent spacing**: Always use `MIN_ELBOW_HEIGHT_MM` (0.5mm) as unit
5. **Perfect balance**: `displacement[center - n] = -displacement[center + n]`

### Visual Comparison

**Before (Linear Distribution)**:
```
L1: 0% of available height   ─────────  Text (top)
L2: 25%                       ───┐ ╱    Text
L3: 50%                       ─────┐ ╱  Text
L4: 75%                       ───────┐ ╱ Text
L5: 100%                      ─────────┘ Text (bottom)
```
**Result**: Asymmetric, unbalanced appearance

**After (Symmetric from Center)**:
```
L1: -1.0mm from center  ────┐ ╱      Text (up 1.0mm)
L2: -0.5mm from center  ──┐ ╱        Text (up 0.5mm)
L3:  0.0mm (CENTER)     ─────        Text (STRAIGHT)
L4: +0.5mm from center  ──┘ ╲        Text (down 0.5mm) ← mirrors L2
L5: +1.0mm from center  ────┘ ╲      Text (down 1.0mm) ← mirrors L1
```
**Result**: Symmetric, balanced, professional

### Technical Implementation

#### New Helper Function: `_calculate_symmetric_positions()`

**Location**: `stackup/core/graphics_layout.py`, lines 331-389

**Algorithm**:
```python
center_idx = total_groups // 2
spacing_unit = config.min_elbow_height_mm  # 0.5mm default

for i in range(total_groups):
    if i == center_idx:
        displacement = 0.0  # Center layer: straight
    elif i < center_idx:
        units_from_center = center_idx - i
        displacement = -units_from_center * spacing_unit  # Above: negative (up)
    else:
        units_from_center = i - center_idx
        displacement = units_from_center * spacing_unit  # Below: positive (down)
```

**Key Features**:
- Center is always index `total_groups // 2`
- Displacement is always a multiple of `MIN_ELBOW_HEIGHT_MM`
- Layers equidistant from center have equal but opposite displacements
- No dependency on available height - purely symmetric

#### Updated `adjust_leader_lines()` Flow

**Before**:
```python
# Linear distribution across available height
for i in range(total_groups):
    fraction = i / (total_groups - 1)
    new_y = first_rect_y + (available_height * fraction)

# Then enforce minimum spacing
new_positions = _adjust_spacing_for_minimum_elbows(...)
```

**After (simplified)**:
```python
# Calculate symmetric positions (already has minimum spacing built-in)
new_positions = _calculate_symmetric_positions(groups_to_adjust, elements, config)

# Calculate elbow heights
elbow_heights = _calculate_elbow_heights(groups_to_adjust, new_positions, elements, config)

# Create leaders (straight for center, elbows for others)
```

**Simplification**: Removed `_adjust_spacing_for_minimum_elbows()` call - no longer needed since symmetric positioning inherently enforces minimum spacing.

### Examples

#### Example 1: 5 Layers (Typical PCB - F.Cu, In1.Cu, In2.Cu, In3.Cu, B.Cu)

**Center**: Index 2 (In2.Cu)

**Displacements** (0.5mm unit):
```
L0 (F.Cu):   -1.0mm  (2 units up)
L1 (In1.Cu): -0.5mm  (1 unit up)
L2 (In2.Cu):  0.0mm  (CENTER - straight)
L3 (In3.Cu): +0.5mm  (1 unit down) ← mirrors L1
L4 (B.Cu):   +1.0mm  (2 units down) ← mirrors L0
```

**Perfect mirror symmetry**: L0 ↔ L4, L1 ↔ L3, L2 = center

#### Example 2: 7 Layers (High-density PCB)

**Center**: Index 3

**Displacements** (0.5mm unit):
```
L0: -1.5mm  (3 units up)
L1: -1.0mm  (2 units up)
L2: -0.5mm  (1 unit up)
L3:  0.0mm  (CENTER - straight)
L4: +0.5mm  (1 unit down) ← mirrors L2
L5: +1.0mm  (2 units down) ← mirrors L1
L6: +1.5mm  (3 units down) ← mirrors L0
```

**Perfect 3-way mirror symmetry**

#### Example 3: 3 Layers (Simple 2-layer PCB with ground plane)

**Center**: Index 1

**Displacements**:
```
L0: -0.5mm  (1 unit up)
L1:  0.0mm  (CENTER - straight)
L2: +0.5mm  (1 unit down) ← mirrors L0
```

**Minimal symmetric layout**

### Test Coverage

**New Test Class**: `TestSymmetricElbowSpacing` (4 tests)
- `test_symmetric_spacing_odd_layers_five`: Verify 5-layer symmetry
- `test_symmetric_spacing_center_is_straight`: Center always straight (3, 5, 7 layers)
- `test_symmetric_spacing_mirrors`: Verify mirror symmetry for 7-layer stackup
- `test_symmetric_positions_calculation`: Test helper function directly with expected values

**Test Results**: 93 tests passing (89 existing + 4 new)

### Files Modified

1. ✅ `stackup/core/graphics_layout.py`:
   - Added `_calculate_symmetric_positions()` helper function (lines 331-389)
   - Updated `adjust_leader_lines()` to use symmetric positioning
   - Removed old linear distribution code (lines 431-451, now replaced)
   - Simplified logic by removing redundant spacing adjustment

2. ✅ `tests/test_graphics_layout.py`:
   - Added `TestSymmetricElbowSpacing` class with 4 comprehensive tests
   - Tests verify center is straight, symmetry, and mirroring

3. ✅ `plan.md`:
   - Documented symmetric spacing algorithm

### Benefits

1. **Visual balance**: Symmetric appearance looks professional and intentional
2. **Center emphasis**: Straight center line creates natural visual anchor point
3. **Predictable**: Always know center will be straight, others will mirror
4. **Simpler code**: Removed complexity of spacing adjustment - built-in by design
5. **Mathematical elegance**: Clean formula: `displacement = (i - center) * unit`
6. **PCB-appropriate**: Matches typical PCB structure (center ground plane, symmetric copper layers)

### Constants Summary (Updated)

| Constant | Value | Purpose |
|----------|-------|---------|
| `MIN_ELBOW_HEIGHT_MM` | 0.5mm | Minimum vertical displacement for elbows (smaller = straight line) |
| `MIN_CALLOUT_SPACING_MM` | 8.8mm | Minimum vertical spacing between callouts |
| `CALLOUT_TEXT_PADDING_MM` | 1.0mm | Horizontal padding from leader to text |
| `DEFAULT_BASE_HEIGHT_MM` | 3.0mm | Base height for proportional mode |

## Conclusion

All visual enhancement features have been successfully implemented and tested. The plugin now provides:

1. **Three thickness modes** (uniform, proportional, scaled) for layer visualization
2. **Soldermask gap spacing** for visual layer separation
3. **Copper layer hatching** with 45-degree diagonal lines
4. **Intelligent elbow generation** that automatically creates professional-looking leader lines by avoiding tiny elbows (< 0.5mm)
5. **Symmetric elbow spacing** that creates balanced, visually appealing layouts with center layer always straight

The implementation uses constants instead of magic numbers, maintains copper as a 1.0 baseline for intuitive ratios, follows the existing architecture, maintains backward compatibility, and includes comprehensive unit test coverage (93 tests passing).

**Status**: ✅ Complete and ready for testing with live KiCad instance

**Latest Enhancements** (December 2024):
- Intelligent elbow generation - No more silly-looking tiny elbows!
- Symmetric spacing from center layer - Professional, balanced appearance!
