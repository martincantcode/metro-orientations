"""
Radial vs. tangential transit roses  (v2)
-----------------------------------------
For every metro line piece: the angle between the track and the direction
from a chosen centre. 0° = runs to/from the centre, 90° = runs around it.

The rose is mirrored four ways: to/from the centre points up and down,
around points left and right. Wedge AREA = share of track length, stacked
in each line's own OSM colour. A faint map of the network sits underneath.

Usage:
    python -m pip install requests geopandas shapely pyproj matplotlib
    python radial_roses.py              # downloads once, caches in ./cache
    python radial_roses.py --refetch    # force a fresh download

Outputs per city: <slug>_rose.png (1080x1350, Instagram 4:5) and
<slug>_lines.gpkg (segments with angle field, for QGIS).
"""
import math, json, os, sys, time, requests
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import re
from matplotlib.patches import Rectangle, Circle
from matplotlib.collections import LineCollection
from shapely.geometry import LineString, Point, Polygon

OVERPASS_SERVERS = [  # tried in order; the main server often returns 502/504 when busy
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

CITIES = {
    # lines: the official lines to keep, ref -> legend name (anything else is dropped).
    # ref_from_name: give a ref to relations that have none, by a piece of their name.
    # colours: fill in or correct colours that OSM is missing.
    "tokyo": dict(
        title="Tokyo", area="東京都", admin_level=4,
        scope="The 13 Tokyo Metro and Toei subway lines. Through-services onto other railways are not included.",
        centre=(35.6812, 139.7671), centre_name="Tokyo Station", routes=["subway"],
        # the 13 subway lines only; through-services onto private railways are dropped
        operators=["東京地下鉄", "東京都交通局", "東京メトロ", "都営", "Tokyo Metro", "Toei"],
        lines={"G": "Ginza", "M": "Marunouchi", "H": "Hibiya", "T": "Tozai", "C": "Chiyoda",
               "Y": "Yurakucho", "Z": "Hanzomon", "N": "Namboku", "F": "Fukutoshin",
               "A": "Asakusa", "I": "Mita", "S": "Shinjuku", "E": "Oedo"}),
    "beijing": dict(
        title="Beijing", area="北京市", admin_level=4,
        scope="Beijing Subway within Beijing municipality. Batong and Daxing sections counted as part of lines 1 and 4.",
        centre=(39.9087, 116.3975), centre_name="Tiananmen", routes=["subway"],
        # 1 and 4 already include the Batong and Daxing sections, so 1E and 4S would count them twice
        lines={"1": "1 / Batong", "2": "2", "3": "3", "4": "4 / Daxing", "5": "5", "6": "6", "7": "7",
               "8": "8", "9": "9", "10": "10", "11": "11", "12": "12", "13": "13", "14": "14",
               "15": "15", "16": "16", "17": "17", "18": "18", "19": "19",
               "24;L2": "Yizhuang", "25N": "Fangshan", "25S": "Yanfang", "27": "Changping",
               "L1": "Capital Airport Exp.", "DAX": "Daxing Airport Exp."},
        ref_from_name={"12号线": "12", "大兴机场线": "DAX"},
        # Yanfang has no colour in OSM; Fangshan's is used as a stand-in, so check the official one
        colours={"DAX": "#3F48CC", "25S": "#D85F26"}),
    "paris": dict(
        title="Paris", area="Île-de-France", admin_level=4,
        scope="Métro lines 1–14, 3bis and 7bis. Airport shuttles and the Grand Paris Express are not included.",
        centre=(48.8566, 2.3522), centre_name="Hôtel de Ville", routes=["subway"],
        # Paris lines go by number; airport shuttles and line 15 (not open yet at last check) are left out
        lines={r: r for r in ["1", "2", "3", "3bis", "4", "5", "6", "7", "7bis", "8", "9",
                              "10", "11", "12", "13", "14"]}),
    "mexico": dict(
        title="Mexico City", area="Ciudad de México", admin_level=4,
        scope="All 12 lines of the STC Metro (1–9, 12, A and B).",
        centre=(19.4326, -99.1332), centre_name="Zócalo", routes=["subway"],
        lines={r: r for r in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "12", "A", "B"]}),
    # ---- added cities: area names and tags are my best guess, so check them with inspect_lines.py ----
    "london": dict(
        title="London", area="Greater London", admin_level=5,
        centre=(51.5073, -0.1276), centre_name="Charing Cross", routes=["subway"],
        scope="The 11 London Underground lines. Elizabeth line, Overground and DLR are not included.",
        lines={n: n for n in ['Bakerloo', 'Central', 'Circle', 'District', 'Hammersmith & City', 'Jubilee', 'Metropolitan', 'Northern', 'Piccadilly', 'Victoria', 'Waterloo & City']},
        ref_from_name={n: n for n in ['Bakerloo', 'Central', 'Circle', 'District', 'Hammersmith & City', 'Jubilee', 'Metropolitan', 'Northern', 'Piccadilly', 'Victoria', 'Waterloo & City']}),
    "nyc": dict(
        title="New York", area="City of New York", admin_level=5,
        bbox=(40.49, -74.26, 40.92, -73.69),   # the five boroughs; the area query timed out
        timeout=400, maxsize=1073741824,       # big network: ask for more time and memory
        centre=(40.7580, -73.9855), centre_name="Times Square", routes=["subway"],
        scope="New York City Subway services. PATH and the Staten Island Railway are not included.",
        operators=["MTA", "New York City Transit", "NYC Subway", "NYCT"],
        lines={n: n for n in ['1', '2', '3', '4', '5', '6', '7', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'J', 'L', 'M', 'N', 'Q', 'R', 'W', 'Z', 'S']}),
    "glasgow": dict(
        title="Glasgow", area="Glasgow City", admin_level=6,
        centre=(55.8609, -4.2514), centre_name="Buchanan Street", routes=["subway"],
        scope="The Glasgow Subway: one loop line, inner and outer circle on separate tracks.",
        lines={"Subway": "Subway"}, ref_from_name={"Subway": "Subway", "Circle": "Subway"},
        colours={"Subway": "#FF6200"}),
    "barcelona": dict(
        title="Barcelona", area="Barcelona", admin_level=8,
        centre=(41.3870, 2.1701), centre_name="Plaça de Catalunya", routes=["subway"],
        scope="TMB metro lines. FGC suburban lines are not included.",
        lines={n: n for n in ['L1', 'L2', 'L3', 'L4', 'L5', 'L9N', 'L9S', 'L10N', 'L10S', 'L11']}),
    "chicago": dict(
        title="Chicago", area="Chicago", admin_level=8,
        bbox=(41.64, -87.95, 42.07, -87.52),
        centre=(41.8818, -87.6278), centre_name="the Loop", routes=["subway", "light_rail"],
        scope="The 8 lines of the CTA 'L', elevated and underground.",
        operators=["Chicago Transit Authority", "CTA"],
        lines={c: c for c in ["Red", "Blue", "Brown", "Green", "Orange", "Pink", "Purple", "Yellow"]},
        ref_from_name={f"{c} Line": c for c in ["Red", "Blue", "Brown", "Green", "Orange", "Pink",
                                                 "Purple", "Yellow"]}),
    "vienna": dict(
        title="Vienna", area="Wien", admin_level=4,
        bbox=(48.11, 16.18, 48.33, 16.58),
        centre=(48.2085, 16.3731), centre_name="Stephansplatz", routes=["subway", "light_rail"],
        scope="The Vienna U-Bahn lines in service. Trams, S-Bahn and the Badner Bahn are not included.",
        operators=["Wiener Linien"],
        lines={u: u for u in ["U1", "U2", "U3", "U4", "U5", "U6"]}),
}

