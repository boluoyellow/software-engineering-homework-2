from config import GRID_SIZE


def path_cells(arrow, grid_size=GRID_SIZE):
    yield from arrow.path_cells(grid_size)


def occupied_cells(arrows, mask):
    occupied = set()
    for index, arrow in enumerate(arrows):
        if mask & (1 << index):
            occupied.update(arrow.body_cells())
    return occupied


def can_move(index, arrows, mask, grid_size=GRID_SIZE):
    occupied = occupied_cells(arrows, mask)
    own_body = set(arrows[index].body_cells())
    return all(cell not in occupied or cell in own_body for cell in path_cells(arrows[index], grid_size))


def is_solvable(arrows, grid_size=GRID_SIZE):
    """Check solvability as a dependency graph, scaling to very large boards."""
    arrows = tuple(arrows)
    owner_by_cell = {}
    for index, arrow in enumerate(arrows):
        for cell in arrow.body_cells():
            if cell in owner_by_cell:
                return False
            owner_by_cell[cell] = index

    dependencies = []
    for index, arrow in enumerate(arrows):
        blockers = {
            owner_by_cell[cell]
            for cell in arrow.path_cells(grid_size)
            if cell in owner_by_cell and owner_by_cell[cell] != index
        }
        dependencies.append(blockers)

    ready = [index for index, blockers in enumerate(dependencies) if not blockers]
    removed = set()
    while ready:
        index = ready.pop()
        if index in removed:
            continue
        removed.add(index)
        for other, blockers in enumerate(dependencies):
            if index in blockers:
                blockers.remove(index)
                if not blockers and other not in removed:
                    ready.append(other)
    return len(removed) == len(arrows)
