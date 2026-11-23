"""Terrain generation and water-flow simulation.

The answer key for every question is derived from these functions, never from
an AI model: priority-flood fills depressions, D8 routing sends each cell's
water to its steepest-descent neighbour, and flow accumulation gives stream size.
"""
import heapq
import math

import numpy as np

N = 160                      # grid cells per side
CELL_M = 25                  # metres per cell -> 4 km x 4 km region
L_KM = N * CELL_M / 1000
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def params(level):
    """Difficulty dial (the 'eye exam'): level 1 = easy, 5 = hard."""
    return dict(
        level=level,
        beta=3.8 - 0.3 * (level - 1),          # lower = rougher terrain, more ridges
        relief_m=22 + 8 * (level - 1),          # height of hills
        contour_m=10 if level <= 2 else 5,      # contour interval on the map style
        stream_cells=260 - 40 * (level - 1),    # lower = more (distractor) streams
        main_cells=2500,
        n_villages=3 + level,
        n_farms=min(6, 2 + level),
    )


def fractal(rng, beta, n=N):
    """Fractal noise in [0, 1] via spectral synthesis (power ~ 1/f^beta)."""
    kx = np.fft.fftfreq(n)[:, None]
    ky = np.fft.fftfreq(n)[None, :]
    k = np.hypot(kx, ky)
    k[0, 0] = 1
    spec = (rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))) / k ** (beta / 2)
    spec[0, 0] = 0
    z = np.real(np.fft.ifft2(spec))
    return (z - z.min()) / (z.max() - z.min())


def outlet_mask(outlet="south"):
    """Cells where water leaves the region: the south edge (synthetic) or every edge (real terrain)."""
    m = np.zeros((N, N), bool)
    m[N - 1, :] = True
    if outlet == "all":
        m[0, :] = m[:, 0] = m[:, N - 1] = True
    return m


def priority_flood(z, outlet="south"):
    """Fill depressions so every cell drains to an outlet cell."""
    filled = z.copy()
    closed = np.zeros(z.shape, bool)
    pq = []
    for y, x in zip(*np.nonzero(outlet_mask(outlet))):
        heapq.heappush(pq, (z[y, x], y, x))
        closed[y, x] = True
    while pq:
        e, y, x = heapq.heappop(pq)
        for dy, dx in N8:
            ny, nx = y + dy, x + dx
            if 0 <= ny < N and 0 <= nx < N and not closed[ny, nx]:
                closed[ny, nx] = True
                filled[ny, nx] = max(z[ny, nx], e + 1e-3)
                heapq.heappush(pq, (filled[ny, nx], ny, nx))
    return filled


def d8_receivers(filled, outlet="south"):
    """Flat index of the steepest-descent neighbour of each cell (-1 = outlet)."""
    rec = -np.ones((N, N), int)
    best = np.zeros((N, N))
    pad = np.pad(filled, 1, constant_values=np.inf)
    rows, cols = np.mgrid[0:N, 0:N]
    for dy, dx in N8:
        nb = pad[1 + dy:1 + dy + N, 1 + dx:1 + dx + N]
        slope = (filled - nb) / math.hypot(dy, dx)
        better = slope > best
        best = np.where(better, slope, best)
        rec = np.where(better, (rows + dy) * N + (cols + dx), rec)
    rec[outlet_mask(outlet)] = -1
    return rec.ravel()


def accumulate(filled, rec):
    """Number of upstream cells draining through each cell."""
    acc = np.ones(N * N)
    for i in np.argsort(-filled, axis=None):
        if rec[i] >= 0:
            acc[rec[i]] += acc[i]
    return acc.reshape(N, N)


def trace(rec, i):
    """Downstream path of water released at cell i, until it leaves the region."""
    path = [int(i)]
    while rec[i] >= 0:
        i = rec[i]
        path.append(int(i))
    return path


def rc(i):
    return divmod(int(i), N)


def dist(a, b):
    (ra, ca), (rb, cb) = rc(a), rc(b)
    return math.hypot(ra - rb, ca - cb)


def km(i):
    r, c = rc(i)
    return ((c + 0.5) * CELL_M / 1000, (r + 0.5) * CELL_M / 1000)


def polyline_length_m(cells):
    """Length in metres of a path of cells after the same smoothing the renderers use
    (5-point moving average, then 3 rounds of Chaikin corner-cutting)."""
    pts = [((rc(i)[1] + 0.5) * CELL_M, (rc(i)[0] + 0.5) * CELL_M) for i in cells]
    if len(pts) < 2:
        return 0.0
    if len(pts) > 4:
        xs = np.convolve(np.pad([q[0] for q in pts], 2, mode="edge"), np.ones(5) / 5, "valid")
        ys = np.convolve(np.pad([q[1] for q in pts], 2, mode="edge"), np.ones(5) / 5, "valid")
        pts = [pts[0]] + list(zip(xs[1:-1], ys[1:-1])) + [pts[-1]]
    for _ in range(3):
        new = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            new += [(.75 * ax + .25 * bx, .75 * ay + .25 * by), (.25 * ax + .75 * bx, .25 * ay + .75 * by)]
        new.append(pts[-1])
        pts = new
    return float(sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:])))
