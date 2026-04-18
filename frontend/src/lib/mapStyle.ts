import type { StyleSpecification } from "maplibre-gl";

/**
 * Dark base style using free OpenStreetMap raster tiles.
 *
 * Production swap: replace with Amazon Location Service (Esri Street) style URL
 * once the ALS map resource is provisioned. The source/layer IDs for the river
 * overlay and town markers stay the same, so useMapLayers keeps working.
 */
export const baseStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "basemap",
      type: "raster",
      source: "osm",
      paint: { "raster-brightness-max": 0.55, "raster-saturation": -0.4 },
    },
  ],
};

export const REGION_CENTER: Record<string, [number, number, number]> = {
  // [lon, lat, zoom] — framed so the full Mississippi basin (main stem +
  // Ohio/Missouri/Arkansas/Yazoo/Red tributaries) fits in view.
  mississippi: [-90.5, 33.8, 5.1],
  ohio: [-84.0, 39.5, 6.0],
  colorado: [-111.0, 39.5, 5.6],
};
