"""Generate a synthetic but plausible Mississippi basin river graph GeoJSON.

No external APIs, no shapefiles — pure Python. Produces a FeatureCollection
with ~400-600 LineString segments spanning the Mississippi main stem plus the
Missouri, Ohio, Arkansas, and Tennessee tributaries. Hydraulic properties
follow the Manning/continuity relationship with realistic per-river regimes
and +/-10% random noise; towns are attached to the nearest segment.

This is the hackathon-demo replacement for ``build_river_graph.py``, which
requires NHD shapefiles and the rate-limited USGS StreamStats API.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

random.seed(42)  # deterministic output

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "mississippi.geojson"

# ---------------------------------------------------------------------------
# River waypoint skeletons. Each river is an ordered list of (lon, lat)
# waypoints that loosely trace the real channel. We densify these into
# per-segment LineStrings with 3-5 points each.
# ---------------------------------------------------------------------------

# Mississippi main stem: Minneapolis -> Gulf of Mexico
MISSISSIPPI_WAYPOINTS: list[tuple[float, float]] = [
    (-93.265, 44.977),   # Minneapolis, MN
    (-92.466, 44.023),   # Red Wing
    (-91.639, 43.775),   # La Crosse, WI
    (-91.160, 43.335),   # Prairie du Chien
    (-90.670, 42.500),   # Dubuque, IA
    (-90.567, 41.524),   # Davenport
    (-91.372, 40.396),   # Keokuk
    (-90.583, 39.721),   # Hannibal
    (-90.199, 38.627),   # St Louis, MO
    (-89.526, 37.306),   # Chester
    (-89.518, 37.005),   # Cape Girardeau, MO
    (-89.176, 37.005),   # Cairo, IL
    (-89.667, 36.500),   # New Madrid
    (-89.971, 35.650),   # Osceola
    (-90.049, 35.149),   # Memphis, TN
    (-90.648, 34.250),   # Helena
    (-90.879, 33.546),   # Greenville
    (-91.050, 32.800),   # Arkansas City area (confluence zone)
    (-91.384, 31.559),   # Natchez, MS
    (-91.234, 30.450),   # Baton Rouge, LA
    (-90.715, 30.050),   # Donaldsonville
    (-90.071, 29.951),   # New Orleans, LA
    (-89.250, 29.150),   # Mouth (Head of Passes)
]

# Missouri River: headwaters (Three Forks MT) -> St Louis confluence
MISSOURI_WAYPOINTS: list[tuple[float, float]] = [
    (-111.500, 45.900),  # Three Forks, MT
    (-108.500, 46.600),  # Fort Benton area
    (-104.050, 47.998),  # Williston, ND
    (-100.783, 46.808),  # Bismarck, ND
    (-98.867, 45.467),   # Mobridge, SD
    (-96.730, 43.550),   # Sioux Falls area
    (-96.400, 42.500),   # Sioux City, IA
    (-95.940, 41.260),   # Omaha, NE
    (-95.677, 39.566),   # St Joseph, MO
    (-94.578, 39.100),   # Kansas City, MO
    (-92.335, 38.952),   # Jefferson City
    (-90.670, 38.800),   # Chesterfield
    (-90.199, 38.627),   # merges into Mississippi at St Louis
]

# Ohio River: Pittsburgh -> Cairo confluence
OHIO_WAYPOINTS: list[tuple[float, float]] = [
    (-80.000, 40.440),   # Pittsburgh, PA
    (-80.600, 40.620),   # Beaver
    (-80.857, 40.370),   # Wheeling area
    (-81.720, 39.300),   # Marietta
    (-82.500, 38.700),   # Huntington
    (-84.510, 39.103),   # Cincinnati, OH
    (-85.759, 38.253),   # Louisville, KY
    (-86.750, 37.900),   # Owensboro
    (-87.571, 37.975),   # Evansville, IN
    (-88.600, 37.150),   # Paducah
    (-89.176, 37.005),   # merges into Mississippi at Cairo
]

# Arkansas River: headwaters (CO) -> Mississippi confluence (Arkansas City, AR)
ARKANSAS_WAYPOINTS: list[tuple[float, float]] = [
    (-106.300, 39.100),  # Leadville, CO headwaters
    (-104.800, 38.270),  # Pueblo, CO
    (-100.900, 38.000),  # Garden City, KS
    (-97.338, 37.687),   # Wichita, KS
    (-95.960, 36.155),   # Tulsa, OK
    (-94.717, 35.383),   # Fort Smith, AR
    (-92.289, 34.746),   # Little Rock, AR
    (-91.360, 34.300),   # Pine Bluff
    (-91.050, 32.800),   # merges into Mississippi (Arkansas City area)
]

# Tennessee River: Knoxville -> Ohio confluence (Paducah)
TENNESSEE_WAYPOINTS: list[tuple[float, float]] = [
    (-83.920, 35.960),   # Knoxville, TN
    (-85.309, 35.045),   # Chattanooga, TN
    (-86.581, 34.730),   # Huntsville, AL
    (-87.677, 34.744),   # Florence, AL
    (-88.050, 35.100),   # Pickwick
    (-88.330, 35.650),   # Savannah
    (-87.850, 36.500),   # Kentucky Lake area
    (-88.600, 37.150),   # merges into Ohio at Paducah
]


# ---------------------------------------------------------------------------
# River regime table: baseline hydraulics per "zone". Each zone has a base
# (velocity, width, depth); we apply +/-10% noise per segment.
# ---------------------------------------------------------------------------

def miss_zone(idx: int, total: int) -> tuple[float, float, float, str]:
    """Return (v, w, d, huc8_prefix) for a Mississippi segment at position idx."""
    frac = idx / max(total - 1, 1)
    if frac < 0.33:
        return 0.5, 200.0, 3.0, "0701000"   # upper
    if frac < 0.66:
        return 0.8, 400.0, 5.0, "0709000"   # middle
    return 1.0, 600.0, 8.0, "0801010"       # lower


def tributary_zone(river: str) -> tuple[float, float, float, str]:
    return {
        "missouri":  (0.7, 250.0, 4.0, "1030010"),
        "ohio":      (0.6, 300.0, 6.0, "0509010"),
        "arkansas":  (0.4, 150.0, 3.0, "1102000"),
        "tennessee": (0.55, 220.0, 5.0, "0602000"),
    }[river]


# ---------------------------------------------------------------------------
# Town table. (name, lat, lon, population, fips). Towns get attached to the
# nearest segment by midpoint great-circle distance.
# ---------------------------------------------------------------------------

TOWNS: list[dict[str, Any]] = [
    {"name": "Minneapolis",    "lat": 44.977, "lon": -93.265, "population": 429000, "fips": "2743000"},
    {"name": "Dubuque",        "lat": 42.500, "lon": -90.670, "population": 59000,  "fips": "1922375"},
    {"name": "St Louis",       "lat": 38.627, "lon": -90.199, "population": 301000, "fips": "2965000"},
    {"name": "Cape Girardeau", "lat": 37.305, "lon": -89.518, "population": 40000,  "fips": "2910468"},
    {"name": "Cairo",          "lat": 37.005, "lon": -89.176, "population": 2000,   "fips": "1710032"},
    {"name": "Memphis",        "lat": 35.149, "lon": -90.049, "population": 633000, "fips": "4748000"},
    {"name": "Vicksburg",      "lat": 32.353, "lon": -90.878, "population": 22000,  "fips": "2876528"},
    {"name": "Natchez",        "lat": 31.559, "lon": -91.384, "population": 15000,  "fips": "2850440"},
    {"name": "Baton Rouge",    "lat": 30.450, "lon": -91.234, "population": 227000, "fips": "2205000"},
    {"name": "New Orleans",    "lat": 29.951, "lon": -90.071, "population": 383000, "fips": "2255000"},
    {"name": "Sioux City",     "lat": 42.500, "lon": -96.400, "population": 85000,  "fips": "1973335"},
    {"name": "Omaha",          "lat": 41.260, "lon": -95.940, "population": 486000, "fips": "3137000"},
    {"name": "Kansas City",    "lat": 39.100, "lon": -94.578, "population": 508000, "fips": "2938000"},
    {"name": "Pittsburgh",     "lat": 40.440, "lon": -80.000, "population": 302000, "fips": "4261000"},
    {"name": "Cincinnati",     "lat": 39.103, "lon": -84.510, "population": 309000, "fips": "3915000"},
    {"name": "Louisville",     "lat": 38.253, "lon": -85.759, "population": 633000, "fips": "2148000"},
    {"name": "Evansville",     "lat": 37.975, "lon": -87.571, "population": 118000, "fips": "1822000"},
    {"name": "Little Rock",    "lat": 34.746, "lon": -92.289, "population": 202000, "fips": "0541000"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between (lon, lat) points."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def densify_waypoints(
    waypoints: list[tuple[float, float]],
    n_segments: int,
) -> list[list[tuple[float, float]]]:
    """Linearly interpolate waypoints into ``n_segments`` LineStrings of 3-5 pts.

    We compute cumulative distance along the polyline, then carve that into
    equal-distance chunks. Each chunk is resampled into 4 intermediate points.
    """
    # Cumulative distance along waypoints.
    cum = [0.0]
    for i in range(1, len(waypoints)):
        cum.append(cum[-1] + haversine_km(waypoints[i - 1], waypoints[i]))
    total = cum[-1]

    def point_at(dist: float) -> tuple[float, float]:
        # Find surrounding waypoints.
        if dist <= 0:
            return waypoints[0]
        if dist >= total:
            return waypoints[-1]
        for i in range(1, len(cum)):
            if cum[i] >= dist:
                t = (dist - cum[i - 1]) / (cum[i] - cum[i - 1])
                lon = waypoints[i - 1][0] + t * (waypoints[i][0] - waypoints[i - 1][0])
                lat = waypoints[i - 1][1] + t * (waypoints[i][1] - waypoints[i - 1][1])
                return (lon, lat)
        return waypoints[-1]

    step = total / n_segments
    segments: list[list[tuple[float, float]]] = []
    pts_per_seg = 4
    for i in range(n_segments):
        seg_start = i * step
        seg_end = (i + 1) * step
        pts = [point_at(seg_start + (j / (pts_per_seg - 1)) * (seg_end - seg_start))
               for j in range(pts_per_seg)]
        segments.append(pts)
    return segments


def noisy(value: float, pct: float = 0.10) -> float:
    return value * (1.0 + random.uniform(-pct, pct))


def segment_midpoint(coords: list[tuple[float, float]]) -> tuple[float, float]:
    return coords[len(coords) // 2]


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build() -> dict[str, Any]:
    # Segment counts per river — tuned to total ~500.
    counts = {
        "mississippi": 180,
        "missouri":    110,
        "ohio":         90,
        "arkansas":     70,
        "tennessee":    60,
    }

    rivers_geom: dict[str, list[list[tuple[float, float]]]] = {
        "mississippi": densify_waypoints(MISSISSIPPI_WAYPOINTS, counts["mississippi"]),
        "missouri":    densify_waypoints(MISSOURI_WAYPOINTS,    counts["missouri"]),
        "ohio":        densify_waypoints(OHIO_WAYPOINTS,        counts["ohio"]),
        "arkansas":    densify_waypoints(ARKANSAS_WAYPOINTS,    counts["arkansas"]),
        "tennessee":   densify_waypoints(TENNESSEE_WAYPOINTS,   counts["tennessee"]),
    }

    # Assign segment IDs.
    prefixes = {
        "mississippi": "MS",
        "missouri":    "MO",
        "ohio":        "OH",
        "arkansas":    "AR",
        "tennessee":   "TN",
    }
    river_segments: dict[str, list[dict[str, Any]]] = {}
    for river, segs in rivers_geom.items():
        river_segments[river] = []
        for i, coords in enumerate(segs):
            river_segments[river].append({
                "segment_id": f"{prefixes[river]}_{i + 1:04d}",
                "coords": coords,
                "river": river,
                "idx": i,
                "of": len(segs),
            })

    # Assign hydraulics.
    for river, segs in river_segments.items():
        for s in segs:
            if river == "mississippi":
                v, w, d, huc_prefix = miss_zone(s["idx"], s["of"])
            else:
                v, w, d, huc_prefix = tributary_zone(river)
            # HUC8 varies slightly within river by position.
            huc_tail = (s["idx"] % 10) + 1
            s["huc8"] = f"{huc_prefix}{huc_tail}"
            s["flow_velocity"] = round(noisy(v), 3)
            s["channel_width"] = round(noisy(w), 2)
            s["mean_depth"] = round(noisy(d), 2)
            s["flow_rate"] = round(s["flow_velocity"] * s["channel_width"] * s["mean_depth"], 2)

    # Downstream connectivity — sequential within each river, with tributary
    # confluences patched into the Mississippi at the nearest segment by
    # midpoint proximity.
    def nearest_ms_idx(point: tuple[float, float]) -> int:
        ms = river_segments["mississippi"]
        dists = [haversine_km(segment_midpoint(s["coords"]), point) for s in ms]
        return dists.index(min(dists))

    # Confluence anchor points (lon, lat) — where tributary meets main stem.
    confluences: dict[str, tuple[float, float]] = {
        "missouri":  (-90.199, 38.627),   # St Louis
        "ohio":      (-89.176, 37.005),   # Cairo
        "arkansas":  (-91.050, 32.800),   # Arkansas City area
        "tennessee": (-88.600, 37.150),   # Paducah (into Ohio, not Mississippi)
    }

    # Sequential downstream for each river.
    for river, segs in river_segments.items():
        for i, s in enumerate(segs):
            if i < len(segs) - 1:
                s["downstream_ids"] = [segs[i + 1]["segment_id"]]
            else:
                s["downstream_ids"] = []

    # Tributary terminal segments -> attach to confluence on target river.
    # Missouri, Ohio, Arkansas -> Mississippi. Tennessee -> Ohio.
    for trib, target_point in confluences.items():
        terminal = river_segments[trib][-1]
        if trib == "tennessee":
            # Find nearest Ohio segment.
            ohio = river_segments["ohio"]
            dists = [haversine_km(segment_midpoint(s["coords"]), target_point) for s in ohio]
            target = ohio[dists.index(min(dists))]
        else:
            target = river_segments["mississippi"][nearest_ms_idx(target_point)]
        terminal["downstream_ids"] = [target["segment_id"]]

    # Attach towns to nearest segment by midpoint distance across all rivers.
    all_segs: list[dict[str, Any]] = [s for segs in river_segments.values() for s in segs]
    for seg in all_segs:
        seg["town"] = None

    for town in TOWNS:
        pt = (town["lon"], town["lat"])
        best = min(all_segs, key=lambda s: haversine_km(segment_midpoint(s["coords"]), pt))
        # Only claim it if closest seg doesn't already have a town (avoid stomping).
        if best["town"] is None:
            best["town"] = {
                "name": town["name"],
                "population": town["population"],
                "fips": town["fips"],
            }
        else:
            # Next-best free segment within 50km.
            ranked = sorted(all_segs, key=lambda s: haversine_km(segment_midpoint(s["coords"]), pt))
            for cand in ranked[1:]:
                if cand["town"] is None:
                    cand["town"] = {
                        "name": town["name"],
                        "population": town["population"],
                        "fips": town["fips"],
                    }
                    break

    # Emit features.
    features: list[dict[str, Any]] = []
    for seg in all_segs:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(lon, 6), round(lat, 6)] for lon, lat in seg["coords"]],
            },
            "properties": {
                "segment_id": seg["segment_id"],
                "flow_velocity": seg["flow_velocity"],
                "channel_width": seg["channel_width"],
                "mean_depth": seg["mean_depth"],
                "flow_rate": seg["flow_rate"],
                "downstream_ids": seg["downstream_ids"],
                "huc8": seg["huc8"],
                "town": seg["town"],
            },
        })

    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    fc = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(fc))
    n = len(fc["features"])
    towns = sum(1 for f in fc["features"] if f["properties"]["town"] is not None)
    terminals = sum(1 for f in fc["features"] if not f["properties"]["downstream_ids"])
    print(f"Wrote {n} segments to {OUTPUT_PATH}")
    print(f"  towns attached: {towns}")
    print(f"  terminal segments (downstream_ids=[]): {terminals}")


if __name__ == "__main__":
    main()
