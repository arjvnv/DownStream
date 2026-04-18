import type { StyleSpecification } from "maplibre-gl";

export type Region = "mississippi" | "ohio" | "colorado";

export const REGION_CENTER: Record<Region, [number, number, number]> = {
  mississippi: [-90.1994, 35.1495, 5],
  ohio: [-82.9988, 39.9612, 6],
  colorado: [-105.7821, 39.5501, 6],
};

export const baseStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#0a0e14" },
    },
  ],
};