# ---- look ---------------------------------------------------------------
BG, FG, MUTED, GRID = "#1e1c1a", "#f2efe9", "#9a948b", "#3a3631"
FONT = "Lato"
NOT_IN_SERVICE = {"construction", "proposed", "disused", "abandoned", "razed"}
BIN_WIDTH = 10      # degrees -> 36 compass sectors around the centre
SPLIT = 45          # track within 45° of pointing at the centre counts as "to/from", the rest as "around"
HATCH_SPACING = 0.012  # stripe spacing, as a fraction of the rose radius
STRIPE_WIDTH = 0.7     # stripe line width (pt)
BAND_TINT = 0.18       # faint fill behind the stripes so each band reads as a shape (0 = none)
GAP = 0.8              # degrees of empty space between neighbouring wedges
MAX_PIECE = 100     # m, track is split into pieces no longer than this
MIN_DIST = 500      # m, pieces closer than this to the centre are ignored
ROSE_FILL = 0.62    # longest wedge reaches this fraction of the map radius
MAP_EXTENT_PCT = 92 # this percentile of track distance from the centre ...
MAP_ZOOM_OUT = 1.0  # ... reaches the rose's outer circle; >1 shows more of the network
MAP_ALPHA = 0.55    # opacity of the network underneath
SUBTITLE = "Which way do the metro lines run?"
FOOTER = "#30DayMapChallenge · Day 25 · Is this a map? · Data © OpenStreetMap contributors"


