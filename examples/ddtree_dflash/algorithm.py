"""Pure-Python best-first tree construction over a factorized draft
distribution Q = q_1 * q_2 * ... * q_d.

Kept independent of Manim so the DDTree best-first algorithm and this
scene's toy numbers can be unit tested directly, and so the scene can build
its visuals from one verified source of truth instead of hand-typed score
strings.
"""

from dataclasses import dataclass
import heapq

# Toy per-position marginals returned by one DFlash pass. Invented for this
# example; every later calculation in the scene uses them exactly.
Q1 = {"the": 0.55, "a": 0.35, "this": 0.10}
Q2 = {"model": 0.60, "system": 0.30, "code": 0.10}
Q3 = {"works": 0.52, "runs": 0.28, "fails": 0.20}


@dataclass(frozen=True)
class Prefix:
    """One inserted tree node: its key path, token, parent key, and mass.

    ``mass`` is the exact (unrounded) prefix probability under Q; the
    caller decides how to round it for display.

    ``key`` and ``parent`` are ``"-"``-joined display strings, kept for
    backward compatibility with callers (such as the scene) that use them
    as plain dictionary keys. They are derived from ``path``, the token
    sequence from the root, which is this prefix's unambiguous identity:
    unlike the joined strings, ``path`` cannot collide across two distinct
    lineages even if a token itself contains ``"-"``.
    """

    key: str
    token: str
    parent: str
    depth: int
    mass: float
    path: tuple[str, ...]


def best_first_prefixes(
    marginals: list[dict[str, float]], *, budget: int, root_key: str = "root"
) -> list[Prefix]:
    """Return the ``budget`` highest-mass prefixes in best-first pop order.

    Mirrors DDTree's construction: a max-heap seeded with the single best
    depth-one token. Each pop inserts that prefix and offers at most two new
    candidates: its next sibling at the same depth (by marginal rank), and
    its best child one depth deeper. Because every child multiplies its
    parent's mass by a probability below one, popping the ``budget`` highest
    masses is automatically prefix-closed, so pop order also matches final
    rank order.
    """
    if budget < 1:
        raise ValueError("budget must be at least 1")
    if not marginals:
        raise ValueError("marginals must contain at least one depth")

    ranked = [sorted(depth.items(), key=lambda item: -item[1]) for depth in marginals]

    def display_key(path: tuple[str, ...]) -> str:
        """Join a path tuple into the scene's historical ``"-"``-separated
        string form. Not used for identity internally -- only ``path``
        (and slices of it) are compared or looked up, so a token
        containing ``"-"`` cannot be confused with a different lineage.
        """
        return "-".join(path)

    # Heap entries carry ``path`` -- the unambiguous tuple identity -- rather
    # than a pre-joined string, so sibling/child expansion below never needs
    # to parse or compare joined keys.
    heap: list[tuple[float, int, tuple[str, ...], int, float]] = []
    counter = 0

    def push(
        mass: float,
        path: tuple[str, ...],
        sibling_index: int,
        parent_mass: float,
    ) -> None:
        nonlocal counter
        counter += 1
        heapq.heappush(heap, (-mass, counter, path, sibling_index, parent_mass))

    seed_token, seed_value = ranked[0][0]
    push(seed_value, (seed_token,), 0, 1.0)

    popped: list[Prefix] = []
    while heap and len(popped) < budget:
        neg_mass, _, path, sibling_index, parent_mass = heapq.heappop(heap)
        mass = -neg_mass
        token = path[-1]
        depth = len(path)
        parent_path = path[:-1]
        parent_key = display_key(parent_path) if parent_path else root_key
        popped.append(
            Prefix(
                key=display_key(path),
                token=token,
                parent=parent_key,
                depth=depth,
                mass=mass,
                path=path,
            )
        )

        depth_tokens = ranked[depth - 1]
        if sibling_index + 1 < len(depth_tokens):
            next_token, next_value = depth_tokens[sibling_index + 1]
            sibling_path = parent_path + (next_token,)
            push(parent_mass * next_value, sibling_path, sibling_index + 1, parent_mass)

        if depth < len(marginals):
            child_token, child_value = ranked[depth][0]
            child_path = path + (child_token,)
            push(mass * child_value, child_path, 0, mass)

    return popped
