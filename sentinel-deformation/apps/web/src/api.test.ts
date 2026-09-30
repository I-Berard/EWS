import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  imageUrl,
  listAois,
  getAnomalies,
  getTimeSeries,
  getMovement,
  getAcquisitions,
  movementImageUrl,
  visitImageUrl,
} from './api'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('imageUrl', () => {
  it('builds image URLs per kind', () => {
    expect(imageUrl('demo-rwanda-1', 'sar')).toBe('/api/demo/aois/demo-rwanda-1/images/sar')
    expect(imageUrl('demo-rwanda-1', 'velocity')).toBe('/api/demo/aois/demo-rwanda-1/images/velocity')
  })
})

describe('json fetch handling', () => {
  it('throws on non-2xx responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"AOI not found"}', { status: 404 })))
    await expect(listAois()).rejects.toThrow('404')
  })

  it('parses JSON payloads', async () => {
    const payload = { type: 'FeatureCollection', features: [{ properties: { rank: 1 } }] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 })))
    const result = await getAnomalies('demo-rwanda-1')
    expect(result.type).toBe('FeatureCollection')
    expect(result.features[0].properties.rank).toBe(1)
  })
})

describe('getTimeSeries', () => {
  it('encodes lat/lng as query params', async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ points: [] }), { status: 200 }),
    )
    vi.stubGlobal('fetch', spy)
    await getTimeSeries('demo-rwanda-1', -1.95, 30.06)
    expect(spy).toHaveBeenCalledWith('/api/demo/aois/demo-rwanda-1/timeseries?lat=-1.95&lng=30.06')
  })
})

describe('movement image URLs', () => {
  it('builds a period-scoped heatmap URL', () => {
    expect(movementImageUrl('demo-rwanda-1', '2026-01-01', '2026-06-01')).toBe(
      '/api/demo/aois/demo-rwanda-1/images/movement?start=2026-01-01&end=2026-06-01',
    )
  })

  it('builds per-visit backscatter URLs', () => {
    expect(visitImageUrl('demo-rwanda-1', 7)).toBe(
      '/api/demo/aois/demo-rwanda-1/images/visit/7',
    )
  })
})

describe('getMovement', () => {
  it('encodes the period as query params', async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ stats: { n_areas: 2 } }), { status: 200 }),
    )
    vi.stubGlobal('fetch', spy)
    const result = await getMovement('demo-rwanda-1', '2026-01-01', '2026-06-01')
    expect(spy).toHaveBeenCalledWith(
      '/api/demo/aois/demo-rwanda-1/movement?start=2026-01-01&end=2026-06-01',
    )
    expect(result.stats.n_areas).toBe(2)
  })

  it('propagates API failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('{"detail":"at least 2 are required"}', { status: 422 }),
      ),
    )
    await expect(getMovement('demo-rwanda-1', '2026-09-01', '2026-09-02')).rejects.toThrow('422')
  })
})

describe('getAcquisitions', () => {
  it('fetches the Sentinel-1 visit schedule', async () => {
    const payload = {
      aoi_id: 'demo-rwanda-1',
      cycle_days: 12,
      acquisitions: [{ id: 'a', index: 0, date: '2025-08-04' }],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 })),
    )
    const result = await getAcquisitions('demo-rwanda-1')
    expect(result.cycle_days).toBe(12)
    expect(result.acquisitions).toHaveLength(1)
    expect(result.acquisitions[0].date).toBe('2025-08-04')
  })
})