def setup_font():
    for f in font_manager.findSystemFonts() + font_manager.findSystemFonts(fontpaths=["fonts"]):
        if "lato" in os.path.basename(f).lower():
            font_manager.fontManager.addfont(f)
    names = {f.name for f in font_manager.fontManager.ttflist}
    if FONT in names:
        plt.rcParams["font.family"] = FONT
    else:
        print(f"! {FONT} not found, using default font")


# ---- data -----------------------------------------------------------------
def fetch(slug, city, refetch=False):
    os.makedirs("cache", exist_ok=True)
    path = f"cache/{slug}.json"
    if os.path.exists(path) and not refetch:
        cached = json.load(open(path, encoding="utf-8"))
        if any(e["type"] == "relation" for e in cached):
            return cached
        print(f"  {slug}: cached download is empty, downloading again")
    route_re = "|".join(city["routes"])
    if city.get("bbox"):
        # a plain bounding box (south, west, north, east) is much lighter for Overpass than an area
        s_, w_, n_, e_ = city["bbox"]
        where = f"({s_},{w_},{n_},{e_})"
        head = ""
    else:
        where = "(area.a)"
        head = f'area["name"="{city["area"]}"]["admin_level"="{city["admin_level"]}"]->.a;'
    # modest limits by default: Overpass turns away "expensive-looking" queries first when busy
    settings = f"[out:json][timeout:{city.get('timeout', 180)}]"
    if city.get("maxsize"):
        settings += f"[maxsize:{city['maxsize']}]"
    settings += ";"
    q = f"""
    {settings}
    {head}
    rel{where}["type"="route"]["route"~"^({route_re})$"];
    out body;
    way(r)["railway"];
    out geom;
    """
    last = None
    for attempt in range(2):
        for url in OVERPASS_SERVERS:
            try:
                r = requests.post(url, data={"data": q}, timeout=city.get("timeout", 180) + 60,
                                  headers={"User-Agent": "30DayMapChallenge radial roses"})
                r.raise_for_status()
                data = r.json()
                els = data["elements"]
                if not any(e["type"] == "relation" for e in els):
                    # Overpass answers a timeout with an empty result plus a "remark", not an error
                    raise RuntimeError(data.get("remark") or "no routes found - check area name / admin_level")
                break
            except Exception as e:
                last = e
                print(f"  {url.split('/')[2]}: {e.__class__.__name__}: {str(e)[:120]} - trying next server")
                time.sleep(10)
        else:
            continue
        break
    else:
        raise RuntimeError(f"all Overpass servers failed: {last}")
    json.dump(els, open(path, "w", encoding="utf-8"))
    return els


def relation_ref(t, city):
    """Line key of a route: from city["ref_from_name"] if a listed piece of text is in its
    name, otherwise its ref tag, otherwise its name."""
    if city:
        for part, r in city.get("ref_from_name", {}).items():
            if part in t.get("name", ""):
                return r
    ref = str(t.get("ref", "")).strip()
    return ref or t.get("name", "?")


def keep_relation(t, city):
    """Per-city filters: official line list, operator whitelist, refs to drop."""
    if city is None:
        return True
    ref = relation_ref(t, city)
    if "lines" in city and ref not in city["lines"]:
        return False
    if ref in city.get("exclude_refs", []):
        return False
    ops = city.get("operators")
    if ops:
        text = " ".join(t.get(k, "") for k in ("operator", "network", "operator:en", "network:en"))
        return any(o.lower() in text.lower() for o in ops)
    return True


