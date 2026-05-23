from __future__ import annotations


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])

    state: dict[str, int] = {}
    # 0 = unvisited, 1 = visiting, 2 = visited

    def visit(node: str) -> bool:
        status = state.get(node, 0)
        if status == 1:
            return True
        if status == 2:
            return False

        state[node] = 1
        for nxt in adjacency.get(node, []):
            if visit(nxt):
                return True
        state[node] = 2
        return False

    for node in adjacency:
        if state.get(node, 0) == 0 and visit(node):
            return True
    return False
