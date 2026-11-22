"""Small, intentionally direct Python reference model for simulator tests."""
from __future__ import annotations


def simulate(addresses, operations, capacity_bytes, line_bytes, ways, policy="lru"):
    line_count = capacity_bytes // line_bytes
    sets = line_count // ways
    cache = [[None for _ in range(ways)] for _ in range(sets)]
    time = 0
    stats = dict(accesses=0, hits=0, misses=0, evictions=0, write_backs=0)
    for address, operation in zip(addresses, operations):
        stats["accesses"] += 1
        block = address // line_bytes
        set_id = block % sets
        tag = block // sets
        way_lines = cache[set_id]
        time += 1
        hit = next((line for line in way_lines if line is not None and line[0] == tag), None)
        if hit is not None:
            stats["hits"] += 1
            hit[2] = time
            if operation == "W":
                hit[1] = True
            continue
        stats["misses"] += 1
        index = next((idx for idx, line in enumerate(way_lines) if line is None), None)
        if index is not None:
            victim = None
        else:
            index = min(range(ways), key=lambda idx: way_lines[idx][3] if policy == "fifo" else way_lines[idx][2])
            victim = way_lines[index]
            stats["evictions"] += 1
            stats["write_backs"] += int(victim[1])
        # tag, dirty, last-use, insertion-time
        insertion = time
        way_lines[index] = [tag, operation == "W", time, insertion]
    return stats
