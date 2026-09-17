from dataclasses import dataclass


MAZE_KINDS = ("maze",)


@dataclass(frozen=True)
class LevelSpec:
    grid_size: int
    arrow_count: int
    kinds: tuple = MAZE_KINDS


LEVELS = (
    LevelSpec(6, 4),
    LevelSpec(8, 7),
    LevelSpec(10, 10),
    LevelSpec(12, 14),
    LevelSpec(14, 18),
    LevelSpec(16, 23),
    LevelSpec(18, 29),
    LevelSpec(20, 36),
    LevelSpec(22, 43),
    LevelSpec(24, 52),
)
