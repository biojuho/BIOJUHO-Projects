import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useFetch } from './useFetch.js'

function Harness() {
  const { data, loading, refetch } = useFetch('/api/example')
  return (
    <button type="button" onClick={refetch}>
      {loading ? 'loading' : data?.label || 'empty'}
    </button>
  )
}

beforeEach(() => {
  let calls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url, options) => {
      calls += 1
      return {
        ok: true,
        json: async () => ({ label: `value-${calls}`, signal: options.signal }),
      }
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('useFetch', () => {
  it('does not abort a completed request when refetching later', async () => {
    const signals = []
    global.fetch.mockImplementation(async (_url, options) => {
      signals.push(options.signal)
      return {
        ok: true,
        json: async () => ({ label: `value-${signals.length}` }),
      }
    })

    render(<Harness />)

    expect(await screen.findByText('value-1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(screen.getByText('value-2')).toBeInTheDocument()
    })
    expect(signals).toHaveLength(2)
    expect(signals[0].aborted).toBe(false)
    expect(signals[1].aborted).toBe(false)
  })
})
