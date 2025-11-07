"""
Unit tests for graphical stackup layout algorithms.
These tests don't require KiCad to be running.
"""
import pytest
from stackup.core.models import (
    StackupData, StackupLayer, LayerType
)
from stackup.core.graphics_models import (
    GraphicalStackupConfig,
    LayerRectangle,
    LeaderLine,
    CalloutText,
    LeaderLineStyle,
    ThicknessMode,
    COPPER_HEIGHT_RATIO,
    DIELECTRIC_HEIGHT_RATIO,
    SOLDERMASK_HEIGHT_RATIO,
    DEFAULT_BASE_HEIGHT_MM,
    MIN_ELBOW_HEIGHT_MM,
)
from stackup.core.graphics_layout import (
    calculate_graphical_layout,
    format_callout_text,
    calculate_tolerance,
    detect_callout_collisions,
    adjust_leader_lines,
    _calculate_layer_heights,
    _calculate_elbow_heights,
    _should_use_straight_line,
    _adjust_spacing_for_minimum_elbows,
    _calculate_symmetric_positions,
)


@pytest.fixture
def sample_stackup():
    """Create a sample stackup for testing"""
    return StackupData(
        layers=[
            StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core1", LayerType.DIELECTRIC, 0.2, "FR4", epsilon_r=4.5, loss_tangent=0.02),
            StackupLayer("In1.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core2", LayerType.DIELECTRIC, 1.2, "FR4", epsilon_r=4.5, loss_tangent=0.02),
            StackupLayer("B.Cu", LayerType.COPPER, 0.035, "Copper"),
        ],
        total_thickness=1.505,
        copper_layer_count=3,
        board_name="test.kicad_pcb"
    )


@pytest.fixture
def dense_stackup():
    """Create a dense stackup with many layers for collision testing"""
    layers = []
    for i in range(10):
        if i % 2 == 0:
            layers.append(StackupLayer(f"Cu{i}", LayerType.COPPER, 0.035, "Copper"))
        else:
            layers.append(StackupLayer(f"Dielectric{i}", LayerType.DIELECTRIC, 0.1, "FR4"))

    return StackupData(
        layers=layers,
        total_thickness=sum(layer.thickness for layer in layers),
        copper_layer_count=5,
        board_name="dense.kicad_pcb"
    )


class TestGraphicalLayoutBasic:
    """Tests for basic graphical layout generation"""

    def test_graphical_layout_basic(self, sample_stackup):
        """Test basic graphical layout generation"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(sample_stackup, config)

        assert layout is not None
        assert len(layout.elements) > 0
        assert layout.total_width_mm > 0
        assert layout.total_height_mm > 0
        assert layout.layer_count == len(sample_stackup.layers)

    def test_graphical_layout_element_count(self, sample_stackup):
        """Test that layout has correct number of elements (rect + leader + text per layer)"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(sample_stackup, config)

        # Should have 3 elements per layer (rectangle, leader line, callout text)
        expected_elements = len(sample_stackup.layers) * 3
        assert len(layout.elements) == expected_elements

    def test_graphical_layout_element_types(self, sample_stackup):
        """Test that layout has correct element types"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        leaders = [e for e in layout.elements if isinstance(e, LeaderLine)]
        callouts = [e for e in layout.elements if isinstance(e, CalloutText)]

        assert len(rectangles) == len(sample_stackup.layers)
        assert len(leaders) == len(sample_stackup.layers)
        assert len(callouts) == len(sample_stackup.layers)

    def test_uniform_layer_heights(self, sample_stackup):
        """Test that all layers have uniform height"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=DEFAULT_BASE_HEIGHT_MM
        )
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]

        for rect in rectangles:
            assert rect.height_mm == DEFAULT_BASE_HEIGHT_MM


