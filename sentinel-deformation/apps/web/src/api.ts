/**
 * Typed API client for the Sentinel Deformation Monitor backend.
 *
 * All requests go through the vite dev proxy (/api -> http://localhost:8000),
 * so no CORS handling is needed in development.
 */

const BASE = '/api/demo'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LonLat = [number, number]

export interface Polygon {
  type: 'Polygon'
  coordinates: LonLat[][]
}

export interface Aoi {
  id: string
  name: string
  description?: string
  geometry: Polygon
}

export interface ProductMeta {
  id: string
  aoi_id: string
  satellite: string
  product_type: string
  bands: string[]
  width: number
  height: number
  bbox: [number, number, number, number] // [west, south, east, north]
  acquisition: { start: string; end: string }
  generated_at: string
}

export interface AnomalyProperties {
  id: string
  aoi_id: string
  event_type: 'subsidence' | 'uplift' | string
  area_m2: number
  mean_velocity: number
  max_velocity: number
  coherence: number
  confidence: number
  pixel_count: number
  rank: number
  detected_at: string
}

export interface AnomalyFeature {
  type: 'Feature'
  properties: AnomalyProperties
  geometry: Polygon
}

export interface AnomalyCollection {
  type: 'FeatureCollection'
  features: AnomalyFeature[]
}

export interface AnomalySummary {
  aoi_id: string
  n_anomalies: number
  max_subsidence_mm_yr: number | null
  max_uplift_mm_yr: number | null
  total_area_m2: number
  top_features: AnomalyProperties[]
}

export interface TimeSeriesPoint {
  date: string
  displacement_mm: number
}

export interface TimeSeries {
  aoi_id: string
  location: { lat: number; lng: number }
  unit: string
  velocity_mm_per_yr: number
  points: TimeSeriesPoint[]
}

export type ImageKind = 'sar' | 'velocity'

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`GET ${url} failed: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export function listAois(): Promise<Aoi[]> {
  return getJson(`${BASE}/aois`)
}

export function getAoi(aoiId: string): Promise<Aoi> {
  return getJson(`${BASE}/aois/${aoiId}`)
}

export function getProductMeta(aoiId: string): Promise<ProductMeta> {
  return getJson(`${BASE}/aois/${aoiId}/product`)
}

export function getAnomalies(aoiId: string): Promise<AnomalyCollection> {
  return getJson(`${BASE}/aois/${aoiId}/anomalies`)
}

export function getSummary(aoiId: string): Promise<AnomalySummary> {
  return getJson(`${BASE}/aois/${aoiId}/summary`)
}

export function getTimeSeries(aoiId: string, lat: number, lng: number): Promise<TimeSeries> {
  return getJson(`${BASE}/aois/${aoiId}/timeseries?lat=${lat}&lng=${lng}`)
}

/** URL for a server-rendered PNG overlay image (use directly in <img>/map layers). */
export function imageUrl(aoiId: string, kind: ImageKind): string {
  return `${BASE}/aois/${aoiId}/images/${kind}`
}
