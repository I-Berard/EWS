/**
 * Tests for the Map component's configuration logic with maplibre-gl mocked.
 * Focuses on the pieces the component computes itself: layer paint
 * expressions (rank-1 emphasis, velocity interpolation), overlay
 * registration order, and visibility toggling.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'

// --- Mock maplibre-gl before importing the component ------------------------

type LayerSpec = { id: string; type: string; paint?: any; layout?: any; minzoom?: number }
type SourceSpec = { type: string; data?: any; url?: string; coordinates?: any }

const addedSources = new Map<string, SourceSpec>()
const addedLayers: LayerSpec[] = []
const layerVisibility = new Map<string, string>()

// Minimal event system so tests can fire the 'load' lifecycle event
const handlers = new Map<string, Set<() => void>>()
const emit = (event: string) => {
  handlers.get(event)?.forEach((cb) => cb())
}

const mapInstance = {
  addControl: vi.fn(),
  on: vi.fn((event: string, cb: () => void) => {
    if (!handlers.has(event)) handlers.set(event, new Set())
    handlers.get(event)!.add(cb)
  }),
  once: vi.fn((event: string, cb: () => void) => {
    if (!handlers.has(event)) handlers.set(event, new Set())
    const wrapper = () => {
      cb()
      handlers.get(event)?.delete(wrapper)
    }
    handlers.get(event)!.add(wrapper)
  }),
  getCanvas: () => ({ style: {} }),
  addSource: vi.fn((id: string, spec: SourceSpec) => {
    addedSources.set(id, spec)
    if (spec.type === 'geojson') {
      (spec as any).setData = vi.fn()
    }
    if (spec.type === 'image') {
      // Real maplibre ImageSources support swapping url/coordinates in place
      ;(spec as any).updateImage = vi.fn()
    }
  }),
  getSource: vi.fn((id: string) => addedSources.get(id)),
  addLayer: vi.fn((spec: LayerSpec, _before?: string) => {
    addedLayers.push(spec)
    layerVisibility.set(spec.id, 'visible')
  }),
  getLayer: vi.fn((id: string) => addedLayers.find((l) => l.id === id)),
  setLayoutProperty: vi.fn((id: string, _prop: string, value: string) => {
    layerVisibility.set(id, value)
  }),
  setFilter: vi.fn(),
  setPaintProperty: vi.fn(),
  fitBounds: vi.fn(),
  triggerRepaint: vi.fn(),
}

// Fire 'load' shortly after construction, like the real map does
queueMicrotask(() => emit('load'))

vi.mock('maplibre-gl', () => {
  class FakeMap {
    constructor(_opts: unknown) {
      queueMicrotask(() => emit('load'))
      return mapInstance as unknown as FakeMap
    }
  }
  return {
    Map: FakeMap,
    NavigationControl: vi.fn(),
  }
})

// jsdom lacks canvas support - stub it so maplibre can "initialize"
beforeEach(() => {
  addedSources.clear()
  addedLayers.length = 0
  layerVisibility.clear()
  handlers.clear() // no stale once('load') callbacks from previous tests
  vi.clearAllMocks()
  HTMLDivElement.prototype.getBoundingClientRect = () =>
    ({ width: 800, height: 600, x: 0, y: 0, top: 0, left: 0, right: 800, bottom: 600, toJSON: () => ({}) }) as DOMRect
})

// Helpers to drive the mocked lifecycle
const flushEffects = async () => {
  const { act } = await import('@testing-library/react')
  await act(async () => { /* let effects run */ })
}

import { render } from '@testing-library/react'
import MapComponent from './Map'
import type { AnomalyCollection, MovementAnalysis, ProductMeta } from '../api'

const makeAnomalies = (): AnomalyCollection => ({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        id: 'a-1', aoi_id: 'x', event_type: 'subsidence', area_m2: 1000,
        mean_velocity: -22.0, max_velocity: -25.0, coherence: 0.9,
        confidence: 0.9, pixel_count: 100, rank: 1, detected_at: '2026-01-01',
      },
      geometry: { type: 'Polygon', coordinates: [[[30.0, -2.0], [30.1, -2.0], [30.1, -1.9], [30.0, -1.9], [30.0, -2.0]]] },
    },
    {
      type: 'Feature',
      properties: {
        id: 'a-2', aoi_id: 'x', event_type: 'subsidence', area_m2: 500,
        mean_velocity: -8.0, max_velocity: -9.0, coherence: 0.8,
        confidence: 0.7, pixel_count: 50, rank: 2, detected_at: '2026-01-01',
      },
      geometry: { type: 'Polygon', coordinates: [[[30.2, -2.0], [30.3, -2.0], [30.3, -1.9], [30.2, -1.9], [30.2, -2.0]]] },
    },
  ],
})

