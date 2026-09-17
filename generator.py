import random

from arrow import ARROW_TURNS, DIRECTION_VECTORS, Arrow
from config import GRID_SIZE
from solver import is_solvable


MAZE_KINDS = ("maze",)
MIN_ARROW_CELLS = 4
MAX_ARROW_CELLS = 18
PALETTE_SIZE = 8


def _in_bounds(cell, grid_size):
    row, col = cell
    return 0 <= row < grid_size and 0 <= col < grid_size


def _ray_cells(head, direction, grid_size):
    dx, dy = DIRECTION_VECTORS[direction]
    row, col = head
    result = []
    while True:
        row, col = row + dy, col + dx
        if not _in_bounds((row, col), grid_size):
            return tuple(result)
        result.append((row, col))


def _turn_between(before, after):
    x, y = before
    if (y, -x) == after:
        return -1
    if (-y, x) == after:
        return 1
    raise ValueError(f"Non-orthogonal turn: {before} -> {after}")


def _arrow_from_cells(cells, rng):
    vectors = [
        (col_b - col_a, row_b - row_a)
        for (row_a, col_a), (row_b, col_b) in zip(cells, cells[1:])
    ]
    direction_by_vector = {vector: name for name, vector in DIRECTION_VECTORS.items()}
    initial_direction = direction_by_vector[vectors[0]]
    segment_lengths = []
    turns = []
    current = vectors[0]
    run_length = 1
    for vector in vectors[1:]:
        if vector == current:
            run_length += 1
            continue
        segment_lengths.append(run_length)
        turns.append(_turn_between(current, vector))
        current = vector
        run_length = 1
    segment_lengths.append(run_length)
    return Arrow(
        cells[0][0],
        cells[0][1],
        initial_direction,
        "maze",
        tuple(segment_lengths),
        tuple(turns),
        rng.randrange(PALETTE_SIZE),
    )


def _weighted_choice(options, weights, rng):
    marker = rng.random() * sum(weights)
    for option, weight in zip(options, weights):
        marker -= weight
        if marker <= 0:
            return option
    return options[-1]


def _grow_path(head, direction, target_length, blocked, grid_size, rng):
    """Grow backward from a fixed arrowhead as a winding self-avoiding walk."""
    dx, dy = DIRECTION_VECTORS[direction]
    predecessor = (head[0] - dy, head[1] - dx)
    if not _in_bounds(predecessor, grid_size) or predecessor in blocked:
        return None

    reverse_path = [head, predecessor]
    used = set(reverse_path)
    previous_step = (predecessor[1] - head[1], predecessor[0] - head[0])
    while len(reverse_path) < target_length:
        row, col = reverse_path[-1]
        options = []
        weights = []
        for step in DIRECTION_VECTORS.values():
            next_cell = (row + step[1], col + step[0])
            if not _in_bounds(next_cell, grid_size) or next_cell in blocked or next_cell in used:
                continue
            if step == (-previous_step[0], -previous_step[1]):
                continue
            onward = 0
            for onward_step in DIRECTION_VECTORS.values():
                probe = (next_cell[0] + onward_step[1], next_cell[1] + onward_step[0])
                if _in_bounds(probe, grid_size) and probe not in blocked and probe not in used:
                    onward += 1
            is_turn = step != previous_step
            options.append((next_cell, step))
            weights.append((3.6 if is_turn else 1.0) * (0.7 + onward * 0.45))
        if not options:
            break
        next_cell, previous_step = _weighted_choice(options, weights, rng)
        reverse_path.append(next_cell)
        used.add(next_cell)

    if len(reverse_path) < MIN_ARROW_CELLS:
        return None
    return list(reversed(reverse_path))


def _head_options(occupied, reserved, grid_size, rng):
    blocked = occupied | reserved
    options = []
    for row in range(grid_size):
        for col in range(grid_size):
            head = (row, col)
            if head in blocked:
                continue
            for direction, (dx, dy) in DIRECTION_VECTORS.items():
                predecessor = (row - dy, col - dx)
                if not _in_bounds(predecessor, grid_size) or predecessor in blocked:
                    continue
                ray = _ray_cells(head, direction, grid_size)
                newly_reserved = sum(cell not in occupied and cell not in reserved for cell in ray)
                blockers = sum(cell in occupied for cell in ray)
                # Short open channels improve density; occupied cells create useful dependencies.
                score = newly_reserved * 2.1 - min(2, blockers) * 1.2 + rng.random() * 6.0
                options.append((score, head, direction, ray))
    options.sort(key=lambda option: option[0])
    return options


def _candidate_level(count, grid_size, rng):
    occupied = set()
    reserved = set()
    arrows = []
    for arrow_index in range(count):
        remaining = count - arrow_index
        free_count = grid_size * grid_size - len(occupied | reserved)
        if free_count < remaining * MIN_ARROW_CELLS:
            return None

        upper = min(MAX_ARROW_CELLS, max(MIN_ARROW_CELLS, grid_size // 2 + 5))
        capacity_average = max(MIN_ARROW_CELLS, free_count // max(1, remaining))
        upper = min(upper, max(MIN_ARROW_CELLS, capacity_average))
        placed = False
        options = _head_options(occupied, reserved, grid_size, rng)
        # Sample from a broad high-quality prefix so heads do not all hug one edge.
        option_limit = min(len(options), max(36, grid_size * 5))
        if option_limit:
            selected = options[:option_limit]
            rng.shuffle(selected)
        else:
            selected = []

        for _, head, direction, ray in selected:
            target = int(rng.triangular(MIN_ARROW_CELLS, upper + 1, upper))
            target = max(MIN_ARROW_CELLS, min(upper, target))
            path_blocked = occupied | reserved | set(ray)
            cells = _grow_path(head, direction, target, path_blocked, grid_size, rng)
            if cells is None:
                continue
            arrow = _arrow_from_cells(cells, rng)
            if not arrow.has_complete_shape(grid_size):
                continue
            arrows.append(arrow)
            occupied.update(cells)
            reserved.update(ray)
            placed = True
            break
        if not placed:
            return None

    rng.shuffle(arrows)
    return arrows


def generate_level(count=7, attempts=180, rng=None, grid_size=GRID_SIZE, kinds=MAZE_KINDS):
    """Generate a sparse, winding maze whose dependency order is guaranteed acyclic."""
    unknown = set(kinds) - set(ARROW_TURNS)
    if unknown:
        raise ValueError(f"Unknown arrow kinds: {sorted(unknown)}")
    if "maze" not in kinds:
        raise ValueError("Maze generation requires the 'maze' arrow kind")
    if grid_size < 4:
        raise ValueError("Maze boards must be at least 4 x 4")
    if count < 1 or grid_size * grid_size < count * MIN_ARROW_CELLS:
        raise ValueError("Arrow count is too high for this board")

    rng = rng or random.Random()
    for _ in range(max(1, attempts)):
        arrows = _candidate_level(count, grid_size, rng)
        if arrows is None:
            continue
        occupied = [cell for arrow in arrows for cell in arrow.body_cells()]
        if (
            len(occupied) == len(set(occupied))
            and all(arrow.has_complete_shape(grid_size) for arrow in arrows)
            and is_solvable(arrows, grid_size)
        ):
            return arrows
    raise RuntimeError("Unable to generate a solvable sparse maze")
