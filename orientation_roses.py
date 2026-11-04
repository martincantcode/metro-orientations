"""
Metro orientation roses  (after Geoff Boeing's street network orientation)
-------------------------------------------------------------------------
For every piece of metro track: its compass bearing. A track running
north-south counts for both N and S (a line has no front or back), so the
rose is symmetric, exactly like Boeing's street roses.

Steps
  1. download metro lines from OpenStreetMap (cached by radial_roses.py)
  2. cut them into 100 m pieces, in metres (UTM)
  3. bearing of each piece = atan2(dx, dy), 0 = north, 90 = east
  4. add the piece's length to the 10° bin of its bearing AND the opposite bin
  5. draw: bar area proportional to track length in that direction

Run (same folder as radial_roses.py):  python orientation_roses.py
Outputs: <slug>_orientation.png (one per city) and all_orientation.png (grid)
"""
import math, sys, time
import numpy as np
import matplotlib.pyplot as plt
import re
import geopandas as gpd
from shapely.geometry import Point
from matplotlib.patches import Rectangle
import radial_roses as rr

# Colour themes. "circle" fills the rose's disc; bars get a hairline in that colour.
THEMES = {
    "dark":  dict(bg=rr.BG, circle="none", fg=rr.FG, muted=rr.MUTED, grid=rr.GRID, gap=rr.BG),
    "light": dict(bg="#EEE8DC", circle="#FFFFFF", fg="#2A2622", muted="#857C70", grid="#E2DACB", gap="#FFFFFF"),
}
THEME = "light"   # "dark" or "light" - swap in your own hex codes above
T = THEMES[THEME]
BG, FG, MUTED, GRID = T["bg"], T["fg"], T["muted"], T["grid"]
BINS = 36             # 10° bins, centred on N, E, S, W like Boeing
STACK_BY_LINE = True  # True: bars stacked in each line's colour; False: one colour
ONE_COLOUR = "#e8a33d"
PIECE = 100           # m
SORT_GRID = True       # overview grid ordered by orientation order (False = order of CITIES)
GRID_GAP = 0.024       # overview grid: space reserved between a rose and the next row
TITLE_DROP = 0.01      # moves each title down into that space, closer to its own rose
INSET_TRIM = 2         # small map: % of outermost track (per side) allowed to run off the edge
INSET_LINE_WIDTH = 1.2 # line width in the small map
CREDIT = "martincreates.com"     # small signature, bottom right
FOOTER = "#30DayMapChallenge · Day 2 · Lines · Data © OpenStreetMap contributors · Method after Geoff Boeing"