const makeProduct = (): ProductMeta => ({
  id: 'p1', aoi_id: 'x', satellite: 'S1', product_type: 'SLC', bands: [],
  width: 300, height: 300,
  bbox: [29.9, -2.0, 30.2, -1.8],
  acquisition: { start: '2025-09-01', end: '2026-09-01' },
  generated_at: '2026-09-28T00:00:00Z',
})

const makeMovement = (): MovementAnalysis => ({
  aoi_id: 'x',
  unit: 'mm (LOS)',
  period: { start: '2026-01-01', end: '2026-06-01', days: 151 },
  n_acquisitions: 13,
  acquisitions: [{ id: 'x-S1-001', index: 0, date: '2025-08-04' }],
  threshold_mm: 5.0,
  stats: {
    max_movement_mm: -18.4,
    max_movement_magnitude_mm: 18.4,
    peak_velocity_mm_yr: -14.2,
    peak_location: { lat: -1.9, lng: 30.05 },
    n_areas: 2,
    total_area_m2: 500000,
  },
  areas: {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: {
          id: 'm-1', aoi_id: 'x', event_type: 'subsidence',
          period_start: '2026-01-01', period_end: '2026-06-01', n_acquisitions: 13,
          area_m2: 300000, mean_movement_mm: -12.0, peak_movement_mm: -18.4,
          mean_velocity_mm_yr: -9.5, coherence: 0.8, confidence: 0.7,
          pixel_count: 90, rank: 1, detected_at: '2026-01-01',
        },
        geometry: { type: 'Polygon', coordinates: [[[30.0, -2.0], [30.1, -2.0], [30.1, -1.9], [30.0, -1.9], [30.0, -2.0]]] },
      },
      {
        type: 'Feature',
        properties: {
          id: 'm-2', aoi_id: 'x', event_type: 'uplift',
          period_start: '2026-01-01', period_end: '2026-06-01', n_acquisitions: 13,
          area_m2: 200000, mean_movement_mm: 6.2, peak_movement_mm: 7.9,
          mean_velocity_mm_yr: 4.9, coherence: 0.75, confidence: 0.65,
          pixel_count: 60, rank: 2, detected_at: '2026-01-01',
        },
        geometry: { type: 'Polygon', coordinates: [[[30.2, -2.0], [30.3, -2.0], [30.3, -1.9], [30.2, -1.9], [30.2, -2.0]]] },
      },
    ],
  },
})