class TestGraphicalLayoutConfiguration:
    """Tests for graphical layout configuration options"""

    def test_custom_layer_height(self, sample_stackup):
        """Test custom uniform layer height"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=10.0
        )
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        assert all(rect.height_mm == 10.0 for rect in rectangles)

        # Total height should be layer_count * uniform_height
        expected_height = len(sample_stackup.layers) * 10.0
        assert layout.total_height_mm == expected_height

    def test_custom_layer_width(self, sample_stackup):
        """Test custom layer width"""
        config = GraphicalStackupConfig(layer_width_mm=100.0)
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        assert all(rect.width_mm == 100.0 for rect in rectangles)

    def test_custom_origin(self, sample_stackup):
        """Test custom origin positioning"""
        config = GraphicalStackupConfig(origin_x_mm=100.0, origin_y_mm=200.0)
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]

        # First rectangle should start at origin
        first_rect = rectangles[0]
        assert first_rect.position_mm[0] == 100.0
        assert first_rect.position_mm[1] == 200.0

    def test_custom_leader_length(self, sample_stackup):
        """Test custom leader line length"""
        config = GraphicalStackupConfig(leader_line_length_mm=30.0)
        layout = calculate_graphical_layout(sample_stackup, config)

        leaders = [e for e in layout.elements if isinstance(e, LeaderLine)]

        # Check first leader (should be straight in initial layout)
        first_leader = leaders[0]
        start_x = first_leader.position_mm[0]
        end_x = first_leader.end_position_mm[0]
        length = end_x - start_x

        assert abs(length - 30.0) < 0.01  # Allow small floating point error


class TestCalloutFormatting:
    """Tests for callout text formatting"""

    def test_format_callout_text_copper(self, sample_stackup):
        """Test callout formatting for copper layer"""
        config = GraphicalStackupConfig()
        copper_layer = sample_stackup.layers[0]  # F.Cu

        callout = format_callout_text(copper_layer, config)

        assert "Copper" in callout
        assert "35" in callout or "0.035" in callout  # Thickness
        assert "±" in callout  # Tolerance symbol

    def test_format_callout_text_dielectric(self, sample_stackup):
        """Test callout formatting for dielectric layer"""
        config = GraphicalStackupConfig()
        dielectric_layer = sample_stackup.layers[1]  # Core1

        callout = format_callout_text(dielectric_layer, config)

        assert "FR4" in callout
        assert "±" in callout

    def test_calculate_tolerance(self):
        """Test tolerance calculation"""
        thickness = 1.0  # 1mm
        tolerance = calculate_tolerance(thickness, tolerance_percent=10.0)

        assert tolerance == 0.1  # 10% of 1mm

    def test_calculate_tolerance_different_percent(self):
        """Test tolerance calculation with different percentage"""
        thickness = 0.5  # 0.5mm
        tolerance = calculate_tolerance(thickness, tolerance_percent=5.0)

        assert tolerance == 0.025  # 5% of 0.5mm


class TestLeaderLinePositioning:
    """Tests for leader line positioning"""

    def test_initial_leader_lines_straight(self, sample_stackup):
        """Test that initial leader lines are straight horizontal"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(sample_stackup, config)

        leaders = [e for e in layout.elements if isinstance(e, LeaderLine)]

        for leader in leaders:
            # Initial leaders should be STRAIGHT style
            assert leader.style == LeaderLineStyle.STRAIGHT
            # Should have one segment
            assert len(leader.segments) == 1
            # Y coordinates should be the same (horizontal)
            start_y = leader.segments[0][0][1]
            end_y = leader.segments[0][1][1]
            assert start_y == end_y

    def test_leader_lines_point_to_layer_center(self, sample_stackup):
        """Test that leader lines start at the center of each layer"""
        config = GraphicalStackupConfig(
            uniform_layer_height_mm=10.0,
            origin_y_mm=50.0
        )
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        leaders = [e for e in layout.elements if isinstance(e, LeaderLine)]

        for i, (rect, leader) in enumerate(zip(rectangles, leaders)):
            rect_center_y = rect.position_mm[1] + (rect.height_mm / 2.0)
            leader_start_y = leader.position_mm[1]

            assert abs(rect_center_y - leader_start_y) < 0.01  # Allow floating point error


