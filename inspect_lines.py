"""
List every metro route in your cached OSM data, so you can check it against
the real network. Writes lines_check.csv and prints a table per city.

Run (same folder, after the other scripts have cached the data):
    python inspect_lines.py
Columns: kept (after the filters in radial_roses.CITIES), ref, colour,
name, name:en, operator, network, track km, from/to.
"""
import csv
import radial_roses as rr

rows = []
import sys
wanted = sys.argv[1:] or list(rr.CITIES)
for slug, city in rr.CITIES.items():
    if slug not in wanted:
        continue
    path = f"cache/{slug}.json"
    if not rr.os.path.exists(path):          # only reads the cache, never downloads
        print(f"{slug}: no cached data, run one of the map scripts first"); continue
    els = rr.json.load(open(path, encoding="utf-8"))
    ways = {e["id"]: e for e in els if e["type"] == "way"}
    print(f"\n=== {city['title']} ===")
    for rel in (e for e in els if e["type"] == "relation"):
        t = rel.get("tags", {})
        km = 0.0
        for m in rel.get("members", []):
            w = ways.get(m["ref"]) if m["type"] == "way" else None
            if w and "geometry" in w and m.get("role", "") in ("", "forward", "backward"):
                g = w["geometry"]
                for a, b in zip(g[:-1], g[1:]):
                    km += rr.math.hypot((b["lon"] - a["lon"]) * 111.3 * rr.math.cos(rr.math.radians(a["lat"])),
                                        (b["lat"] - a["lat"]) * 111.3)
        row = dict(city=slug, kept="yes" if rr.keep_relation(t, city) else "no",
                   ref=t.get("ref", ""), colour=t.get("colour", ""), name=t.get("name", ""),
                   name_en=t.get("name:en", ""), operator=t.get("operator", ""), network=t.get("network", ""),
                   km=round(km, 1), from_to=f"{t.get('from', '')} → {t.get('to', '')}",
                   osm=f"https://www.openstreetmap.org/relation/{rel['id']}")
        rows.append(row)
    for r in sorted((r for r in rows if r["city"] == slug), key=lambda r: (r["kept"], r["ref"])):
        print(f"{r['kept']:3s} {r['ref']:8s} {r['colour']:8s} {r['km']:6.1f} km  "
              f"{(r['name_en'] or r['name'])[:45]:45s} {r['operator'][:30]}")

if not rows:
    raise SystemExit("Nothing cached yet for these cities - run orientation_roses.py first.")
with open("lines_check.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("\nWrote lines_check.csv (open it in a spreadsheet; each row links to the OSM relation)")
