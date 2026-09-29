import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  imageUrl,
  listAois,
  getAnomalies,
  getTimeSeries,
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
