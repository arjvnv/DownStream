/**
 * Amazon Location Service helpers (geocode + map resource lookup).
 *
 * Stubbed for local dev. Populate VITE_ALS_MAP_NAME and VITE_ALS_API_KEY via
 * Amplify build env to activate. The map component falls back to the free
 * OSM tile source in baseStyle when these are absent.
 */
export const alsMapName = import.meta.env.VITE_ALS_MAP_NAME as string | undefined;
export const alsApiKey = import.meta.env.VITE_ALS_API_KEY as string | undefined;

export function alsStyleUrl(): string | null {
  if (!alsMapName || !alsApiKey) return null;
  return `https://maps.geo.us-east-1.amazonaws.com/maps/v0/maps/${alsMapName}/style-descriptor?key=${alsApiKey}`;
}
