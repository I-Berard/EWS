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

export interface Acquisition {
  id: string
  index: number
  date: string
}

export interface AcquisitionSchedule {
  aoi_id: string
  cycle_days: number
  acquisitions: Acquisition[]
}

export interface RealTimelineItem {
  id: string
  date: string
  thumbnail_url: string
  image_bbox: [number, number, number, number]
}

export type ImageKind = 'sar' | 'velocity' | 'movement'

export interface MovementPeriod {
  start: string
  end: string
  days: number
}

export interface MovementStats {
  max_movement_mm: number
  max_movement_magnitude_mm: number
  peak_velocity_mm_yr: number
  peak_location: { lat: number; lng: number }
  n_areas: number
  total_area_m2: number
}

export interface MovementAreaProperties {
  id: string
  aoi_id: string
  event_type: 'subsidence' | 'uplift' | string
  period_start: string
  period_end: string
  n_acquisitions: number
  area_m2: number
  mean_movement_mm: number
  peak_movement_mm: number
  mean_velocity_mm_yr: number
  coherence: number
  confidence: number
  pixel_count: number
  rank: number
  detected_at: string
}

export interface MovementAreaFeature {
  type: 'Feature'
  properties: MovementAreaProperties
  geometry: Polygon
}

export interface MovementAnalysis {
  aoi_id: string
  unit: string
  period: MovementPeriod
  n_acquisitions: number
  acquisitions: Acquisition[]
  threshold_mm: number
  stats: MovementStats
  areas: { type: 'FeatureCollection'; features: MovementAreaFeature[] }
}

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

/** Sentinel-1 visit schedule (12-day revisit) that makes up the demo stack. */
export function getAcquisitions(aoiId: string): Promise<AcquisitionSchedule> {
  return getJson(`${BASE}/aois/${aoiId}/acquisitions`)
}

/** Stacked movement analysis for every Sentinel-1 visit inside [start, end]. */
export function getMovement(aoiId: string, start: string, end: string): Promise<MovementAnalysis> {
  return getJson(
    `${BASE}/aois/${aoiId}/movement?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
  )
}

/** URL of the movement heatmap PNG for a period (map overlay / thumbnail). */
export function movementImageUrl(aoiId: string, start: string, end: string): string {
  return `${BASE}/aois/${aoiId}/images/movement?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
}

/** URL of a single Sentinel-1 visit's backscatter image (stack member). */
export function visitImageUrl(aoiId: string, index: number): string {
  return `${BASE}/aois/${aoiId}/images/visit/${index}`
}

/** Fetch real Sentinel-1 GRD quicklooks timeline. */
export function getRealTimeline(aoiId: string, bbox?: [number, number, number, number]): Promise<RealTimelineItem[]> {
  let url = `${BASE}/aois/${aoiId}/real-timeline`
  if (bbox) {
    url += `?min_lng=${bbox[0]}&min_lat=${bbox[1]}&max_lng=${bbox[2]}&max_lat=${bbox[3]}`
  }
  return getJson(url)
}
