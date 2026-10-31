"""Stickreihenfolge planen: Teile so ordnen, dass die Summe aller Wege dazwischen am kleinsten
ist – statt immer nur zum gerade nächstgelegenen Teil zu springen (das lässt oft einzelne Teile
liegen, zu denen am Ende quer über das Motiv zurückgesprungen werden muss).

Bis 9 Teile wird die beste Reihenfolge exakt gesucht, darüber mit »nächster Nachbar« von
mehreren Anfängen aus plus Nachbessern (Teile bzw. Teilstücke an bessere Stellen verschieben).
"""
from itertools import combinations

EXACT = 9           # bis zu so vielen Teilen exakt
HEURISTIC = 80      # darüber zu aufwendig – Aufrufer nimmt dann den einfachen Weg


def order(n, cost, start=None, pred=None, end=None):
    """Reihenfolge der Teile 0…n-1 mit der kleinsten Summe von cost(i, j).
    start(i): Kosten der Anfahrt zum ersten Teil (None: alle gleich).
    pred[j]: Teile, die vor j drankommen müssen (z. B. weil j sie überdeckt).
    end: Teil, das zuletzt kommen muss. Bei Gleichstand gewinnt die ursprüngliche Reihenfolge.
    None, wenn sich die Bedingungen widersprechen."""
    if n <= 1:
        return list(range(n))
    pred = pred or [set() for _ in range(n)]
    s0 = [start(i) if start else 0.0 for i in range(n)]
    c = [[cost(i, j) if i != j else 0.0 for j in range(n)] for i in range(n)]
    ident = list(range(n))
    if _valid(ident, pred, end):
        base = _length(ident, c, s0)
    else:
        base = None
    if n <= EXACT:
        best = _exact(n, c, s0, pred, end)
    else:
        best = _improve(_greedy_best(n, c, s0, pred, end), c, s0, pred, end)
    if best is None:
        return ident if base is not None else None
    if base is not None and _length(best, c, s0) >= base - 1e-6:
        return ident
    return best


def _valid(seq, pred, end):
    seen = set()
    for j in seq:
        if not pred[j] <= seen:
            return False
        seen.add(j)
    return end is None or seq[-1] == end


def _length(seq, c, s0):
    return s0[seq[0]] + sum(c[a][b] for a, b in zip(seq, seq[1:]))


def _exact(n, c, s0, pred, end):
    """Held-Karp: beste Reihenfolge über alle Teilmengen."""
    full = (1 << n) - 1
    pmask = [sum(1 << i for i in pred[j]) for j in range(n)]
    INF = float("inf")
    dp = {}
    for j in range(n):
        if pmask[j] == 0 and (end != j or n == 1):
            dp[(1 << j, j)] = (s0[j], None)
    for size in range(1, n):
        for subset in combinations(range(n), size):
            m = sum(1 << i for i in subset)
            for last in subset:
                cur = dp.get((m, last))
                if cur is None:
                    continue
                for j in range(n):
                    if m & (1 << j) or (pmask[j] & m) != pmask[j]:
                        continue
                    if j == end and size != n - 1:
                        continue
                    v = cur[0] + c[last][j]
                    key = (m | (1 << j), j)
                    if v < dp.get(key, (INF,))[0] - 1e-9:
                        dp[key] = (v, last)
    ends = [(dp[(full, j)][0], j) for j in range(n) if (full, j) in dp]
    if not ends:
        return None
    _, j = min(ends)
    seq, m = [], full
    while j is not None:
        seq.append(j)
        prev = dp[(m, j)][1]
        m &= ~(1 << j)
        j = prev
    return seq[::-1]


def _greedy_best(n, c, s0, pred, end):
    """Nächster Nachbar von mehreren Anfängen aus – der kürzeste Gesamtweg gewinnt."""
    starts = sorted(range(n), key=lambda j: s0[j])[:12]
    best = None
    for st in starts:
        if pred[st] or (st == end and n > 1):
            continue
        seq, placed = [st], {st}
        while len(seq) < n:
            cand = [j for j in range(n) if j not in placed and pred[j] <= placed
                    and (j != end or len(seq) == n - 1)]
            if not cand:
                break
            j = min(cand, key=lambda k: (c[seq[-1]][k], k))
            seq.append(j)
            placed.add(j)
        if len(seq) == n:
            L = _length(seq, c, s0)
            if best is None or L < best[0]:
                best = (L, seq)
    return best[1] if best else None


def _improve(seq, c, s0, pred, end, limit=400):
    """Nachbessern: Stücke aus 1–3 Teilen an eine bessere Stelle verschieben (Or-opt)."""
    if seq is None:
        return None
    n = len(seq)

    def w(a, b):                        # -1 = Anfahrt, n = Ende (kostet nichts)
        if b == n:
            return 0.0
        return s0[b] if a < 0 else c[a][b]
    for _ in range(limit):
        ext = [-1] + seq + [n]
        found = None
        for k in (1, 2, 3):
            for i in range(1, n - k + 2):
                piece = ext[i:i + k]
                inner = sum(c[a][b] for a, b in zip(piece, piece[1:]))
                gain = w(ext[i - 1], piece[0]) + w(piece[-1], ext[i + k]) - w(ext[i - 1], ext[i + k])
                rest = ext[:i] + ext[i + k:]
                for p in range(len(rest) - 1):
                    if p == i - 1:
                        continue
                    x, y = rest[p], rest[p + 1]
                    if y == -1:
                        continue
                    add = w(x, piece[0]) + w(piece[-1], y) - w(x, y)
                    if add - gain < -1e-6:
                        cand = rest[1:p + 1] + piece + rest[p + 1:-1]
                        if _valid(cand, pred, end):
                            found = cand
                            break
                if found:
                    break
            if found:
                break
        if not found:
            break
        seq = found
    return seq