def line_name(ref, city):
    """Legend label: the readable name from the city's line list, else the ref."""
    return (city or {}).get("lines", {}).get(ref, ref)


def build_lines(elements, city=None):
    ways = {e["id"]: e for e in elements if e["type"] == "way"}
    rels = [e for e in elements if e["type"] == "relation"]
    # colour per line: city override > any relation of that line that has one > grey
    known = {}
    for rel in rels:
        t = rel.get("tags", {})
        c = t.get("colour") or t.get("color")
        if c:
            known.setdefault(relation_ref(t, city), c)
    if city:
        known.update(city.get("colours", {}))
    rows, seen = [], set()
    for rel in rels:
        t = rel.get("tags", {})
        if not keep_relation(t, city):
            continue
        if t.get("state") in ("proposed", "construction") or t.get("disused") == "yes":
            continue
        ref = relation_ref(t, city)
        colour = known.get(ref, "#888888")
        for m in rel.get("members", []):
            if m["type"] != "way" or m.get("role", "") not in ("", "forward", "backward"):
                continue
            w = ways.get(m["ref"])
            if not w or "geometry" not in w:
                continue
            if w.get("tags", {}).get("railway") in NOT_IN_SERVICE:
                continue                         # e.g. Grand Paris Express lines still being built
            key = (w["id"], ref)
            if key in seen:
                continue
            seen.add(key)
            coords = [(p["lon"], p["lat"]) for p in w["geometry"]]
            if len(coords) >= 2:
                rows.append(dict(line=ref, colour=colour, way_id=w["id"], geometry=LineString(coords)))
    if not rows:
        return gpd.GeoDataFrame(columns=["line", "colour", "way_id", "geometry"], geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def radial_segments(gdf, centre_latlon):
    utm = gdf.estimate_utm_crs()
    g = gdf.to_crs(utm)
    c = gpd.GeoSeries([Point(centre_latlon[1], centre_latlon[0])], crs=4326).to_crs(utm).iloc[0]
    out = []
    for _, row in g.iterrows():
        geom = row.geometry
        n = max(1, int(math.ceil(geom.length / MAX_PIECE)))
        xy = [geom.interpolate(i / n, normalized=True).coords[0] for i in range(n + 1)]
        for (x1, y1), (x2, y2) in zip(xy[:-1], xy[1:]):
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy)
            if L < 1:
                continue
            mx, my = (x1 + x2) / 2 - c.x, (y1 + y2) / 2 - c.y
            R = math.hypot(mx, my)
            if R < MIN_DIST:
                continue
            ang = math.degrees(math.acos(min(1.0, abs(dx * mx + dy * my) / (L * R))))
            pos = math.degrees(math.atan2(mx, my)) % 360   # where it is: 0 = north, 90 = east
            # signed angle of the track relative to the radius, folded to (-90, 90]
            sang = (math.degrees(math.atan2(dx, dy)) - pos + 180) % 360 - 180
            sang = sang - 180 if sang > 90 else sang + 180 if sang <= -90 else sang
            out.append(dict(line=row.line, colour=row.colour, length=L, angle=ang, sangle=sang, pos=pos,
                            dist_km=R / 1000, geometry=LineString([(x1, y1), (x2, y2)])))
    return gpd.GeoDataFrame(out, crs=utm), (c.x, c.y)


def shares(seg):
    w = seg["length"].sum()
    return (seg.loc[seg.angle < SPLIT, "length"].sum() / w,
            seg.loc[seg.angle >= SPLIT, "length"].sum() / w)


