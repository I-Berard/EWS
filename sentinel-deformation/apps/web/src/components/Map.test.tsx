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
    handlers.get(event)!.add(() => {
      cb()
      handlers.get(event)!.delete(cb)
    })
  }),
  getCanvas: () => ({ style: {} }),
  addSource: vi.fn((id: string, spec: SourceSpec) => {
    addedSources.set(id, spec)
    if (spec.type === 'geojson') {
      (spec as any).setData = vi.fn()
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
import type { AnomalyCollection, ProductMeta } from '../api'

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

describe('Map component', () => {
  it('adds AOI source + outline layer when aoi provided', async () => {
    render(
      <MapComponent
        aoi={{ id: 'x', geometry: { type: 'Polygon', coordinates: [[[29.9, -2], [30.2, -2], [30.2, -1.8], [29.9, -1.8], [29.9, -2]]] } }}
        anomalies={makeAnomalies()}
        product={makeProduct()}
        visibleImages={{ sar: false, velocity: true }}
      />,
    )
    await flushEffects()

    expect(addedSources.has('aoi')).toBe(true)
    expect(addedLayers.some((l) => l.id === 'aoi-outline')).toBe(true)
  })

  it('registers anomaly fill with rank-1 emphasis and velocity ramp', async () => {
    render(
      <MapComponent anomalies={makeAnomalies()} visibleImages={{ sar: false, velocity: false }} />,
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
      <MapComponent product={makeProduct()} visibleImages={{ sar: true, velocity: true }} />,
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
      <MapComponent product={makeProduct()} visibleImages={{ sar: false, velocity: true }} />,
    )
    await flushEffects()

    expect(layerVisibility.get('overlay-sar')).toBe('none')
    expect(layerVisibility.get('overlay-velocity')).toBe('visible')
  })
})
