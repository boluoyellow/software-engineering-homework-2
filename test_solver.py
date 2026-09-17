import random

from arrow import Arrow, polyline_length, sample_route_span, smooth_route
from generator import generate_level
from levels import LEVELS
from solver import can_move, is_solvable


def test_generated_levels_are_solvable():
    for seed in range(10):
        level = generate_level(rng=random.Random(seed))
        occupied = [cell for arrow in level for cell in arrow.body_cells()]
        assert len(level) == 7
        assert len(occupied) < 8 * 8
        assert len(set(occupied)) == len(occupied)
        assert is_solvable(level)


def test_front_blocker_prevents_departure_until_removed():
    moving = Arrow(2, 1, "right")
    blocker = Arrow(2, 3, "up")
    arrows = (moving, blocker)
    assert not can_move(0, arrows, 0b11, 6)
    assert can_move(0, arrows, 0b01, 6)


def test_curved_arrow_routes_turn_on_the_configured_cells():
    left = Arrow(3, 1, "right", "turn_left", (2, 2))
    assert left.body_cells() == ((3, 1), (3, 2), (3, 3), (2, 3), (1, 3))
    assert list(left.path_cells(6)) == [(0, 3)]

    zigzag = Arrow(3, 1, "right", "zigzag_left", (1, 2, 3))
    assert zigzag.body_cells() == (
        (3, 1),
        (3, 2),
        (2, 2),
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 5),
    )
    assert list(zigzag.path_cells(6)) == []

    wave = Arrow(5, 1, "right", "wave_left", (1, 1, 1, 1, 2))
    assert len(wave.body_cells()) == 7
    assert len(set(wave.body_cells())) == 7

    animated = smooth_route([(0, 0), (10, 0), (10, 10)], radius=4, steps=8)
    assert animated[0] == (0, 0)
    assert animated[-1] == (10, 10)
    assert (10, 0) not in animated
    assert any(6 < x < 10 and 0 < y < 4 for x, y in animated)

    guide = animated + [(10, 30)]
    rope_length = polyline_length(animated)
    pulled = sample_route_span(guide, start_distance=3, length=rope_length, sample_count=30)
    assert pulled[0] != animated[0]
    assert abs(polyline_length(pulled) - rope_length) < 0.2


def test_campaign_is_a_solvable_irregular_sparse_maze():
    sizes = [spec.grid_size for spec in LEVELS]
    assert sizes == sorted(sizes)
    assert sizes == list(range(6, 25, 2))
    averages = []
    turn_counts = []

    for index, spec in enumerate(LEVELS):
        arrows = generate_level(
            spec.arrow_count,
            rng=random.Random(index),
            grid_size=spec.grid_size,
            kinds=spec.kinds,
        )
        assert len(arrows) == spec.arrow_count
        assert all(arrow.kind in spec.kinds for arrow in arrows)
        assert all(arrow.has_complete_shape(spec.grid_size) for arrow in arrows)
        assert {arrow.kind for arrow in arrows} == set(spec.kinds)
        occupied = [cell for arrow in arrows for cell in arrow.body_cells()]
        assert len(set(occupied)) == len(occupied)
        density = len(occupied) / (spec.grid_size * spec.grid_size)
        assert 0.55 <= density <= 0.85
        assert all(len(arrow.body_cells()) >= 4 for arrow in arrows)
        assert all(len(arrow.body_cells()) <= 18 for arrow in arrows)
        turn_counts.extend(len(arrow.turns) for arrow in arrows)
        averages.append(len(occupied) / len(arrows))
        assert is_solvable(arrows, spec.grid_size)
    assert averages[-1] > averages[0]
    assert max(turn_counts) >= 7
    assert sum(count >= 2 for count in turn_counts) > len(turn_counts) // 2


if __name__ == "__main__":
    test_generated_levels_are_solvable()
    test_front_blocker_prevents_departure_until_removed()
    test_curved_arrow_routes_turn_on_the_configured_cells()
    test_campaign_is_a_solvable_irregular_sparse_maze()
    print("solver and campaign tests passed")