# ---- drawing --------------------------------------------------------------
def draw(seg, lines_utm, centre_xy, city, path):
    total = seg["length"].sum()
    nb = 360 // BIN_WIDTH
    seg = seg.assign(sector=(seg["pos"] // BIN_WIDTH).astype(int) % nb,
                     radial=seg["angle"] < SPLIT)
    legend = (seg.groupby(["line", "colour"])["length"].sum()
                 .sort_values(ascending=False).reset_index())

    # per compass sector, stacked by line (longest innermost). For each band keep the
    # length-weighted mean direction of its track (axial mean via doubled angles).
    g = seg.assign(w=seg["length"],
                   c2=seg["length"] * np.cos(np.radians(2 * seg["sangle"])),
                   s2=seg["length"] * np.sin(np.radians(2 * seg["sangle"])))
    band = g.groupby(["sector", "line"])[["w", "c2", "s2"]].sum()
    cum = np.zeros(nb)
    layers = []   # (colour, sector, lo, hi, mean_angle)
    for _, r in legend.iterrows():
        for sec in range(nb):
            if (sec, r.line) not in band.index:
                continue
            b = band.loc[(sec, r.line)]
            hi = cum[sec] + b.w / total
            mean = 0.5 * math.degrees(math.atan2(b.s2, b.c2))
            layers.append((r.colour, sec, cum[sec], hi, mean))
            cum[sec] = hi
    rmax = math.sqrt(cum.max()) / ROSE_FILL   # sqrt -> wedge area ∝ share

    fig = plt.figure(figsize=(5.4, 6.75), dpi=200, facecolor=BG)
    w = 0.78
    box = [(1 - w) / 2, 0.193, w, w * 5.4 / 6.75]   # square panel for the rose

    # network underneath: full width, centred on the same point, extends well beyond the rose
    MAP_BOX = [0, 0.175, 1, 0.66]
    ax_m = fig.add_axes(MAP_BOX, facecolor="none", zorder=0)
    cx, cy = centre_xy
    half_x = np.percentile(seg["dist_km"], MAP_EXTENT_PCT) * 1000 * (0.5 / (w / 2)) * MAP_ZOOM_OUT
    half_y = half_x * (MAP_BOX[3] * 6.75) / (MAP_BOX[2] * 5.4)
    for colour, grp in lines_utm.groupby("colour"):
        grp.plot(ax=ax_m, color=colour, linewidth=0.8, alpha=MAP_ALPHA)
    ax_m.set_xlim(cx - half_x, cx + half_x); ax_m.set_ylim(cy - half_y, cy + half_y)
    ax_m.set_aspect("equal"); ax_m.axis("off")

    # rose on top, drawn as polygons so each band can be filled with stripes
    ax = fig.add_axes(box, facecolor="none")
    ax.set_xlim(-rmax, rmax); ax.set_ylim(-rmax, rmax); ax.set_aspect("equal"); ax.axis("off")
    spacing = rmax * HATCH_SPACING

    def pt(r, deg):
        return (r * math.sin(math.radians(deg)), r * math.cos(math.radians(deg)))

    strokes, colours, fills = [], [], []
    for colour, sec, lo, hi, mean in layers:
        r0, r1 = math.sqrt(lo), math.sqrt(hi)
        a0, a1 = sec * BIN_WIDTH + GAP / 2, (sec + 1) * BIN_WIDTH - GAP / 2
        arc = np.linspace(a0, a1, 12)
        poly = Polygon([pt(r1, a) for a in arc] + [pt(r0, a) for a in arc[::-1]] if r0 > 0
                       else [(0, 0)] + [pt(r1, a) for a in arc])
        if poly.area <= 0:
            continue
        fills.append((poly, colour))
        # stripes: direction = this sector's radius turned by the band's mean angle
        d = math.radians((sec + 0.5) * BIN_WIDTH + mean)
        dvec, nvec = (math.sin(d), math.cos(d)), (math.cos(d), -math.sin(d))
        cxp, cyp = poly.centroid.x, poly.centroid.y
        reach = r1 - r0 + r1 * math.radians(BIN_WIDTH) + spacing
        for k in np.arange(-reach, reach + 1e-9, spacing):
            ox, oy = cxp + k * nvec[0], cyp + k * nvec[1]
            ln = LineString([(ox - reach * dvec[0], oy - reach * dvec[1]),
                             (ox + reach * dvec[0], oy + reach * dvec[1])]).intersection(poly)
            for part in getattr(ln, "geoms", [ln]):
                if part.length > 0:
                    strokes.append(list(part.coords)); colours.append(colour)
    for poly, colour in fills:
        ax.fill(*poly.exterior.xy, color=colour, alpha=BAND_TINT, lw=0)
    ax.add_collection(LineCollection(strokes, colors=colours, linewidths=STRIPE_WIDTH, capstyle="butt"))
    t = np.linspace(0, 2 * np.pi, 200)
    for r in np.linspace(0, rmax * ROSE_FILL, 4)[1:]:
        ax.plot(r * np.sin(t), r * np.cos(t), color=GRID, lw=0.4, zorder=0)
    lab = dict(color=MUTED, fontsize=6.5, ha="center", va="center")
    for deg, txt in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
        ax.text(*pt(rmax * 1.0, deg), txt, **lab)
    ax.plot(0, 0, "o", ms=2.5, color=FG, zorder=10)

    # text
    rad, tan = shares(seg)
    fig.text(0.06, 0.965, city["title"], color=FG, fontsize=26, fontweight="black", va="top")
    fig.text(0.06, 0.895, SUBTITLE, color=FG, fontsize=9.5, va="top")
    fig.text(0.06, 0.867, f"{rad:.0%} of track runs to or from {city['centre_name']}, "
                          f"{tan:.0%} runs around it", color=MUTED, fontsize=7.5, va="top")

    # legend, in natural line order (1, 2, 3 … 10, A, B …)
    nat = lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(x))]
    legend = legend.iloc[sorted(range(len(legend)), key=lambda i: nat(legend.line[i]))].reset_index(drop=True)
    # skip labels Lato can't draw (e.g. Chinese names without a ref) and through-service combos like "DT;Z"
    ok = legend["line"].astype(str).map(lambda x: ";" not in x and len(x) <= 6
                                        and all(ord(ch) < 0x2000 for ch in x))
    legend = legend[ok].drop_duplicates(["line", "colour"]).reset_index(drop=True)
    n = len(legend)
    ncol = min(n, 8 if n > 16 else 6)
    ax_l = fig.add_axes([0.06, 0.08, 0.88, 0.095]); ax_l.axis("off")
    ax_l.set_xlim(0, ncol); ax_l.set_ylim(0, 1)
    rows = math.ceil(n / ncol)
    step = min(0.25, 1 / max(rows, 1))
    for i, r in legend.iterrows():
        col, row = i % ncol, i // ncol
        y = 1 - (row + 0.5) * step
        ax_l.add_patch(Rectangle((col + 0.02, y - step * 0.18), 0.22, step * 0.36,
                                 color=r.colour, transform=ax_l.transData))
        ax_l.text(col + 0.3, y, str(r.line), color=FG, fontsize=6, va="center")
    fig.text(0.06, 0.025, FOOTER, color=MUTED, fontsize=5.5)
    fig.text(0.06, 0.055, "Wedge = track lying in that direction from the centre (area = share of track).",
             color=MUTED, fontsize=5.5)
    fig.text(0.06, 0.04, "Stripes run the way the track runs: pointing at the centre = to/from it, across = around it.",
             color=MUTED, fontsize=5.5)

    fig.savefig(path, dpi=200, facecolor=BG)
    plt.close(fig)
    return rad, tan


def run(slug, city, elements=None, refetch=False):
    elements = elements if elements is not None else fetch(slug, city, refetch)
    lines = build_lines(elements, city)
    if lines.empty:
        print(f"{slug}: no lines found - check area name / admin_level"); return
    seg, centre_xy = radial_segments(lines, city["centre"])
    seg.to_file(f"{slug}_lines.gpkg", layer="segments", driver="GPKG")
    rad, tan = draw(seg, lines.to_crs(seg.crs), centre_xy, city, f"{slug}_rose.png")
    print(f"{slug:10s} lines={lines['line'].nunique():3d}  km={seg['length'].sum()/1000:7.1f}  "
          f"to/from={rad:.0%}  around={tan:.0%}")


if __name__ == "__main__":
    setup_font()
    refetch = "--refetch" in sys.argv
    for slug, city in CITIES.items():
        try:
            run(slug, city, refetch=refetch)
        except Exception as e:
            print(slug, "failed:", e)
        time.sleep(2)
