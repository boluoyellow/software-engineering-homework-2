"""Responsive board geometry shared by rendering and input handling."""

from dataclasses import dataclass


MIN_SIDE_MARGIN = 56
BOARD_Y = 92
BOARD_PADDING = 5


@dataclass(frozen=True)
class Layout:
    grid_size: int
    cell_size: int
    board_y: int = BOARD_Y

    @property
    def board_x(self):
        return (self.window_width - self.board_width) // 2

    @property
    def board_width(self):
        return self.grid_size * self.cell_size

    @property
    def board_height(self):
        return self.grid_size * self.cell_size

    @property
    def window_width(self):
        return max(800, MIN_SIDE_MARGIN * 2 + self.board_width)

    @property
    def window_height(self):
        return self.board_y + self.board_height + 72


def get_layout(grid_size):
    """Grow the physical board while keeping late levels desktop-friendly."""
    # Small maps keep generous cells; large maps fit inside a ~660 px board.
    cell_size = max(27, min(70, 660 // grid_size))
    return Layout(grid_size=grid_size, cell_size=cell_size)


# Backwards-compatible defaults for modules or extensions using the old constants.
GRID_SIZE = 8
_DEFAULT = get_layout(GRID_SIZE)
BOARD_X = _DEFAULT.board_x
CELL_SIZE = _DEFAULT.cell_size
BOARD_WIDTH = _DEFAULT.board_width
BOARD_HEIGHT = _DEFAULT.board_height
WINDOW_WIDTH = _DEFAULT.window_width
WINDOW_HEIGHT = _DEFAULT.window_height
ARROW_LENGTH = CELL_SIZE - BOARD_PADDING * 2 - 8
ARROW_HEAD = 15
