# Development Plans

## 1️⃣ Scale Feature - ✅ COMPLETE

See bottom of this file for archived scale feature plan.

---

## 2️⃣ Fix Text Spacing at Small Scales - ✅ COMPLETE

See bottom of this file for archived text spacing fix plan.

---

## 3️⃣ Fix Callout Horizontal Spacing with Aligned Text Column - READY TO IMPLEMENT

### Problem Summary

When many callouts require large vertical displacements, their 45° elbows consume most of the horizontal space budget (fixed at 20mm via `leader_line_length_mm`), causing the elbows to bunch together horizontally. While vertical spacing between callouts was recently fixed, horizontal spacing between elbow endpoints can still be problematically tight.

**Visual Example** (from user's screenshot):
```
Current behavior (fixed 20mm horizontal):

SOLDERMASK — 20.0µm ±2.0µm
    ╱
COPPER — 35.0µm ±3.5µm
  ╱
DIELECTRIC — 100.0µm ±10.0µm
 ╱
COPPER — 35.0µm ±3.5µm
╱
[stackup rectangle]

Problem: Elbows are very close horizontally (2-3mm apart),
creating visual crowding despite correct vertical spacing.
```

**Root Cause**:
- `leader_line_length_mm` is **fixed at 20.0mm** (default)
- For 45° elbows: `horizontal_budget = 20mm - initial_segment - diagonal_length`
- As `diagonal_length` increases (large vertical displacement), `remaining_horizontal` decreases
- Text moves **closer** to the graphic when elbows are large
- Result: Elbows bunch together horizontally

**Key Code Location**: `stackup/core/graphics_layout.py:589`
```python
remaining_horizontal = config.leader_line_length_mm - horizontal_len - angle_len
# ↑ As angle_len grows, remaining_horizontal shrinks → text moves left → crowding
```

### Design Decision: Aligned Text Column Approach

After discussion with user, selected approach: **Calculate maximum required leader length across all callouts, then use that length uniformly to create a clean, aligned text column.**

**Why This Approach**:
- ✅ Professional, clean appearance
- ✅ Text alignment makes reading easier
- ✅ All callouts get same horizontal space
- ✅ Naturally scales with vertical displacement needs
- ✅ No new configuration parameters needed (smart defaults)
- ✅ Preserves existing 45° elbow constraint logic

**Alternative Approaches Considered**:
1. **Ragged (variable X)**: Each callout extends just enough based on its vertical displacement
   - ❌ Text at different X positions looks unorganized
   - ✅ Minimal horizontal space usage

2. **Minimum guaranteed spacing**: Add horizontal gap enforcement between elbow endpoints
   - ❌ Complex collision detection in 2D
   - ❌ More complicated algorithm
   - ✅ Only extends where needed

### Architecture Analysis

#### Current Leader Line Calculation Flow

```
adjust_leader_lines(layout, config)
    ↓
For each callout:
    ↓
    Is vertical displacement < min_elbow_height_mm?
        YES → _create_straight_leader_line()
              • Simple horizontal line
              • Length = config.leader_line_length_mm (FIXED)
        NO  → _create_elbow_leader_line()
              • Three segments: horizontal + diagonal + horizontal
              • Total length = config.leader_line_length_mm (FIXED)
              • Distribution:
                - Initial horizontal: 40% of total
                - Diagonal: 45° angle (horizontal = vertical displacement)
                - Final horizontal: remaining budget
              • Problem: Final horizontal can be very short!
```

**Current Implementation** (`graphics_layout.py:574-609`):
```python
def _create_elbow_leader_line(...):
    # Direction based on which side of center
    if new_callout_y > rect_center_y:
        style = LeaderLineStyle.ANGLED_DOWN
    else:
        style = LeaderLineStyle.ANGLED_UP

    # Fixed distribution
    horizontal_len = config.leader_line_length_mm * 0.4  # 40% initial
    angle_len = abs(new_callout_y - rect_center_y)       # 45° diagonal
    remaining_horizontal = config.leader_line_length_mm - horizontal_len - angle_len
    #                      ↑ PROBLEM: Can be very small or even negative!

    # Create three segments
    segments = [
        Segment(start, horizontal_end),     # Initial horizontal
        Segment(horizontal_end, elbow_end), # 45° diagonal
        Segment(elbow_end, final_end)       # Final horizontal (may be tiny!)
    ]
```

#### Where Dimensions Are Used

**Config Definition** (`stackup/core/graphics_models.py:124`):
```python
leader_line_length_mm: float = 20.0  # Fixed horizontal distance from layer edge to text
```

**Layout Calculation** (`stackup/core/graphics_layout.py`):
- Line 211: Initial straight leader lines created with fixed length
- Lines 551-573: Straight leader lines (replacement) use fixed length
- Lines 574-609: Elbow leader lines use fixed length for total budget
- Line 236: Initial text X position = `layer_edge_x + config.leader_line_length_mm`

### Solution Design

#### Core Concept: Dynamic Maximum Leader Length

Calculate the **maximum leader length needed** across all callouts based on their vertical displacements, then use this length uniformly for all callouts.

**Formula**:
```
For each callout:
    vertical_displacement = abs(new_callout_y - rect_center_y)

    If vertical_displacement < min_elbow_height_mm:
        required_length = base_leader_length  # Straight line
    Else:
        # Elbow line needs: initial + diagonal + comfortable final segment
        initial_segment = base_leader_length * 0.4
        diagonal_segment = vertical_displacement  # 45° means horizontal = vertical
        min_final_segment = 5.0  # Comfortable space for final horizontal (new constant)
        required_length = initial_segment + diagonal_segment + min_final_segment

max_leader_length = max(required_length for all callouts)
effective_leader_length = max(max_leader_length, config.leader_line_length_mm)
```

**Result**: All callouts use `effective_leader_length`, ensuring:
- Text aligns in a clean vertical column
- All elbows have comfortable horizontal spacing
- Never shorter than configured minimum
- Automatically scales with vertical displacement needs

#### Implementation Strategy

**Phase 1: Add Helper Function**

Create new function to calculate required leader length for a given vertical displacement.

**Location**: `stackup/core/graphics_layout.py` (around line 520, before `adjust_leader_lines`)

```python
def _calculate_required_leader_length(
    vertical_displacement: float,
    base_leader_length: float,
    min_elbow_height: float,
    min_final_segment: float = 5.0
) -> float:
    """
    Calculate the leader line length required for a callout with given vertical displacement.

    For straight lines (displacement < min_elbow_height), returns base length.
    For elbow lines, calculates total length needed for:
      - Initial horizontal segment (40% of base)
      - 45° diagonal segment (length = vertical displacement)
      - Comfortable final horizontal segment (min_final_segment)

    Args:
        vertical_displacement: Absolute vertical distance from layer center to callout position
        base_leader_length: Base leader line length from config (20.0mm default)
        min_elbow_height: Minimum vertical displacement to create elbow (0.5mm default)
        min_final_segment: Minimum comfortable horizontal space after elbow (5.0mm default)

    Returns:
        Required leader line length in mm
    """
    if vertical_displacement < min_elbow_height:
        # Straight line - just use base length
        return base_leader_length
    else:
        # Elbow line - need space for all three segments
        initial_horizontal = base_leader_length * 0.4
        diagonal = vertical_displacement  # 45° angle: horizontal = vertical
        final_horizontal = min_final_segment
        return initial_horizontal + diagonal + final_horizontal
```

**Why This Works**:
- Straight lines: No extra space needed beyond base
- Elbow lines: Guarantees comfortable final segment regardless of diagonal length
- Preserves 40% initial segment distribution from current implementation
- New constant `min_final_segment` (5.0mm) ensures readable spacing

**Phase 2: Modify `adjust_leader_lines()`**

**Step 2.1**: Calculate maximum leader length before processing callouts

**Location**: `stackup/core/graphics_layout.py:528` (start of `adjust_leader_lines` function)

**Current code**:
```python
def adjust_leader_lines(
    layout: GraphicalStackupLayout, config: GraphicalStackupConfig
) -> GraphicalStackupLayout:
    """Adjust leader lines to avoid overlapping callouts using symmetric spreading."""
    # Existing collision detection and grouping...
    has_collisions = True
    iteration = 0
    max_iterations = 50
```

**New code** (insert after docstring, before main loop):
```python
def adjust_leader_lines(
    layout: GraphicalStackupLayout, config: GraphicalStackupConfig
) -> GraphicalStackupLayout:
    """Adjust leader lines to avoid overlapping callouts using symmetric spreading."""

    # PHASE 2.1: Calculate maximum required leader length across all callouts
    # This ensures all text aligns at the same X position (aligned column)

    # Find the stackup rectangle center Y for displacement calculations
    if not layout.elements:
        # No elements, just return as-is
        return layout

    # Assume first element is main stackup rectangle (established pattern in codebase)
    rect_center_y = layout.elements[0].center_y  # Center of stackup rectangle

    # Scan all current callout positions to find maximum displacement
    max_required_length = config.leader_line_length_mm  # Start with configured minimum

    for callout in layout.callouts:
        vertical_displacement = abs(callout.position_y - rect_center_y)
        required_length = _calculate_required_leader_length(
            vertical_displacement,
            config.leader_line_length_mm,
            config.min_elbow_height_mm,
            min_final_segment=5.0  # New constant for comfortable final spacing
        )
        max_required_length = max(max_required_length, required_length)

    # Create effective config with adjusted leader length
    effective_config = config.model_copy()
    effective_config.leader_line_length_mm = max_required_length

    # Use effective_config for all subsequent operations
    # (Continue with existing collision detection logic, but use effective_config)

    has_collisions = True
    iteration = 0
    max_iterations = 50
```

**Step 2.2**: Update leader line creation calls to use `effective_config`

**Locations**: Throughout `adjust_leader_lines` function

**Changes**:
1. Line ~551-573 (straight line creation): Change `config` to `effective_config`
2. Line ~574-609 (elbow line creation): Change `config` to `effective_config`
3. All other references to `config` within loop: Change to `effective_config`

**Note**: Keep original `config` parameter for collision detection thresholds, but use `effective_config` for dimensional calculations.

**Step 2.3**: Update collision detection to use effective config

**Location**: Line ~529 (collision detection call)

```python
# Before:
collision_mask = detect_callout_collisions(layout, config)

# After:
collision_mask = detect_callout_collisions(layout, effective_config)
```

**Step 2.4**: Add debug logging (optional, for verification)

```python
# After calculating max_required_length:
if max_required_length > config.leader_line_length_mm:
    # Length was extended - log for debugging
    print(f"DEBUG: Extended leader length from {config.leader_line_length_mm:.1f}mm "
          f"to {max_required_length:.1f}mm for aligned text column")
```

#### Constants and Configuration

**New Constant**:
- `MIN_FINAL_SEGMENT_MM = 5.0`: Minimum comfortable horizontal space after elbow

**Why 5.0mm?**
- Provides visual breathing room after the elbow
- Roughly 1.67× the default text height (3.0mm)
- Scales with overall scale parameter
- Can be tuned based on testing results

**Should It Be Configurable?**
- **Decision**: No, keep as internal constant for now
- **Reasoning**: User said "smart defaults, may add tuning later"
- **Future**: Could expose as `min_final_horizontal_mm` config field if users request it

### Implementation Plan

#### Phase 1: Add Helper Function

**Task 1.1**: Create `_calculate_required_leader_length()` function
- **File**: `stackup/core/graphics_layout.py`
- **Location**: Around line 520 (before `adjust_leader_lines`)
- **Code**: See solution design above
- **Testing**: Unit test with various vertical displacements

**Task 1.2**: Add constant for minimum final segment
- **Location**: Top of `graphics_layout.py` with other constants
- **Code**: `MIN_FINAL_SEGMENT_MM = 5.0  # Minimum horizontal space after elbow`

#### Phase 2: Modify `adjust_leader_lines()`

**Task 2.1**: Add maximum leader length calculation
- **Location**: Start of `adjust_leader_lines`, after docstring
- **Logic**:
  1. Extract stackup rectangle center Y
  2. Scan all callouts
  3. Calculate required length for each
  4. Find maximum
  5. Create `effective_config` with adjusted length

**Task 2.2**: Update all `config` references to `effective_config`
- **Locations**:
  - Line ~551-573: Straight line creation
  - Line ~574-609: Elbow line creation
  - Line ~529: Collision detection call
  - Any other dimensional calculations in the loop

**Task 2.3**: Add debug logging
- **Purpose**: Verify length extension is working
- **Location**: After calculating `max_required_length`
- **Temporary**: Can be removed after testing

#### Phase 3: Update Unit Tests

**Task 3.1**: Identify affected tests

Run test suite to find tests that assert specific leader line coordinates:
```bash
pytest tests/test_graphics_layout.py -v
```

Expected affected tests (need coordinate updates):
- Tests that verify exact leader line endpoint X positions
- Tests that check specific callout text X coordinates
- Tests that validate leader line segment positions

**Task 3.2**: Update test assertions

For each affected test:
1. Understand what it's testing (behavior vs coordinates)
2. If testing behavior (e.g., "center callout is straight"), keep test
3. If testing coordinates, update to new expected values
4. Document why coordinates changed in test comments

**Task 3.3**: Add new test for aligned text column

**New Test**: `test_aligned_text_column_with_large_displacements`

```python
def test_aligned_text_column_with_large_displacements():
    """
    Verify that all callout text aligns at the same X position when
    callouts have varying vertical displacements.

    This test ensures the dynamic leader length calculation works correctly
    to create an aligned text column.
    """
    # Create stackup with many layers requiring large vertical displacements
    stackup_data = StackupData(
        layers=[
            Layer(f"L{i}", LayerType.COPPER, thickness_um=35.0, tolerance_um=3.5)
            for i in range(10)  # 10 copper layers
        ],
        total_thickness_mm=0.175
    )

    config = GraphicalStackupConfig(
        scale_mm=100.0,
        thickness_mode=ThicknessMode.UNIFORM,
        uniform_layer_height_mm=3.0,
        leader_line_length_mm=20.0,  # Base length
        min_callout_spacing_mm=8.0,
        visualization_style=VisualizationStyle.GRAPHICAL
    )

    layout, effective_config = calculate_graphical_layout(stackup_data, config)
    layout = adjust_leader_lines(layout, effective_config)

    # Extract all callout text X positions
    text_x_positions = [callout.position_x for callout in layout.callouts]

    # Verify all text aligns at the same X position (within floating point tolerance)
    assert len(set(round(x, 6) for x in text_x_positions)) == 1, \
        "All callout text should align at the same X position (aligned column)"

    # Verify leader length was extended beyond base (due to large vertical displacements)
    max_x = max(text_x_positions)
    layer_edge_x = layout.elements[0].position_x + layout.elements[0].width / 2
    actual_leader_length = max_x - layer_edge_x

    assert actual_leader_length > config.leader_line_length_mm, \
        f"Leader length should be extended beyond {config.leader_line_length_mm}mm base, " \
        f"got {actual_leader_length:.1f}mm"
```

**Task 3.4**: Add test for minimum final segment

```python
def test_elbow_final_segment_minimum():
    """
    Verify that elbow leader lines maintain a minimum comfortable horizontal
    segment after the 45° diagonal, even with large vertical displacements.
    """
    # Test with single callout requiring large vertical displacement
    stackup_data = create_simple_stackup(num_layers=5)

    config = GraphicalStackupConfig(
        leader_line_length_mm=20.0,
        min_elbow_height_mm=0.5
    )

    layout, effective_config = calculate_graphical_layout(stackup_data, config)
    layout = adjust_leader_lines(layout, effective_config)

    # Find callout with largest vertical displacement
    rect_center_y = layout.elements[0].center_y
    max_displacement_callout = max(
        layout.callouts,
        key=lambda c: abs(c.position_y - rect_center_y)
    )

    # Get its leader line
    leader = next(l for l in layout.leader_lines if l.to_layer_name == max_displacement_callout.layer_name)

    # For three-segment elbow line, last segment is final horizontal
    if len(leader.segments) == 3:
        final_segment = leader.segments[2]
        final_horizontal_length = abs(final_segment.end_x - final_segment.start_x)

        assert final_horizontal_length >= 5.0, \
            f"Final horizontal segment should be at least 5.0mm, got {final_horizontal_length:.1f}mm"
```

#### Phase 4: Visual Verification

**Task 4.1**: Generate test outputs with problematic stackup

Using the user's problematic stackup (if available) or create similar dense stackup:

```bash
# Generate SVG exports at scale that showed the problem
python3 -m stackup.cli.main --visualization graphical --scale 100 --export-svg before_fix.svg

# After implementing fix:
python3 -m stackup.cli.main --visualization graphical --scale 100 --export-svg after_fix.svg
```

**Task 4.2**: Manual inspection checklist

For each generated SVG:
- [ ] All callout text aligns vertically (same X position)
- [ ] No horizontal crowding between elbows
- [ ] Final horizontal segments after elbows are comfortable (visually ~5mm)
- [ ] Text is readable and well-spaced
- [ ] Symmetric layout is preserved
- [ ] Overall appearance is professional

**Task 4.3**: Measure actual dimensions

Use SVG inspection tools to verify:
- Text X positions (should be identical)
- Leader line total lengths (should be consistent)
- Final segment lengths (should be ≥ 5mm)
- Spacing between elbow endpoints

#### Phase 5: Edge Cases & Validation

**Task 5.1**: Test with various stackup densities

```bash
# Sparse stackup (2-4 layers)
python3 -m stackup.cli.main --visualization graphical --scale 100

# Medium stackup (6-8 layers)
python3 -m stackup.cli.main --visualization graphical --scale 100

# Dense stackup (10+ layers)
python3 -m stackup.cli.main --visualization graphical --scale 100
```

**Expected Behavior**:
- Sparse: May not extend leader length (vertical displacements small)
- Medium: Moderate extension
- Dense: Significant extension to accommodate large displacements

**Task 5.2**: Test with different thickness modes

```bash
# UNIFORM mode
python3 -m stackup.cli.main --thickness-mode uniform --scale 100

# PROPORTIONAL mode
python3 -m stackup.cli.main --thickness-mode proportional --scale 100

# SCALED mode
python3 -m stackup.cli.main --thickness-mode scaled --scale 100
```

**Expected**: Feature should work identically across all modes

**Task 5.3**: Test with different scales

```bash
# Small scale (where previous spacing issue occurred)
python3 -m stackup.cli.main --scale 50

# Medium scale
python3 -m stackup.cli.main --scale 100

# Large scale
python3 -m stackup.cli.main --scale 200
```

**Expected**: Aligned column behavior should be consistent at all scales

**Task 5.4**: Extreme edge case - Single layer

```bash
# Single copper layer stackup
python3 -m stackup.cli.main --visualization graphical
```

**Expected**: Should handle gracefully (center callout straight, no extension needed)

#### Phase 6: Performance & Correctness

**Task 6.1**: Verify no performance regression

The additional scan through callouts adds O(n) complexity, which is acceptable.

**Benchmark**:
```python
import time

# Test with dense stackup (worst case)
stackup = create_stackup_with_n_layers(50)  # 50 layers
config = GraphicalStackupConfig(scale_mm=100.0)

start = time.time()
layout = calculate_graphical_layout(stackup, config)
layout = adjust_leader_lines(layout, config)
end = time.time()

print(f"Time for 50-layer stackup: {(end - start) * 1000:.2f}ms")
```

**Expected**: < 100ms even for 50 layers (scan is trivial compared to layout calculations)

**Task 6.2**: Verify no memory leaks

```python
# Run layout calculation 1000 times
for i in range(1000):
    layout = calculate_graphical_layout(stackup_data, config)
    layout = adjust_leader_lines(layout, config)

# Check memory usage remains stable
```

**Task 6.3**: Verify thread safety (future consideration)

Current implementation is stateless, so should be thread-safe.

#### Phase 7: Documentation

**Task 7.1**: Add inline code comments

**Locations**:
1. `_calculate_required_leader_length()`: Explain formula and reasoning
2. `adjust_leader_lines()`: Explain maximum calculation logic
3. `MIN_FINAL_SEGMENT_MM`: Explain why 5.0mm was chosen

**Task 7.2**: Update function docstrings

**`adjust_leader_lines()` docstring update**:
```python
def adjust_leader_lines(
    layout: GraphicalStackupLayout, config: GraphicalStackupConfig
) -> GraphicalStackupLayout:
    """
    Adjust leader lines to avoid overlapping callouts using symmetric spreading.

    This function:
    1. Calculates maximum required leader length based on all callout vertical
       displacements to ensure aligned text column
    2. Detects collisions between callouts (spacing < min_callout_spacing_mm)
    3. Groups colliding callouts by proximity
    4. Redistributes callouts symmetrically around center with minimum spacing
    5. Recreates leader lines with adjusted positions (straight or 45° elbow)

    The leader length calculation ensures all callout text aligns at the same
    X position, creating a professional appearance and preventing horizontal
    crowding of elbow endpoints.

    Args:
        layout: Initial graphical stackup layout with potential collisions
        config: Configuration with spacing and dimension parameters

    Returns:
        Layout with adjusted leader lines ensuring minimum spacing and aligned text
    """
```

**Task 7.3**: Update CLAUDE.md

Add section under "Known Issues & Limitations":

```markdown
### Callout Horizontal Spacing (FIXED)

**Previous Issue**: When many callouts required large vertical displacements (e.g., dense stackups with 10+ layers), the 45° elbows would bunch together horizontally because leader line length was fixed at 20mm.

**Root Cause**: Fixed `leader_line_length_mm` meant that large diagonal segments consumed most of the horizontal budget, leaving little space for the final horizontal segment. This caused elbow endpoints to be very close horizontally (2-3mm), creating visual crowding.

**Fix Applied**: Dynamic leader length calculation with aligned text column approach:
- Scans all callout vertical displacements before creating leader lines
- Calculates maximum required leader length to ensure comfortable final horizontal segment (5.0mm minimum)
- Uses this maximum length uniformly for all callouts
- Result: All text aligns at the same X position, professional appearance, no horizontal crowding

**See also**:
- `stackup/core/graphics_layout.py:_calculate_required_leader_length()` for calculation logic
- `stackup/core/graphics_layout.py:adjust_leader_lines()` for implementation
```

Add section under "Architecture Overview":

```markdown
### Aligned Text Column Feature

When multiple callouts have varying vertical displacements, the plugin automatically calculates the appropriate leader line length to create an aligned text column. This prevents horizontal crowding of 45° elbows while maintaining a professional, organized appearance.

**How It Works**:
1. Before adjusting leader lines, scan all callout positions
2. For each callout, calculate required leader length based on vertical displacement
3. Find maximum required length across all callouts
4. Use this maximum uniformly for all callouts
5. Result: Text aligns at consistent X position

**Configuration**: No user-facing parameters needed (smart defaults). The base `leader_line_length_mm` (20.0mm default) serves as the minimum; actual length extends as needed.
```

**Task 7.4**: Update plan.md (this file)

Mark task as complete and move to archived section.

### Testing Strategy

#### Unit Tests

**Existing Tests to Verify** (should still pass):
```python
# Symmetric spacing tests
test_symmetric_spacing_odd_layers_five()
test_symmetric_spacing_even_layers_six()
test_symmetric_spacing_center_is_straight()
test_symmetric_spacing_mirrors()

# Leader line tests (may need coordinate updates)
test_create_straight_leader_line()
test_create_elbow_leader_line_up()
test_create_elbow_leader_line_down()

# Layout tests
test_graphical_layout_basic_structure()
test_leader_line_adjustment()
```

**New Tests to Add**:
```python
# Aligned column feature
test_aligned_text_column_with_large_displacements()
test_elbow_final_segment_minimum()
test_calculate_required_leader_length_straight()
test_calculate_required_leader_length_elbow()
test_leader_length_extension_with_dense_stackup()

# Edge cases
test_aligned_column_single_layer()
test_aligned_column_sparse_stackup()
test_aligned_column_all_thickness_modes()
test_aligned_column_various_scales()
```

#### Integration Tests

Manual CLI testing with various configurations:

```bash
# Dense stackup at scale that triggered issue
pytest tests/test_integration.py::test_dense_stackup_graphical

# All thickness modes with dense stackup
pytest tests/test_integration.py -k "thickness_mode and dense"

# SVG export verification
pytest tests/test_integration.py::test_svg_export_aligned_column
```

#### Visual Tests

**Checklist for Manual Inspection**:

For each generated SVG:
- [ ] Text alignment: All callout labels at same X coordinate
- [ ] Horizontal spacing: No crowding between elbow endpoints
- [ ] Final segments: Comfortable space (≥5mm) after each elbow
- [ ] Symmetry: Layout remains symmetric around center
- [ ] Readability: Text is clear and well-spaced
- [ ] Professional appearance: Clean, organized look

**Test Configurations**:
1. Dense 10-layer stackup at 100mm scale
2. Dense 10-layer stackup at 50mm scale (previously problematic)
3. Sparse 4-layer stackup at 100mm scale
4. Mixed copper/dielectric with soldermask at 150mm scale

### Success Criteria

✅ **Aligned Text Column**: All callout text aligns at the same X position

✅ **No Horizontal Crowding**: Elbow endpoints have comfortable horizontal spacing

✅ **Minimum Final Segment**: All elbow lines have ≥5mm final horizontal segment

✅ **No Regressions**: All existing unit tests pass (after coordinate updates)

✅ **Scale Invariant**: Feature works consistently at all scales (50mm to 200mm)

✅ **Mode Independent**: Works identically across UNIFORM, PROPORTIONAL, and SCALED thickness modes

✅ **Visual Quality**: Professional, organized appearance in generated SVGs

✅ **Performance**: No significant performance impact (< 10% overhead)

✅ **Documented**: Code comments, docstrings, and CLAUDE.md updated

### Rollback Plan

If critical issues arise:

1. **Immediate Rollback**:
   - Revert `adjust_leader_lines()` changes
   - Remove `_calculate_required_leader_length()` function
   - Restore original fixed `leader_line_length_mm` behavior

2. **Partial Rollback**:
   - Keep helper function for future use
   - Add configuration flag: `enable_aligned_column: bool = False`
   - Gate the feature behind flag for testing

3. **Alternative Approach**:
   - If aligned column doesn't work well, try "minimum gap" approach instead
   - Implement horizontal spacing enforcement between elbow endpoints
   - More complex but may handle edge cases better

### Future Enhancements (Out of Scope)

**Possible Future Features**:
1. **User-configurable alignment**:
   - Config option: `text_alignment: Literal["left", "aligned", "justified"]`
   - "left" = current behavior, "aligned" = this feature, "justified" = distribute evenly

2. **Adaptive final segment**:
   - Scale final segment with text size
   - Formula: `min_final_segment = text_size_mm * 1.67`

3. **Smart wrapping**:
   - For extremely dense stackups, wrap to multiple columns
   - Left side and right side callouts

4. **Variable elbow angles**:
   - Support angles other than 45° (e.g., 30°, 60°)
   - Could save horizontal space or improve aesthetics

---

## Archived: Text Spacing at Small Scales Fix (✅ COMPLETE)

### Overview
Fixed critical bug where callout spacing algorithm used wrong measurement value (`min_elbow_height_mm` = 0.3mm instead of `min_callout_spacing_mm` = 4.0mm), causing severe text overlaps at small scales.

### Solution
Changed `_calculate_symmetric_positions()` in `stackup/core/graphics_layout.py:463` to use `config.min_callout_spacing_mm` as the spacing unit instead of `config.min_elbow_height_mm`.

### Results
- ✅ All 111 unit tests pass
- ✅ Zero spacing violations at 50mm scale (verified with diagnostics)
- ✅ Text spacing now scale-invariant
- ✅ Guaranteed to meet minimum spacing thresholds

### Files Modified
- `stackup/core/graphics_layout.py`: Line 463 spacing unit fix
- `stackup/core/diagnostics.py`: Added diagnostic utilities
- `tests/test_graphics_layout.py`: Updated test cases

---

## Archived: Scale Feature Implementation Plan (✅ COMPLETE)

### Overview
Add a scale parameter to control the overall size of generated cross-section drawings. The scale is specified as the desired **total height** in mm, and all dimensions scale proportionally to maintain aspect ratio.

### Design Goals
- **User-friendly**: Specify desired height in mm (e.g., `--scale 150` = 150mm tall cross-section)
- **Maintains aspect ratio**: Width, text size, line widths, and all other dimensions scale proportionally
- **GUI-ready**: Configuration field that can be easily exposed in a future GUI dialog
- **Mode-specific**: Applies to graphical mode only (cross-section drawings)

### Architecture Overview

#### Current Dimension Flow
```
CLI args → GraphicalStackupConfig → graphics_layout.py → graphics_renderer.py
```

#### Where Dimensions Are Defined
- **Config**: `GraphicalStackupConfig` in `stackup/core/graphics_models.py`
  - `uniform_layer_height_mm = 3.0` (base layer height)
  - `layer_width_mm = 50.0` (stackup rectangle width)
  - `max_total_height_mm = 100.0` (max height for SCALED thickness mode)
  - `leader_line_length_mm = 15.0`
  - `callout_text_size_mm = 3.0`
  - `soldermask_gap_mm = 0.3`
  - `copper_hatch_spacing_mm = 2.0`

- **Layout**: `graphics_layout.py` calculates actual dimensions based on config
  - `_calculate_layer_heights()` determines individual layer heights
  - `calculate_graphical_layout()` computes total layout dimensions

### Implementation Details

#### Config Updates
- Added field: `scale_mm: Optional[float] = None`
- Minimum floors applied to spacing parameters when scaling:
  - `min_callout_spacing_mm`: floor of 4.0mm
  - `min_elbow_height_mm`: floor of 0.3mm

#### Layout Logic
- Two-pass calculation:
  1. Calculate with default dimensions to determine base height
  2. If `scale_mm` specified, apply scale factor and recalculate
- Helper function `_scale_config()` multiplies all dimension fields by scale factor

#### CLI Support
- Added `--scale MM` argument to specify desired height in mm
- Works with all thickness modes (UNIFORM, PROPORTIONAL, SCALED)
- Works with SVG export

#### Testing
- Comprehensive test suite covers scaling at various values
- Tests verify:
  - Exact height matching
  - Aspect ratio preservation
  - Element count preservation
  - Origin position preservation
  - Interaction with all thickness modes and features