def bearings(lines_utm):
    rows = []
    for _, row in lines_utm.iterrows():
        g = row.geometry
        n = max(1, int(math.ceil(g.length / PIECE)))
        xy = [g.interpolate(i / n, normalized=True).coords[0] for i in range(n + 1)]
        for (x1, y1), (x2, y2) in zip(xy[:-1], xy[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if L > 1:
                b = math.degrees(math.atan2(x2 - x1, y2 - y1)) % 180   # 0–180, the other half is mirrored
                rows.append((row.line, row.colour, b, L))
    return rows


def binned(rows):
    """Return per-line histograms over 36 bins (both directions), and line order."""
    width = 360 / BINS
    per_line = {}
    for line, colour, b, L in rows:
        h = per_line.setdefault((line, colour), np.zeros(BINS))
        for bb in (b, b + 180):
            h[int(((bb + width / 2) % 360) // width)] += L
    order = sorted(per_line, key=lambda k: -per_line[k].sum())
    return per_line, order


def order_index(hist):
    """Boeing's orientation order: 0 = all directions equally, 1 = perfect grid."""
    p = hist / hist.sum()
    p = p[p > 0]
    H = -(p * np.log(p)).sum()
    hmax, hgrid = math.log(BINS), math.log(4)
    return 1 - ((H - hgrid) / (hmax - hgrid)) ** 2


def draw_rose(ax, per_line, order, fontsize=6, circle=True, labels=True):
    gap = T["gap"] if circle else BG
    total = sum(h for h in per_line.values()).sum() / 2      # each piece counted twice
    theta = np.radians(np.arange(BINS) * 360 / BINS)
    width = np.radians(360 / BINS)
    cum = np.zeros(BINS)
    for key in order:
        h = per_line[key] / total
        lo, hi = np.sqrt(cum), np.sqrt(cum + h)               # sqrt -> bar AREA ∝ length
        ax.bar(theta, hi - lo, bottom=lo, width=width * 0.92,
               color=key[1] if STACK_BY_LINE else ONE_COLOUR, edgecolor=gap, linewidth=0.2)
        cum += h
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    ax.set_ylim(0, np.sqrt(cum.max()) * 1.05)
    ax.set_yticks([]); ax.set_facecolor(T["circle"] if circle else "none")
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N", "E", "S", "W"] if labels else [], color=MUTED, fontsize=fontsize)
    ax.tick_params(pad=-1)
    ax.spines["polar"].set_color(GRID); ax.grid(color=GRID, lw=0.4)
    return cum


def legend_entries(per_line, city=None):
    """(label, colour) pairs: readable names, in the order of the city's line list."""
    order = list((city or {}).get("lines", {}))
    nat = lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(x))]
    keys = sorted(per_line, key=lambda k: (order.index(k[0]) if k[0] in order else 999, nat(k[0])))
    out, seen = [], set()
    for line, colour in keys:
        lab = rr.line_name(line, city)
        if any(ord(ch) >= 0x3000 for ch in lab) or (lab, colour) in seen:
            continue
        seen.add((lab, colour)); out.append((lab, colour))
    return out


def single(slug, city, per_line, order, phi, lines_utm=None, centre_xy=None):
    fig = plt.figure(figsize=(5.4, 6.75), dpi=200, facecolor=BG)
    rose_w = 0.64
    rose_box = [(1 - rose_w) / 2, 0.29, rose_w, rose_w * 5.4 / 6.75]
    ax = fig.add_axes(rose_box, projection="polar")
    draw_rose(ax, per_line, order, fontsize=8)

    fig.text(0.06, 0.965, city["title"], color=FG, fontsize=26, fontweight="black", va="top")
    fig.text(0.06, 0.895, "Which way does the metro run?", color=FG, fontsize=9.5, va="top")
    fig.text(0.06, 0.867, f"Compass direction of every metro track, weighted by length · orientation order {phi:.2f}",
             color=MUTED, fontsize=7, va="top")
    if city.get("scope"):
        fig.text(0.06, 0.843, city["scope"], color=MUTED, fontsize=5.6, va="top")

    # bottom block: small icon-like network map on the left, legend on the right
    block_y, block_h = 0.082, 0.18
    map_w = block_h * 6.75 / 5.4                     # square in inches
    if lines_utm is not None:
        axm = fig.add_axes([0.04, block_y, map_w, block_h], facecolor="none")
        # frame the network itself (not the city centre), ignoring the outermost 2% of track
        pts = np.vstack([np.asarray(g.coords) for g in lines_utm.geometry])
        x0, x1 = np.percentile(pts[:, 0], [INSET_TRIM, 100 - INSET_TRIM])
        y0, y1 = np.percentile(pts[:, 1], [INSET_TRIM, 100 - INSET_TRIM])
        mx, my, half = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) / 2 * 1.05
        for colour, grp in lines_utm.groupby("colour"):
            grp.plot(ax=axm, color=colour, linewidth=INSET_LINE_WIDTH, capstyle="round")
        axm.set_xlim(mx - half, mx + half); axm.set_ylim(my - half, my + half)
        axm.set_aspect("equal"); axm.axis("off")

    entries = legend_entries(per_line, city)
    n = len(entries)
    longest = max((len(l) for l, _ in entries), default=1)
    ncol = 3 if longest > 12 else 4 if longest > 5 else 6 if n > 12 else 4
    lx = 0.04 + map_w + 0.04
    axl = fig.add_axes([lx, block_y, 0.94 - lx, block_h]); axl.axis("off")
    axl.set_xlim(0, ncol); axl.set_ylim(0, 1)
    rows = max(1, math.ceil(n / ncol))
    step = min(0.2, 1 / rows)
    for i, (lab, colour) in enumerate(entries):
        col, row = i % ncol, i // ncol
        y = 1 - (row + 0.5) * step
        u = ncol / 6                       # keeps swatches the same physical size for any column count
        axl.add_patch(Rectangle((col + 0.02 * u, y - step * 0.2), 0.25 * u, step * 0.4, color=colour))
        axl.text(col + 0.34 * u, y, lab, color=FG, fontsize=5.8, va="center")

    fig.text(0.06, 0.058, "Bar area = share of track running in that direction (a north–south track counts for N and S).",
             color=MUTED, fontsize=5.2)
    fig.text(0.06, 0.04, "Orientation order: 0 = no preferred direction, 1 = perfect grid.", color=MUTED, fontsize=5.2)
    fig.text(0.06, 0.02, FOOTER, color=MUTED, fontsize=5.2)
    fig.text(0.94, 0.02, CREDIT, color=MUTED, fontsize=5.6, fontweight="bold", ha="right")
    fig.savefig(f"{slug}_orientation.png", dpi=200, facecolor=BG)
    plt.close(fig)


def grid(results):
    n = len(results)
    cols = 2 if n <= 4 else 3
    rows = math.ceil(n / cols)
    fig = plt.figure(figsize=(5.4, 6.75), dpi=200, facecolor=BG)
    top, bottom = 0.87, 0.1
    cell_h = (top - bottom) / rows
    cell_w = 0.9 / cols
    label_h = 0.052                                   # room for city name + orientation order
    size = min(cell_w * 0.82, (cell_h - label_h - GRID_GAP) * 6.75 / 5.4)
    h = size * 5.4 / 6.75                             # rose height in figure units
    for i, (slug, city, per_line, order, phi) in enumerate(results):
        r, c = divmod(i, cols)
        cx = 0.05 + cell_w * (c + 0.5)
        cell_top = top - cell_h * r
        # label sits right above its own rose; the gap to the rose above is the rest of the cell
        rose_top = cell_top - label_h
        title_y = cell_top - TITLE_DROP                   # nudge the label down towards its own rose
        fig.text(cx, title_y, city["title"], color=FG, fontsize=10, fontweight="bold", ha="center", va="top")
        fig.text(cx, title_y - 0.027, f"orientation order {phi:.2f}", color=MUTED, fontsize=5.5,
                 ha="center", va="top")
        ax = fig.add_axes([cx - size / 2, rose_top - h, size, h], projection="polar")
        draw_rose(ax, per_line, order, fontsize=5, circle=False, labels=False)   # shapes, not colours
    # one north arrow for all roses
    fig.add_artist(plt.matplotlib.patches.FancyArrowPatch((0.93, 0.072), (0.93, 0.105), transform=fig.transFigure,
                   arrowstyle="-|>", mutation_scale=7, color=MUTED, lw=0.8))
    fig.text(0.93, 0.108, "N", color=MUTED, fontsize=6, ha="center", va="bottom")
    fig.text(0.06, 0.965, "Which way does the metro run?", color=FG, fontsize=18, fontweight="black", va="top")
    fig.text(0.06, 0.915, "Compass direction of every metro track, weighted by length, coloured by line",
             color=MUTED, fontsize=7, va="top")
    fig.text(0.06, 0.04, "Bar area = share of track running in that direction. Orientation order: 0 = no preferred "
                         "direction, 1 = perfect grid.", color=MUTED, fontsize=5.3)
    fig.text(0.06, 0.02, FOOTER, color=MUTED, fontsize=5.3)
    fig.text(0.94, 0.02, CREDIT, color=MUTED, fontsize=5.6, fontweight="bold", ha="right")
    fig.savefig("all_orientation.png", dpi=200, facecolor=BG)
    plt.rcParams["svg.fonttype"] = "none"            # keep text as editable text in the SVG
    fig.savefig("all_orientation.svg", facecolor=BG)
    plt.close(fig)


def run(slug, city, elements=None):
    elements = elements if elements is not None else rr.fetch(slug, city)
    lines = rr.build_lines(elements, city)
    if lines.empty:
        print(f"{slug}: no lines found"); return None
    utm = lines.to_crs(lines.estimate_utm_crs())
    per_line, order = binned(bearings(utm))
    phi = order_index(sum(per_line.values()))
    c = gpd.GeoSeries([Point(city["centre"][1], city["centre"][0])], crs=4326).to_crs(utm.crs).iloc[0]
    single(slug, city, per_line, order, phi, utm, (c.x, c.y))
    print(f"{slug:10s} orientation order = {phi:.2f}")
    return (slug, city, per_line, order, phi)


if __name__ == "__main__":
    rr.setup_font()
    results = []
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or list(rr.CITIES)
    for slug, city in rr.CITIES.items():
        if slug not in wanted:
            continue
        try:
            res = run(slug, city)
            if res:
                results.append(res)
        except Exception as e:
            print(slug, "failed:", e)
        time.sleep(1)
    if results:
        if SORT_GRID:   # most grid-like first, most scattered last
            results.sort(key=lambda r: -r[4])
        grid(results)