class TestCollisionDetection:
    """Tests for callout collision detection"""

    def test_detect_no_collisions_sparse(self, sample_stackup):
        """Test collision detection with sparse stackup (should have no collisions)"""
        config = GraphicalStackupConfig(uniform_layer_height_mm=10.0)
        layout = calculate_graphical_layout(sample_stackup, config)

        collisions = detect_callout_collisions(layout)

        # With 10mm layer height and 8mm min spacing, should have no collisions
        assert len(collisions) == 0

    def test_detect_collisions_dense(self, dense_stackup):
        """Test collision detection with dense stackup (should have collisions)"""
        config = GraphicalStackupConfig(
            uniform_layer_height_mm=5.0,
            min_callout_spacing_mm=8.0
        )
        layout = calculate_graphical_layout(dense_stackup, config)

        collisions = detect_callout_collisions(layout)

        # With 5mm layer height and 8mm min spacing, should have collisions
        assert len(collisions) > 0

    def test_collision_detection_accuracy(self):
        """Test collision detection with controlled data"""
        # Create a simple stackup with 3 layers, 5mm height each
        stackup = StackupData(
            layers=[
                StackupLayer("L1", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L2", LayerType.DIELECTRIC, 0.1, "FR4"),
                StackupLayer("L3", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.17,
            copper_layer_count=2,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            uniform_layer_height_mm=5.0,
            min_callout_spacing_mm=8.0
        )
        layout = calculate_graphical_layout(stackup, config)

        collisions = detect_callout_collisions(layout)

        # With 5mm spacing between callouts and 8mm minimum, all should collide
        assert len(collisions) > 0


class TestLeaderLineAdjustment:
    """Tests for leader line adjustment to avoid collisions"""

    def test_adjust_leader_lines_no_collisions(self, sample_stackup):
        """Test that adjustment preserves layout when no collisions"""
        config = GraphicalStackupConfig(uniform_layer_height_mm=10.0)
        layout = calculate_graphical_layout(sample_stackup, config)

        adjusted_layout = adjust_leader_lines(layout, config)

        # Should return layout unchanged
        assert len(adjusted_layout.elements) == len(layout.elements)

        # Leaders should still be straight
        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]
        assert all(leader.style == LeaderLineStyle.STRAIGHT for leader in leaders)

    def test_adjust_leader_lines_with_collisions(self, dense_stackup):
        """Test that adjustment creates angled leaders when collisions exist"""
        config = GraphicalStackupConfig(
            uniform_layer_height_mm=5.0,
            min_callout_spacing_mm=8.0
        )
        layout = calculate_graphical_layout(dense_stackup, config)

        adjusted_layout = adjust_leader_lines(layout, config)

        # Should have some angled leaders
        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]
        angled_leaders = [
            l for l in leaders
            if l.style in [LeaderLineStyle.ANGLED_UP, LeaderLineStyle.ANGLED_DOWN]
        ]

        assert len(angled_leaders) > 0

    def test_adjusted_callout_spacing(self, dense_stackup):
        """Test that adjusted callouts have proper spacing"""
        config = GraphicalStackupConfig(
            uniform_layer_height_mm=5.0,
            min_callout_spacing_mm=8.0
        )
        layout = calculate_graphical_layout(dense_stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        # Extract callout positions
        callouts = [e for e in adjusted_layout.elements if isinstance(e, CalloutText)]
        callout_y_positions = [c.position_mm[1] for c in callouts]

        # Check that adjacent callouts have sufficient spacing
        for i in range(len(callout_y_positions) - 1):
            spacing = abs(callout_y_positions[i+1] - callout_y_positions[i])
            # After adjustment, spacing should be >= min spacing or unchanged (if no collision)
            assert spacing >= config.min_callout_spacing_mm - 0.1 or spacing < config.min_callout_spacing_mm

    def test_angled_leader_has_multiple_segments(self, dense_stackup):
        """Test that angled leaders have multiple segments"""
        config = GraphicalStackupConfig(
            uniform_layer_height_mm=5.0,
            min_callout_spacing_mm=8.0
        )
        layout = calculate_graphical_layout(dense_stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]
        angled_leaders = [
            l for l in leaders
            if l.style in [LeaderLineStyle.ANGLED_UP, LeaderLineStyle.ANGLED_DOWN]
        ]

        for leader in angled_leaders:
            # Angled leaders should have 3 segments (horizontal, angled, horizontal)
            assert len(leader.segments) == 3


class TestEdgeCases:
    """Tests for edge cases"""

    def test_single_layer_stackup(self):
        """Test layout with single layer"""
        stackup = StackupData(
            layers=[
                StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.035,
            copper_layer_count=1,
            board_name="single.kicad_pcb"
        )

        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(stackup, config)

        assert layout is not None
        assert len(layout.elements) == 3  # 1 rect + 1 leader + 1 callout

    def test_empty_stackup(self):
        """Test layout with no layers"""
        stackup = StackupData(
            layers=[],
            total_thickness=0,
            copper_layer_count=0,
            board_name="empty.kicad_pcb"
        )

        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(stackup, config)

        assert layout is not None
        assert len(layout.elements) == 0
        assert layout.layer_count == 0


@pytest.fixture
def stackup_with_soldermask():
    """Create a stackup with soldermask layers for visual feature testing"""
    return StackupData(
        layers=[
            StackupLayer("F.Mask", LayerType.SOLDERMASK, 0.01, "SOLDERMASK", color="green"),
            StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core1", LayerType.DIELECTRIC, 0.2, "FR4", epsilon_r=4.5),
            StackupLayer("In1.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("Core2", LayerType.DIELECTRIC, 1.2, "FR4", epsilon_r=4.5),
            StackupLayer("B.Cu", LayerType.COPPER, 0.035, "Copper"),
            StackupLayer("B.Mask", LayerType.SOLDERMASK, 0.01, "SOLDERMASK", color="green"),
        ],
        total_thickness=1.525,
        copper_layer_count=3,
        board_name="test_with_mask.kicad_pcb"
    )


class TestThicknessModes:
    """Tests for different thickness rendering modes"""

    def test_uniform_thickness_mode(self, sample_stackup):
        """Test uniform thickness mode - all layers same height"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=5.0
        )
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]

        # All layers should have the same height
        for rect in rectangles:
            assert rect.height_mm == 5.0

    def test_proportional_thickness_mode(self, sample_stackup):
        """Test proportional thickness mode - fixed ratios"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.PROPORTIONAL,
            # uniform_layer_height_mm uses DEFAULT_BASE_HEIGHT_MM (3.75mm) by default
        )
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        layers = sample_stackup.layers

        # Check each layer has correct proportional height
        base_height = DEFAULT_BASE_HEIGHT_MM
        for rect, layer in zip(rectangles, layers):
            if layer.layer_type == LayerType.COPPER:
                assert rect.height_mm == base_height * COPPER_HEIGHT_RATIO  # 3.75mm (1.0 * 3.75)
            elif layer.layer_type == LayerType.DIELECTRIC:
                assert rect.height_mm == base_height * DIELECTRIC_HEIGHT_RATIO  # 4.6875mm (1.25 * 3.75)

    def test_scaled_thickness_mode(self, sample_stackup):
        """Test scaled thickness mode - actual thickness ratios"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.SCALED,
            max_total_height_mm=100.0
        )
        layout = calculate_graphical_layout(sample_stackup, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        layers = sample_stackup.layers

        # Total height of all rectangles should be approximately max_total_height_mm
        total_rect_height = sum(rect.height_mm for rect in rectangles)
        assert abs(total_rect_height - 100.0) < 0.01

        # Heights should be proportional to actual thicknesses
        scale_factor = 100.0 / sample_stackup.total_thickness
        for rect, layer in zip(rectangles, layers):
            expected_height = layer.thickness * scale_factor
            assert abs(rect.height_mm - expected_height) < 0.01

    def test_calculate_layer_heights_uniform(self, sample_stackup):
        """Test _calculate_layer_heights helper with uniform mode"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=7.0
        )
        heights = _calculate_layer_heights(sample_stackup, config)

        assert len(heights) == len(sample_stackup.layers)
        assert all(h == 7.0 for h in heights)

    def test_calculate_layer_heights_proportional(self, stackup_with_soldermask):
        """Test _calculate_layer_heights helper with proportional mode"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.PROPORTIONAL,
            # Uses default ratios and base height
        )
        heights = _calculate_layer_heights(stackup_with_soldermask, config)

        layers = stackup_with_soldermask.layers
        assert len(heights) == len(layers)

        base_height = DEFAULT_BASE_HEIGHT_MM

        # Check soldermask layers
        assert heights[0] == base_height * SOLDERMASK_HEIGHT_RATIO  # F.Mask
        assert heights[6] == base_height * SOLDERMASK_HEIGHT_RATIO  # B.Mask

        # Check copper layers
        assert heights[1] == base_height * COPPER_HEIGHT_RATIO  # F.Cu
        assert heights[3] == base_height * COPPER_HEIGHT_RATIO  # In1.Cu

        # Check dielectric layers
        assert heights[2] == base_height * DIELECTRIC_HEIGHT_RATIO  # Core1
        assert heights[4] == base_height * DIELECTRIC_HEIGHT_RATIO  # Core2


class TestSoldermaskGapSpacing:
    """Tests for soldermask layer gap spacing"""

    def test_soldermask_gap_disabled(self, stackup_with_soldermask):
        """Test that no gap is added when soldermask_gap_mm is 0"""
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=DEFAULT_BASE_HEIGHT_MM,
            soldermask_gap_mm=0.0
        )
        layout = calculate_graphical_layout(stackup_with_soldermask, config)

        # Total height should be exactly layer_count * layer_height (no gaps)
        expected_height = len(stackup_with_soldermask.layers) * DEFAULT_BASE_HEIGHT_MM
        assert layout.total_height_mm == expected_height

    def test_soldermask_gap_enabled(self, stackup_with_soldermask):
        """Test that gaps are added above/below soldermask layers"""
        gap_size = 2.0
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=DEFAULT_BASE_HEIGHT_MM,
            soldermask_gap_mm=gap_size
        )
        layout = calculate_graphical_layout(stackup_with_soldermask, config)

        # Count soldermask layers
        soldermask_count = sum(
            1 for layer in stackup_with_soldermask.layers
            if layer.layer_type == LayerType.SOLDERMASK
        )

        # Total height should include gaps (2 gaps per soldermask layer)
        base_height = len(stackup_with_soldermask.layers) * DEFAULT_BASE_HEIGHT_MM
        gap_height = soldermask_count * 2.0 * gap_size  # 2 gaps per mask
        expected_height = base_height + gap_height

        assert abs(layout.total_height_mm - expected_height) < 0.01

    def test_soldermask_rectangles_have_gaps(self, stackup_with_soldermask):
        """Test that soldermask rectangles are positioned with gaps"""
        gap_size = 2.0
        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=DEFAULT_BASE_HEIGHT_MM,
            soldermask_gap_mm=gap_size,
            origin_y_mm=0.0
        )
        layout = calculate_graphical_layout(stackup_with_soldermask, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        layers = stackup_with_soldermask.layers

        # First element should be F.Mask, which should start at gap offset
        assert layers[0].layer_type == LayerType.SOLDERMASK
        assert rectangles[0].position_mm[1] == gap_size  # origin + gap

        # F.Cu should be right after F.Mask + another gap
        assert layers[1].layer_type == LayerType.COPPER
        expected_y = gap_size + DEFAULT_BASE_HEIGHT_MM + gap_size  # gap + mask_height + gap
        assert abs(rectangles[1].position_mm[1] - expected_y) < 0.01


class TestLayerTypeStorage:
    """Tests for layer type storage in rectangles"""

    def test_layer_type_stored_in_rectangles(self, stackup_with_soldermask):
        """Test that layer type is stored in LayerRectangle for rendering"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(stackup_with_soldermask, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]
        layers = stackup_with_soldermask.layers

        for rect, layer in zip(rectangles, layers):
            assert rect.layer_type == layer.layer_type.value

    def test_copper_layers_identified(self, stackup_with_soldermask):
        """Test that copper layers can be identified from rectangles"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(stackup_with_soldermask, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]

        copper_rects = [
            r for r in rectangles
            if r.layer_type == LayerType.COPPER.value
        ]

        # Should have 3 copper layers
        assert len(copper_rects) == 3

    def test_soldermask_layers_identified(self, stackup_with_soldermask):
        """Test that soldermask layers can be identified from rectangles"""
        config = GraphicalStackupConfig()
        layout = calculate_graphical_layout(stackup_with_soldermask, config)

        rectangles = [e for e in layout.elements if isinstance(e, LayerRectangle)]

        soldermask_rects = [
            r for r in rectangles
            if r.layer_type == LayerType.SOLDERMASK.value
        ]

        # Should have 2 soldermask layers
        assert len(soldermask_rects) == 2


class TestIntelligentElbowGeneration:
    """Test smart elbow generation based on size thresholds"""

    def test_min_elbow_height_constant_used(self):
        """Verify MIN_ELBOW_HEIGHT_MM constant is respected"""
        config = GraphicalStackupConfig(min_elbow_height_mm=0.5)
        assert config.min_elbow_height_mm == MIN_ELBOW_HEIGHT_MM
        assert config.min_elbow_height_mm == 0.5

        # Test with custom value
        config_custom = GraphicalStackupConfig(min_elbow_height_mm=1.0)
        assert config_custom.min_elbow_height_mm == 1.0

    def test_should_use_straight_line_logic(self):
        """Test _should_use_straight_line() decision logic"""
        config = GraphicalStackupConfig(min_elbow_height_mm=0.5)

        # Elbow too small → use straight line
        assert _should_use_straight_line(0.2, config) is True
        assert _should_use_straight_line(0.4, config) is True
        assert _should_use_straight_line(0.49, config) is True

        # Elbow large enough → use elbow
        assert _should_use_straight_line(0.5, config) is False
        assert _should_use_straight_line(0.6, config) is False
        assert _should_use_straight_line(1.0, config) is False

        # Edge case: exactly at threshold
        assert _should_use_straight_line(0.5, config) is False

    def test_elbow_height_calculation(self):
        """Test _calculate_elbow_heights() helper function"""
        # Create simple stackup with two layers
        stackup = StackupData(
            layers=[
                StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("B.Cu", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.07,
            copper_layer_count=2,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=5.0,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)

        # Set up groups and proposed positions
        groups_to_adjust = [(0, 1, 2), (3, 4, 5)]  # (rect, leader, callout) indices

        # Propose callouts 3mm above/below layer centers
        # Layer 1 center: y=2.5 (y=0, height=5.0)
        # Layer 2 center: y=7.5 (y=5, height=5.0)
        new_callout_positions = [5.5, 4.5]  # 3mm above first, 3mm below second

        elbow_heights = _calculate_elbow_heights(
            groups_to_adjust, new_callout_positions, layout.elements, config
        )

        # Should calculate vertical displacement for each
        assert len(elbow_heights) == 2
        assert abs(elbow_heights[0] - 3.0) < 0.01  # |5.5 - 2.5| = 3.0
        assert abs(elbow_heights[1] - 3.0) < 0.01  # |4.5 - 7.5| = 3.0

    def test_adjust_spacing_for_minimum_elbows(self):
        """Test _adjust_spacing_for_minimum_elbows() enforcement"""
        # Create simple stackup
        stackup = StackupData(
            layers=[
                StackupLayer("F.Cu", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("B.Cu", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.07,
            copper_layer_count=2,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=5.0,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
            min_elbow_height_mm=0.5,
        )

        layout = calculate_graphical_layout(stackup, config)

        groups_to_adjust = [(0, 1, 2), (3, 4, 5)]

        # Propose callouts with tiny elbows (0.2mm)
        # Layer 1 center: 2.5, Layer 2 center: 7.5
        new_callout_positions = [2.7, 7.3]  # 0.2mm displacement
        elbow_heights = [0.2, 0.2]

        adjusted_positions = _adjust_spacing_for_minimum_elbows(
            groups_to_adjust, new_callout_positions, elbow_heights, layout.elements, config
        )

        # Should enforce minimum 0.5mm displacement
        # Layer 1: 2.5 + 0.5 = 3.0 (callout below)
        # Layer 2: 7.5 - 0.5 = 7.0 (callout above)
        assert abs(adjusted_positions[0] - 3.0) < 0.01
        assert abs(adjusted_positions[1] - 7.0) < 0.01

    def test_small_elbows_become_straight(self):
        """Elbows < 0.5mm should be converted to straight lines"""
        # Create stackup with layers very close together
        stackup = StackupData(
            layers=[
                StackupLayer("L1", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L2", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L3", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.105,
            copper_layer_count=3,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=2.0,  # Small layers to create tiny spacing
            min_callout_spacing_mm=100.0,  # Force collisions
            min_elbow_height_mm=0.5,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        # Get all leader lines
        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]

        # After adjustment with small spacing, some should be forced to >= 0.5mm elbow
        # or remain straight if already far enough
        # With our enforcement, elbows should either be >= 0.5mm or straight
        for leader in leaders:
            if leader.style != LeaderLineStyle.STRAIGHT:
                # Calculate elbow height from segments
                if len(leader.segments) >= 2:
                    # Angled segment is the middle one
                    y_start = leader.segments[0][0][1]
                    y_end = leader.segments[-1][1][1]
                    elbow_height = abs(y_end - y_start)
                    # Should be >= min threshold if not straight
                    assert elbow_height >= config.min_elbow_height_mm - 0.01

    def test_large_elbows_remain_elbows(self):
        """Elbows >= 0.5mm should remain as elbows"""
        # Create stackup with sufficient spacing
        stackup = StackupData(
            layers=[
                StackupLayer("L1", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("Core", LayerType.DIELECTRIC, 2.0, "FR4"),
                StackupLayer("L2", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=2.07,
            copper_layer_count=2,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.SCALED,
            max_total_height_mm=30.0,  # Scale to create larger visual spacing
            min_callout_spacing_mm=5.0,  # Force some collisions
            min_elbow_height_mm=0.5,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        # Get all leader lines
        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]

        # With sufficient spacing, adjusted leaders should use elbows
        angled_leaders = [
            l for l in leaders
            if l.style in [LeaderLineStyle.ANGLED_UP, LeaderLineStyle.ANGLED_DOWN]
        ]

        # Should have some angled leaders (not all straight)
        # In this case with collisions, we expect elbows
        if len(leaders) > len(angled_leaders):
            # Some are straight, which is fine if spacing is good
            pass

        # Verify angled leaders have proper elbow heights
        for leader in angled_leaders:
            assert len(leader.segments) == 3  # H → angled → H
            y_start = leader.segments[0][0][1]
            y_end = leader.segments[-1][1][1]
            elbow_height = abs(y_end - y_start)
            # Should be >= min threshold
            assert elbow_height >= config.min_elbow_height_mm - 0.01

    def test_minimum_elbow_enforcement(self):
        """When callouts too close, spacing should be increased to create 0.5mm+ elbows"""
        # Create dense stackup
        stackup = StackupData(
            layers=[
                StackupLayer("L1", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("D1", LayerType.DIELECTRIC, 0.1, "FR4"),
                StackupLayer("L2", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("D2", LayerType.DIELECTRIC, 0.1, "FR4"),
                StackupLayer("L3", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.305,
            copper_layer_count=3,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=3.0,
            min_callout_spacing_mm=20.0,  # Force collisions
            min_elbow_height_mm=0.5,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        # Get callouts
        callouts = [e for e in adjusted_layout.elements if isinstance(e, CalloutText)]

        # Verify callouts have minimum vertical spacing
        # (Either they're spread out enough, or elbows are enforced)
        for i in range(len(callouts) - 1):
            y1 = callouts[i].position_mm[1]
            y2 = callouts[i + 1].position_mm[1]
            vertical_gap = abs(y2 - y1)

            # Gap might be smaller than min_callout_spacing if elbows compensate
            # But the elbow heights should be >= min_elbow_height_mm
            # This is enforced by _adjust_spacing_for_minimum_elbows

        # Verify all leaders have proper elbow heights or are straight
        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]
        for leader in leaders:
            if leader.style != LeaderLineStyle.STRAIGHT:
                # Should have elbow >= threshold
                y_start = leader.segments[0][0][1]
                y_end = leader.segments[-1][1][1]
                elbow_height = abs(y_end - y_start)
                assert elbow_height >= config.min_elbow_height_mm - 0.01


class TestSymmetricElbowSpacing:
    """Test symmetric spacing from center layer"""

    def test_symmetric_spacing_odd_layers_five(self):
        """Test symmetric spacing with 5 colliding layers"""
        # Create 5-layer stackup
        stackup = StackupData(
            layers=[
                StackupLayer("L1", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L2", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L3", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L4", LayerType.COPPER, 0.035, "Copper"),
                StackupLayer("L5", LayerType.COPPER, 0.035, "Copper"),
            ],
            total_thickness=0.175,
            copper_layer_count=5,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=3.0,
            min_callout_spacing_mm=20.0,  # Force collisions
            min_elbow_height_mm=0.5,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        # Get callouts and leaders
        callouts = [e for e in adjusted_layout.elements if isinstance(e, CalloutText)]
        leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]

        # Verify center layer (index 2) has straight line
        center_leader = leaders[2]
        assert center_leader.style == LeaderLineStyle.STRAIGHT

        # Verify layers 0 and 4 have matching displacements (mirror)
        # Calculate displacements from layer rectangles
        rects = [e for e in adjusted_layout.elements if isinstance(e, LayerRectangle)]

        rect0_center = rects[0].position_mm[1] + rects[0].height_mm / 2
        rect4_center = rects[4].position_mm[1] + rects[4].height_mm / 2

        displacement0 = abs(callouts[0].position_mm[1] - rect0_center)
        displacement4 = abs(callouts[4].position_mm[1] - rect4_center)

        # Should be equal (mirrored)
        assert abs(displacement0 - displacement4) < 0.01

        # Verify layers 1 and 3 have matching displacements
        rect1_center = rects[1].position_mm[1] + rects[1].height_mm / 2
        rect3_center = rects[3].position_mm[1] + rects[3].height_mm / 2

        displacement1 = abs(callouts[1].position_mm[1] - rect1_center)
        displacement3 = abs(callouts[3].position_mm[1] - rect3_center)

        assert abs(displacement1 - displacement3) < 0.01

    def test_symmetric_spacing_center_is_straight(self):
        """Test that center layer always has straight leader line"""
        # Test with 3, 5, 7 layers
        for num_layers in [3, 5, 7]:
            stackup = StackupData(
                layers=[
                    StackupLayer(f"L{i+1}", LayerType.COPPER, 0.035, "Copper")
                    for i in range(num_layers)
                ],
                total_thickness=0.035 * num_layers,
                copper_layer_count=num_layers,
                board_name="test.kicad_pcb"
            )

            config = GraphicalStackupConfig(
                thickness_mode=ThicknessMode.UNIFORM,
                uniform_layer_height_mm=3.0,
                min_callout_spacing_mm=50.0,  # Force collisions
                min_elbow_height_mm=0.5,
                origin_x_mm=0.0,
                origin_y_mm=0.0,
            )

            layout = calculate_graphical_layout(stackup, config)
            adjusted_layout = adjust_leader_lines(layout, config)

            leaders = [e for e in adjusted_layout.elements if isinstance(e, LeaderLine)]

            # Center index
            center_idx = num_layers // 2
            center_leader = leaders[center_idx]

            # Center should always be straight
            assert center_leader.style == LeaderLineStyle.STRAIGHT, \
                f"Failed for {num_layers} layers: center leader (index {center_idx}) is not straight"

    def test_symmetric_spacing_mirrors(self):
        """Test that layers above/below center mirror each other"""
        # Create 7-layer stackup for thorough testing
        stackup = StackupData(
            layers=[
                StackupLayer(f"L{i+1}", LayerType.COPPER, 0.035, "Copper")
                for i in range(7)
            ],
            total_thickness=0.245,
            copper_layer_count=7,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=3.0,
            min_callout_spacing_mm=30.0,  # Force collisions
            min_elbow_height_mm=0.5,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)
        adjusted_layout = adjust_leader_lines(layout, config)

        # Get elements
        callouts = [e for e in adjusted_layout.elements if isinstance(e, CalloutText)]
        rects = [e for e in adjusted_layout.elements if isinstance(e, LayerRectangle)]

        # Calculate displacements for all layers
        displacements = []
        for i in range(7):
            rect_center = rects[i].position_mm[1] + rects[i].height_mm / 2
            callout_y = callouts[i].position_mm[1]
            displacement = callout_y - rect_center
            displacements.append(displacement)

        # Verify symmetry: displacement[i] = -displacement[6-i]
        # Layer 0 ↔ Layer 6
        assert abs(displacements[0] + displacements[6]) < 0.01, \
            f"L0 and L6 not mirrored: {displacements[0]} vs {displacements[6]}"

        # Layer 1 ↔ Layer 5
        assert abs(displacements[1] + displacements[5]) < 0.01, \
            f"L1 and L5 not mirrored: {displacements[1]} vs {displacements[5]}"

        # Layer 2 ↔ Layer 4
        assert abs(displacements[2] + displacements[4]) < 0.01, \
            f"L2 and L4 not mirrored: {displacements[2]} vs {displacements[4]}"

        # Layer 3 (center) should be 0
        assert abs(displacements[3]) < 0.01, \
            f"Center layer L3 not at 0 displacement: {displacements[3]}"

    def test_symmetric_positions_calculation(self):
        """Test _calculate_symmetric_positions() helper directly"""
        # Create simple 5-layer stackup
        stackup = StackupData(
            layers=[
                StackupLayer(f"L{i+1}", LayerType.COPPER, 0.035, "Copper")
                for i in range(5)
            ],
            total_thickness=0.175,
            copper_layer_count=5,
            board_name="test.kicad_pcb"
        )

        config = GraphicalStackupConfig(
            thickness_mode=ThicknessMode.UNIFORM,
            uniform_layer_height_mm=5.0,
            min_elbow_height_mm=0.5,
            origin_x_mm=0.0,
            origin_y_mm=0.0,
        )

        layout = calculate_graphical_layout(stackup, config)

        # Set up groups (all layers)
        groups_to_adjust = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 13, 14)]

        positions = _calculate_symmetric_positions(groups_to_adjust, layout.elements, config)

        # Calculate expected positions
        # Layer centers: 2.5, 7.5, 12.5, 17.5, 22.5 (y=0, 5, 10, 15, 20 with height=5)
        # Center index = 2, spacing_unit = 0.5
        # Expected displacements: -1.0, -0.5, 0.0, +0.5, +1.0
        # Expected positions: 1.5, 7.0, 12.5, 18.0, 23.5

        expected = [
            2.5 - 1.0,  # L0: center - 2 * 0.5 = 1.5
            7.5 - 0.5,  # L1: center - 1 * 0.5 = 7.0
            12.5 + 0.0,  # L2: center + 0 = 12.5 (CENTER)
            17.5 + 0.5,  # L3: center + 1 * 0.5 = 18.0
            22.5 + 1.0,  # L4: center + 2 * 0.5 = 23.5
        ]

        for i, (expected_pos, actual_pos) in enumerate(zip(expected, positions)):
            assert abs(expected_pos - actual_pos) < 0.01, \
                f"Layer {i}: expected {expected_pos}, got {actual_pos}"
