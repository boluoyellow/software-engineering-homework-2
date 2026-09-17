from dataclasses import dataclass


DIRECTION_VECTORS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

# -1 turns left and +1 turns right in screen coordinates.
ARROW_TURNS = {
    "straight": (),
    "long_straight": (),
    "turn_left": (-1,),
    "turn_right": (1,),
    "zigzag_left": (-1, 1),
    "zigzag_right": (1, -1),
    "hook_left": (-1, -1),
    "hook_right": (1, 1),
    "stair_left": (-1, 1, -1),
    "stair_right": (1, -1, 1),
    "wave_left": (-1, 1, -1, 1),
    "wave_right": (1, -1, 1, -1),
    "snake_left": (-1, -1, 1, 1),
    "snake_right": (1, 1, -1, -1),
    "maze": (),
}

_RENDER_CACHE = {}


def clear_render_cache():
    _RENDER_CACHE.clear()


def _rotate(vector, turn):
    x, y = vector
    return (y, -x) if turn < 0 else (-y, x)


def smooth_route(points, radius, steps=8):
    """Replace polyline corners with quadratic curves without changing endpoints."""
    if len(points) < 3:
        return list(points)
    smoothed = [points[0]]
    for index in range(1, len(points) - 1):
        previous = points[index - 1]
        corner = points[index]
        following = points[index + 1]
        incoming = (corner[0] - previous[0], corner[1] - previous[1])
        outgoing = (following[0] - corner[0], following[1] - corner[1])
        incoming_length = max(0.001, (incoming[0] ** 2 + incoming[1] ** 2) ** 0.5)
        outgoing_length = max(0.001, (outgoing[0] ** 2 + outgoing[1] ** 2) ** 0.5)
        incoming_unit = (incoming[0] / incoming_length, incoming[1] / incoming_length)
        outgoing_unit = (outgoing[0] / outgoing_length, outgoing[1] / outgoing_length)
        cross = incoming_unit[0] * outgoing_unit[1] - incoming_unit[1] * outgoing_unit[0]
        dot = incoming_unit[0] * outgoing_unit[0] + incoming_unit[1] * outgoing_unit[1]
        if abs(cross) < 0.001 and dot > 0:
            smoothed.append(corner)
            continue
        curve_radius = min(radius, incoming_length * 0.45, outgoing_length * 0.45)
        entry = (
            corner[0] - incoming_unit[0] * curve_radius,
            corner[1] - incoming_unit[1] * curve_radius,
        )
        exit_point = (
            corner[0] + outgoing_unit[0] * curve_radius,
            corner[1] + outgoing_unit[1] * curve_radius,
        )
        smoothed.append(entry)
        for step in range(1, steps + 1):
            t = step / steps
            inverse = 1.0 - t
            smoothed.append(
                (
                    inverse * inverse * entry[0] + 2 * inverse * t * corner[0] + t * t * exit_point[0],
                    inverse * inverse * entry[1] + 2 * inverse * t * corner[1] + t * t * exit_point[1],
                )
            )
    smoothed.append(points[-1])
    return smoothed


def polyline_length(points):
    return sum(
        ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        for start, end in zip(points, points[1:])
    )


