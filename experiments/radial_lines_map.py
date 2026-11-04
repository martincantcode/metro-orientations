"""
Radial lines map  (Day 2 · Lines)
---------------------------------
Every piece of metro track coloured by one thing: the angle it makes with
the direction to the centre. 0° (runs straight to/from the centre) -> warm,
90° (runs around it) -> cool, everything in between on a smooth gradient.
A small mirrored rose in the corner works as the legend and summary.

Reuses the download/caching code from radial_roses.py (keep both files in
the same folder). Run:  python radial_lines_map.py
"""
import math, sys, time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import radial_roses as rr

BG, FG, MUTED, GRID = rr.BG, rr.FG, rr.MUTED, rr.GRID
# to/from centre  ->  diagonal  ->  around
CMAP = LinearSegmentedColormap.from_list("radial", ["#ffb347", "#e8507a", "#8a5cf5", "#3ec5e0"])
LINE_WIDTH = 1.1
MAP_EXTENT_PCT = 85    # map half-width = this percentile of track distance from centre (long outliers run off the edge)
PIECE = 300            # m, longer pieces than the rose uses -> smoother colours along wiggly lines
ROSE_BIN = 10


def draw_map(seg, centre_xy, city, path):
    fig = plt.figure(figsize=(5.4, 6.75), dpi=200, facecolor=BG)

    # big map: full width, from below the title to above the footer
    ax = fig.add_axes([0, 0.06, 1, 0.80], facecolor=BG)
    cx, cy = centre_xy
    half = np.percentile(seg["dist_km"], MAP_EXTENT_PCT) * 1000
    segs = [list(g.coords) for g in seg.geometry]
    lc = LineCollection(segs, colors=CMAP(seg["angle"].values / 90), linewidths=LINE_WIDTH,
                        capstyle="round")
    ax.add_collection(lc)
    ax.plot(cx, cy, "o", ms=3, color=FG, zorder=5)
    ax.set_aspect("equal")
    ax.set_xlim(cx - half * 1.0, cx + half * 1.0)
    ax.set_ylim(cy - half * 1.25, cy + half * 1.0)   # a bit of room below for the rose
    ax.axis("off")

    # small mirrored rose as legend: angle only, coloured with the same gradient
    nb = 90 // ROSE_BIN
    total = seg["length"].sum()
    bins = np.clip((seg["angle"] // ROSE_BIN).astype(int), 0, nb - 1)
    share = seg.groupby(bins)["length"].sum().reindex(range(nb), fill_value=0).values / total
    r = np.sqrt(share)
    axr = fig.add_axes([0.66, 0.085, 0.30, 0.30 * 5.4 / 6.75], projection="polar", facecolor="none")
    axr.set_theta_zero_location("N"); axr.set_theta_direction(-1)
    centres = np.radians(np.arange(nb) * ROSE_BIN + ROSE_BIN / 2)
    cols = CMAP((np.arange(nb) * ROSE_BIN + ROSE_BIN / 2) / 90)
    for theta in (centres, -centres, np.pi - centres, np.pi + centres):
        axr.bar(theta, r, width=np.radians(ROSE_BIN), color=cols, edgecolor=BG, linewidth=0.4)
    axr.set_ylim(0, r.max() * 1.05)
    axr.set_xticks([]); axr.set_yticks([]); axr.spines["polar"].set_visible(False); axr.grid(False)
    fig.text(0.81, 0.07, "vertical: to / from centre    horizontal: around", color=MUTED, fontsize=5.3, ha="center")

    # text
    rad, tan = rr.shares(seg)
    fig.text(0.06, 0.965, city["title"], color=FG, fontsize=26, fontweight="black", va="top")
    fig.text(0.06, 0.895, "Do the metro lines run to the centre, or around it?", color=FG, fontsize=9.5, va="top")
    fig.text(0.06, 0.867, f"Measured from {city['centre_name']}: "
                          f"{rad:.0%} of track mostly heads to or from it, {tan:.0%} mostly circles it",
             color=MUTED, fontsize=7, va="top")
    fig.text(0.06, 0.045, "Colour = angle between the track and the direction to the centre "
                          "(0° = straight towards it, 90° = across it). Rose: share of track per angle.",
             color=MUTED, fontsize=5.3)
    fig.text(0.06, 0.025, "#30DayMapChallenge · Day 2 · Lines · Data © OpenStreetMap contributors", color=MUTED, fontsize=5.3)
    fig.savefig(path, dpi=200, facecolor=BG)
    plt.close(fig)


def run(slug, city, elements=None, refetch=False):
    elements = elements if elements is not None else rr.fetch(slug, city, refetch)
    lines = rr.build_lines(elements, city)
    if lines.empty:
        print(f"{slug}: no lines found - check area name / admin_level"); return
    rr.MAX_PIECE = PIECE
    seg, centre_xy = rr.radial_segments(lines, city["centre"])
    draw_map(seg, centre_xy, city, f"{slug}_map.png")
    rad, tan = rr.shares(seg)
    print(f"{slug:10s} to/from={rad:.0%}  around={tan:.0%}")


if __name__ == "__main__":
    rr.setup_font()
    refetch = "--refetch" in sys.argv
    for slug, city in rr.CITIES.items():
        try:
            run(slug, city, refetch=refetch)
        except Exception as e:
            print(slug, "failed:", e)
        time.sleep(2)
