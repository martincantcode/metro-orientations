# Which way does the metro run?

Compass roses of metro networks, in the spirit of Geoff Boeing's [street network orientation](https://geoffboeing.com/2019/09/urban-street-network-orientation/) — but for subway track instead of streets. Made for the [#30DayMapChallenge](https://30daymapchallenge.com) 2026 (Day 2 · Lines).

![Overview](images/all_orientation.png)

Beijing's metro follows the old city's north–south axis, Manhattan's grid shows up as a tilted cross, Glasgow's single loop turns out to be anything but round, and Paris, London and Tokyo run in every direction at once.

## How it works

1. **Download** the metro routes of each city from OpenStreetMap (Overpass API), cached locally.
2. **Filter** to the city's actual metro lines (see [What counts as a metro line](#what-counts-as-a-metro-line)).
3. **Cut** every line into 100 m pieces (in a metric UTM projection).
4. **Bearing** of each piece = its compass direction. A track running north–south counts for both N and S (track has no front or back), so the rose is symmetric, like Boeing's.
5. **Add up** track length per 10° direction. Bar *area* is proportional to the share of track running that way; bars are stacked in each line's colour.
6. **Orientation order** (Boeing's measure): 0 = no preferred direction, 1 = perfect grid.

Each city image also has a small map of the network and a legend with line names.

## Usage

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python orientation_roses.py                      # all cities + overview grid
python orientation_roses.py nyc glasgow          # only some cities
python inspect_lines.py tokyo                    # list every route in the data, and whether it's kept
```

Outputs: `<city>_orientation.png` (1080 × 1350, Instagram 4:5) per city, plus `all_orientation.png` / `.svg` (grid of the cities you ran, sorted by orientation order).

Downloads are cached in `cache/`. Overpass is sometimes slow or overloaded (502/504 errors): the script tries three servers and you can simply run it again later.

## Files

| File | What it does |
|---|---|
| `radial_roses.py` | **Shared module**: city list (`CITIES`), download & cache, line filters, line names. The other scripts import it, so keep them in the same folder. (It's named after an earlier experiment and can also be run on its own, see below.) |
| `orientation_roses.py` | The compass roses (the posted maps) |
| `inspect_lines.py` | Writes `lines_check.csv` listing every OSM route per city — use it to check and fix the line filters |
| `experiments/radial_lines_map.py` | An earlier idea: colour each piece of track by whether it runs *towards* the city centre or *around* it |

Running `python radial_roses.py` draws the "radial roses" experiment: wedges by direction from the centre, with stripes showing whether track runs to/from the centre or around it.

## What counts as a metro line

Each city entry in `CITIES` has a `lines` list of the official metro lines (and readable names for the legend). Everything else is dropped. Notable choices:

- **Tokyo:** the 13 Tokyo Metro and Toei lines. Through-services onto private railways and JR (incl. the Yamanote line) are not included.
- **London:** the 11 Underground lines. No Elizabeth line, Overground or DLR.
- **Paris:** Métro 1–14, 3bis and 7bis. No RER, airport shuttles or Grand Paris Express.
- **Beijing:** Batong and Daxing sections counted as part of lines 1 and 4.
- **New York:** subway services; shared trunk track counts once per service.

This is the narrow "what the city brands as its metro" definition. It's somewhat arbitrary, but it's one rule applied the same way everywhere. To add a city, copy an entry in `CITIES`, run `inspect_lines.py <city>` and adjust its `lines`.

## Settings

At the top of `orientation_roses.py`: `THEME` (`"light"` or `"dark"`) and the colours in `THEMES`, `STACK_BY_LINE` (line colours or one colour), `SORT_GRID`, grid spacing (`GRID_GAP`, `TITLE_DROP`) and the size of the network inset (`INSET_TRIM`, `INSET_LINE_WIDTH`).

## Font

Uses [Lato](https://fonts.google.com/specimen/Lato) (SIL Open Font License) if installed, or from a `fonts/` folder next to the scripts.

## Limitations

- Colours and line membership come from OpenStreetMap tags. Most match the official colours, but not all were checked.
- Orientation is of track length, not of service frequency or ridership.
- Ring lines and curvy networks naturally score low on orientation order; small networks (Glasgow) give spikier roses because each kilometre is a bigger share.

## Credits

- Data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL)
- Method after Geoff Boeing, *Urban spatial order: street network orientation, configuration, and entropy* (Applied Network Science, 2019)
- Built with GeoPandas, Shapely, pyproj and Matplotlib
- Code written with help from Claude (Anthropic)

Made by Martin Bangratz · [martincreates.com](https://martincreates.com)

## License

Code: MIT (see [LICENSE](LICENSE)). Map data: ODbL, © OpenStreetMap contributors.