describe('Map component', () => {
  it('adds AOI source + outline layer when aoi provided', async () => {
    render(
      <MapComponent
        aoi={{ id: 'x', geometry: { type: 'Polygon', coordinates: [[[29.9, -2], [30.2, -2], [30.2, -1.8], [29.9, -1.8], [29.9, -2]]] } }}
        anomalies={makeAnomalies()}
        product={makeProduct()}
        visibleImages={{ sar: false, velocity: true, movement: false }}
      />,
    )
    await flushEffects()

    expect(addedSources.has('aoi')).toBe(true)
    expect(addedLayers.some((l) => l.id === 'aoi-outline')).toBe(true)
  })

  it('registers anomaly fill with rank-1 emphasis and velocity ramp', async () => {
    render(
      <MapComponent anomalies={makeAnomalies()} visibleImages={{ sar: false, velocity: false, movement: false }} />,
    )
    await flushEffects()

    const fill = addedLayers.find((l) => l.id === 'anomalies-fill')
    expect(fill).toBeDefined()
    const color = JSON.stringify(fill!.paint!['fill-color'])
    // rank 1 -> #ff2222 and uplift -> #4dc3ff branches exist
    expect(color).toContain('#ff2222')
    expect(color).toContain('#4dc3ff')
    // velocity interpolation ramp present
    expect(color).toContain('interpolate')
    expect(color).toContain('#820000')
  })

  it('registers both raster overlay sources with AOI bbox coordinates', async () => {
    render(
      <MapComponent product={makeProduct()} visibleImages={{ sar: true, velocity: true, movement: false }} />,
    )
    await flushEffects()

    const sar = addedSources.get('img-sar')
    const vel = addedSources.get('img-velocity')
    expect(sar?.type).toBe('image')
    expect(sar?.url).toContain('/images/sar')
    expect(vel?.type).toBe('image')
    expect(vel?.url).toContain('/images/velocity')
    // bbox corners NW / NE / SE / SW
    expect(sar?.coordinates).toEqual([
      [29.9, -1.8], [30.2, -1.8], [30.2, -2.0], [29.9, -2.0],
    ])
    expect(addedLayers.some((l) => l.id === 'overlay-sar')).toBe(true)
    expect(addedLayers.some((l) => l.id === 'overlay-velocity')).toBe(true)
  })

  it('hides overlay layers that are toggled off', async () => {
    render(
      <MapComponent product={makeProduct()} visibleImages={{ sar: false, velocity: true, movement: false }} />,
    )
    await flushEffects()

    expect(layerVisibility.get('overlay-sar')).toBe('none')
    expect(layerVisibility.get('overlay-velocity')).toBe('visible')
  })

  it('registers the movement heatmap overlay for the selected period', async () => {
    render(
      <MapComponent
        product={makeProduct()}
        movementUrl="/api/demo/aois/x/images/movement?start=2026-01-01&end=2026-06-01"
        visibleImages={{ sar: false, velocity: false, movement: true }}
      />,
    )
    await flushEffects()

    const src = addedSources.get('img-movement')
    expect(src?.type).toBe('image')
    expect(src?.url).toContain('images/movement?start=2026-01-01')
    expect(src?.coordinates).toEqual([
      [29.9, -1.8], [30.2, -1.8], [30.2, -2.0], [29.9, -2.0],
    ])
    expect(addedLayers.some((l) => l.id === 'overlay-movement')).toBe(true)
    expect(layerVisibility.get('overlay-movement')).toBe('visible')
  })

  it('hides the movement overlay when the layer is toggled off', async () => {
    render(
      <MapComponent
        product={makeProduct()}
        movementUrl="/api/demo/aois/x/images/movement?start=2026-01-01&end=2026-06-01"
        visibleImages={{ sar: false, velocity: false, movement: false }}
      />,
    )
    await flushEffects()

    expect(layerVisibility.get('overlay-movement')).toBe('none')
  })

  it('swaps the movement image in place when the period changes', async () => {
    const first = '/api/demo/aois/x/images/movement?start=2026-01-01&end=2026-06-01'
    const second = '/api/demo/aois/x/images/movement?start=2025-10-01&end=2025-12-01'
    const { rerender } = render(
      <MapComponent
        product={makeProduct()}
        movementUrl={first}
        visibleImages={{ sar: false, velocity: false, movement: true }}
      />,
    )
    await flushEffects()

    rerender(
      <MapComponent
        product={makeProduct()}
        movementUrl={second}
        visibleImages={{ sar: false, velocity: false, movement: true }}
      />,
    )
    await flushEffects()

    // No source re-add: the existing ImageSource is updated in place
    const src = addedSources.get('img-movement') as any
    expect(src.updateImage).toHaveBeenCalledTimes(1)
    expect(src.updateImage).toHaveBeenCalledWith(
      expect.objectContaining({ url: second }),
    )
    // img-sar + img-velocity + img-movement, with img-movement never re-added
    expect(addedSources.size).toBe(3)
  })

  it('renders ranked movement areas with the movement colour ramp', async () => {
    render(
      <MapComponent
        product={makeProduct()}
        movementUrl="/api/demo/aois/x/images/movement?start=2026-01-01&end=2026-06-01"
        movementAreas={makeMovement()}
        visibleImages={{ sar: false, velocity: false, movement: true }}
      />,
    )
    await flushEffects()

    expect(addedSources.get('movement-areas')?.type).toBe('geojson')
    const fill = addedLayers.find((l) => l.id === 'movement-areas-fill')
    expect(fill).toBeDefined()
    const color = JSON.stringify(fill!.paint!['fill-color'])
    expect(color).toContain('interpolate')
    expect(color).toContain('peak_movement_mm')
    expect(color).toContain('#ff2da5') // magenta family, distinct from velocity red
    const outline = addedLayers.find((l) => l.id === 'movement-areas-outline')
    expect(outline).toBeDefined()
    // visible when the movement layer is toggled on
    expect(layerVisibility.get('movement-areas-fill')).toBe('visible')
    expect(layerVisibility.get('movement-areas-outline')).toBe('visible')
  })

  it('hides movement areas when the movement layer is toggled off', async () => {
    render(
      <MapComponent
        product={makeProduct()}
        movementUrl="/api/demo/aois/x/images/movement?start=2026-01-01&end=2026-06-01"
        movementAreas={makeMovement()}
        visibleImages={{ sar: false, velocity: false, movement: false }}
      />,
    )
    await flushEffects()

    expect(layerVisibility.get('movement-areas-fill')).toBe('none')
    expect(layerVisibility.get('movement-areas-outline')).toBe('none')
  })
})
