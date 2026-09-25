"""Exact, CPU-only toy checks independent of scene geometry and GPU sources."""
from fractions import Fraction as F
from itertools import product
import heapq
import json


def weight(prefix, q):
    result = F(1)
    for i, token in enumerate(prefix):
        result *= q[i]["AB".index(token)]
    return result


def enumerate_prefixes(q):
    return sorted(
        ((weight(p, q), "".join(p)) for d in range(1, len(q) + 1)
         for p in product("AB", repeat=d)),
        key=lambda x: (-x[0], x[1]),
    )


def heap_select(q, budget):
    heap = [(-q[0][0], "A")]
    selected, frontier = [], []
    while heap and len(selected) < budget:
        neg, p = heapq.heappop(heap)
        selected.append((p, -neg))
        if p[-1] == "A":
            sib = p[:-1] + "B"
            heapq.heappush(heap, (-weight(sib, q), sib))
        if len(p) < len(q):
            child = p + "A"
            heapq.heappush(heap, (-weight(child, q), child))
        frontier.append([(p, float(-w)) for w, p in sorted(heap)])
    return selected, frontier


def walk(children, posterior):
    accepted = [0]
    while posterior[accepted[-1]] in children[accepted[-1]]:
        accepted.append(children[accepted[-1]][posterior[accepted[-1]]])
    return accepted, posterior[accepted[-1]]


def check():
    q = [[F(6, 10), F(4, 10)], [F(7, 10), F(3, 10)], [F(8, 10), F(2, 10)]]
    assert all(sum(row) == 1 for row in q)
    selected, frontier = heap_select(q, 5)
    assert [p for p, _ in selected] == ["A", "AA", "B", "AAA", "BA"]
    assert [v for _, v in selected] == [F(3, 5), F(42, 100), F(2, 5), F(336, 1000), F(28, 100)]
    exhaustive = enumerate_prefixes(q)
    assert [(v, p) for p, v in selected] == exhaustive[:5]
    assert exhaustive[5] == (F(224, 1000), "BAA")
    assert weight("AB", q) == F(18, 100)
    tree = {p for p, _ in selected}
    expectation = F(0)
    for tokens in product("AB", repeat=3):
        s = "".join(tokens)
        alpha = max([0] + [d for d in range(1, 4) if s[:d] in tree])
        expectation += weight(s, q) * alpha
    assert expectation == sum(v for _, v in selected) == F(2036, 1000)
    assert [sum(v for p, v in selected if len(p) == d) for d in (1, 2, 3)] == [F(1), F(7, 10), F(336, 1000)]
    concentrated = [[F(9, 10), F(1, 10)], [F(9, 10), F(1, 10)], [F(8, 10), F(2, 10)]]
    other, _ = heap_select(concentrated, 3)
    assert other == [("A", F(9, 10)), ("AA", F(81, 100)), ("AAA", F(648, 1000))]
    prefixes = ["", "A", "AA", "B", "AAA", "BA"]
    positions = [len(p) for p in prefixes]
    assert positions == [0, 1, 2, 1, 3, 2]
    parents = [-1] + [prefixes.index(p[:-1]) for p in prefixes[1:]]
    assert parents == [-1, 0, 1, 0, 2, 3]
    visibility = [[p.startswith(a) for a in prefixes] for p in prefixes]
    assert visibility[5] == [True, False, False, True, False, True]
    children = [{} for _ in prefixes]
    for i, p in enumerate(prefixes[1:], 1):
        children[parents[i]][p[-1]] = i
    accepted, bonus = walk(children, ["B", "A", "B", "A", "A", "B"])
    assert accepted == [0, 3, 5] and bonus == "B"
    assert [("b" if not prefixes[i] else prefixes[i][-1]) for i in accepted] == ["b", "B", "A"]
    assert walk(children, ["X"] * 6) == ([0], "X")
    assert walk(children, ["A", "A", "A", "A", "B", "B"]) == ([0, 1, 2, 4], "B")
    # Final stop-token cleanup includes first generated stop token, not later speculative outputs.
    out = ["b", "B", "STOP", "A"]
    assert out[:out.index("STOP") + 1] == ["b", "B", "STOP"]
    # Check every budget of both tiny distributions against exhaustive ranking.
    for distribution in (q, concentrated):
        all_nodes = enumerate_prefixes(distribution)
        for budget in range(1, 15):
            got, _ = heap_select(distribution, budget)
            assert sum(w for _, w in got) == sum(w for w, _ in all_nodes[:budget])
            assert all(len(p) == 1 or p[:-1] in {t for t, _ in got} for p, _ in got)
    return {"status": "passed", "method": "Fraction arithmetic; exhaustive continuation expectation; independent heap and prefix enumeration",
            "selected": [(p, float(v)) for p, v in selected], "frontiers": frontier,
            "expectation": float(expectation), "positions": positions, "parents": parents,
            "visibility": visibility, "accepted_indices": accepted, "bonus": bonus,
            "checks": ["all displayed products", "all main heap states", "root outside B", "contrast", "budget sweep 1–14", "ancestor mask", "depth positions", "mismatch", "leaf", "stop retention"]}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