def sample_route_span(points, start_distance, length, sample_count):
    """Sample a fixed-length rope after it advances along a guide polyline."""
    if len(points) < 2:
        return list(points)
    distances = [0.0]
    for start, end in zip(points, points[1:]):
        distances.append(
            distances[-1] + ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        )
    result = []
    segment = 0
    for index in range(max(2, sample_count)):
        target = start_distance + length * index / max(1, sample_count - 1)
        target = max(0.0, min(target, distances[-1]))
        while segment < len(distances) - 2 and distances[segment + 1] < target:
            segment += 1
        segment_length = max(0.001, distances[segment + 1] - distances[segment])
        ratio = (target - distances[segment]) / segment_length
        start, end = points[segment], points[segment + 1]
        result.append(
            (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
        )
    return result


@dataclass(frozen=True)
class Arrow:
    """An arrow whose body may occupy a multi-cell orthogonal route."""

    row: int
    col: int
    direction: str
    kind: str = "straight"
    segment_lengths: tuple = ()
    turn_sequence: tuple = ()
    color_index: int = 0

    @property
    def vector(self):
        return DIRECTION_VECTORS[self.direction]

    @property
    def turns(self):
        return self.turn_sequence or ARROW_TURNS[self.kind]

    @property
    def final_vector(self):
        vector = self.vector
        for turn in self.turns:
            vector = _rotate(vector, turn)
        return vector

    @property
    def segments(self):
        if self.segment_lengths:
            return self.segment_lengths
        if self.kind == "straight":
            return (0,)
        if self.kind == "long_straight":
            return (2,)
        return (1,) * (len(self.turns) + 1)

    def body_cells(self):
        """Return ordered cells from the tail cell through the arrowhead cell."""
        cells = [(self.row, self.col)]
        row, col = self.row, self.col
        dx, dy = self.vector
        for segment_index, length in enumerate(self.segments):
            for _ in range(length):
                row, col = row + dy, col + dx
                cells.append((row, col))
            if segment_index < len(self.turns):
                dx, dy = _rotate((dx, dy), self.turns[segment_index])
        return tuple(cells)

    @property
    def head_cell(self):
        return self.body_cells()[-1]

    def path_cells(self, grid_size):
        """Yield the clearance ray beyond the arrow's pointed head."""
        row, col = self.head_cell
        dx, dy = self.final_vector
        while True:
            row, col = row + dy, col + dx
            if not (0 <= row < grid_size and 0 <= col < grid_size):
                return
            yield row, col

    def has_complete_shape(self, grid_size):
        cells = self.body_cells()
        if len(cells) != len(set(cells)) or not all(
            0 <= row < grid_size and 0 <= col < grid_size for row, col in cells
        ):
            return False
        body = set(cells)
        return all(cell not in body for cell in self.path_cells(grid_size))

    def occupies(self, row, col):
        return (row, col) in self.body_cells()

    def _board_points(self, board_x, board_y, cell_size):
        def center(cell):
            row, col = cell
            return (
                board_x + col * cell_size + cell_size / 2,
                board_y + row * cell_size + cell_size / 2,
            )

        centers = [center(cell) for cell in self.body_cells()]
        start_dx, start_dy = self.vector
        end_dx, end_dy = self.final_vector
        if len(centers) == 1:
            center_x, center_y = centers[0]
            reach = cell_size * 0.32
            return [
                (center_x - start_dx * reach, center_y - start_dy * reach),
                (center_x + end_dx * reach, center_y + end_dy * reach),
            ]
        tail = (
            centers[0][0] - start_dx * cell_size * 0.22,
            centers[0][1] - start_dy * cell_size * 0.22,
        )
        tip = (
            centers[-1][0] + end_dx * cell_size * 0.31,
            centers[-1][1] + end_dy * cell_size * 0.31,
        )
        return [tail] + centers[1:] + [tip]

    def draw(self, surface, board_x, board_y, color, cell_size, shake=(0, 0), highlighted=False):
        """Draw one continuous neon arrow across its complete multi-cell body."""
        cache_key = (self, tuple(color), cell_size, highlighted)
        cached = _RENDER_CACHE.get(cache_key)
        if cached is not None:
            layer, offset = cached
            surface.blit(layer, (board_x + offset[0] + shake[0], board_y + offset[1] + shake[1]))
            return
        world_points = self._board_points(0, 0, cell_size)
        layer, offset = _render_arrow_path(world_points, color, cell_size, highlighted, smooth=True, scale=3)
        _RENDER_CACHE[cache_key] = (layer, offset)
        surface.blit(layer, (board_x + offset[0] + shake[0], board_y + offset[1] + shake[1]))

    def draw_moving(self, surface, world_points, color, cell_size, shake=(0, 0)):
        """Draw the full flexible body at its current rope-simulation points."""
        layer, offset = _render_arrow_path(world_points, color, cell_size, False, smooth=False, scale=2)
        surface.blit(layer, (offset[0] + shake[0], offset[1] + shake[1]))


def _render_arrow_path(world_points, color, cell_size, highlighted, smooth, scale):
    import pygame

    padding = int(cell_size * 0.42)
    min_x = int(min(point[0] for point in world_points)) - padding
    min_y = int(min(point[1] for point in world_points)) - padding
    max_x = int(max(point[0] for point in world_points)) + padding
    max_y = int(max(point[1] for point in world_points)) + padding
    width = max_x - min_x + 1
    height = max_y - min_y + 1
    layer = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)
    raw_points = [((x - min_x) * scale, (y - min_y) * scale) for x, y in world_points]
    tip = raw_points[-1]
    before = raw_points[-2]
    final_length = max(1.0, ((tip[0] - before[0]) ** 2 + (tip[1] - before[1]) ** 2) ** 0.5)
    dx, dy = (tip[0] - before[0]) / final_length, (tip[1] - before[1]) / final_length
    px, py = -dy, dx
    head_length = cell_size * 0.23 * scale
    base = (tip[0] - dx * head_length, tip[1] - dy * head_length)
    wing = head_length * 0.48
    arrow_head = [
        (int(tip[0]), int(tip[1])),
        (int(base[0] + px * wing), int(base[1] + py * wing)),
        (int(base[0] - px * wing), int(base[1] - py * wing)),
    ]
    body_source = raw_points[:-1] + [base]
    if smooth:
        body_source = smooth_route(body_source, cell_size * 0.38 * scale, 12)
    body_points = [(int(x), int(y)) for x, y in body_source]

    def rounded_path(path, draw_color, width_value):
        pygame.draw.lines(layer, draw_color, False, path, width_value)
        radius = max(1, width_value // 2)
        for point in path:
            pygame.draw.circle(layer, draw_color, point, radius)

    glow = 100 if highlighted else 58
    rounded_path(body_points, (*color, glow // 3), max(8, int(cell_size * 0.28 * scale)))
    rounded_path(body_points, (*color, glow), max(6, int(cell_size * 0.17 * scale)))
    pygame.draw.polygon(layer, (*color, glow), arrow_head)
    shadow_offset = (2 * scale, 3 * scale)
    shadow_points = [(x + shadow_offset[0], y + shadow_offset[1]) for x, y in body_points]
    shadow_head = [(x + shadow_offset[0], y + shadow_offset[1]) for x, y in arrow_head]
    rounded_path(shadow_points, (1, 5, 15, 228), max(4, int(cell_size * 0.12 * scale)))
    pygame.draw.polygon(layer, (1, 5, 15, 228), shadow_head)
    rounded_path(body_points, (*color, 255), max(3, int(cell_size * 0.075 * scale)))
    pygame.draw.polygon(layer, (*color, 255), arrow_head)
    shine = tuple(min(255, channel + 100) for channel in color)
    rounded_path(body_points, (*shine, 210), max(2, int(cell_size * 0.018 * scale)))
    pygame.draw.line(layer, (*shine, 235), arrow_head[0], arrow_head[1], max(2, scale))
    return pygame.transform.smoothscale(layer, (width, height)), (min_x, min_y)
