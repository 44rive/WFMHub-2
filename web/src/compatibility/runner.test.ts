import { describe, expect, it } from 'vitest'
import { probeLabels, probeOrder } from './runner'

describe('hybrid compatibility probe contract', () => {
  it('keeps every required capability explicit and ordered', () => {
    expect(probeOrder).toEqual([
      'host_sqlite',
      'wasm_worker',
      'duckdb_opfs',
      'pyodide_forecasting',
      'highs_mip',
    ])
    expect(Object.keys(probeLabels).sort()).toEqual([...probeOrder].sort())
  })
})
