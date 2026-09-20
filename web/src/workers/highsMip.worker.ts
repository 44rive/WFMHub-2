import loadHighs from 'highs'
import type { WorkerResponse } from '../compatibility/types'

async function runProbe(): Promise<Record<string, unknown>> {
  const highs = await loadHighs()
  const model = `Minimize
    staffing_cost: 3 early + 2 late
  Subject To
    coverage: early + late >= 7
  Bounds
    0 <= early <= 5
    0 <= late <= 4
  Generals
    early late
  End`
  const result = highs.solve(model, { output_flag: false })
  if (result.Status !== 'Optimal') {
    throw new Error(`HiGHS ended with status ${result.Status}`)
  }
  const early = result.Columns.early?.Primal
  const late = result.Columns.late?.Primal
  if (early !== 3 || late !== 4 || result.ObjectiveValue !== 17) {
    throw new Error(
      `Unexpected staffing solution: early=${String(early)}, late=${String(late)}, objective=${result.ObjectiveValue}`,
    )
  }
  return {
    status: result.Status,
    objective: result.ObjectiveValue,
    early,
    late,
    integerModel: true,
  }
}

self.addEventListener('message', async () => {
  try {
    const response: WorkerResponse = { ok: true, details: await runProbe() }
    self.postMessage(response)
  } catch (error) {
    const response: WorkerResponse = {
      ok: false,
      error: {
        type: error instanceof Error ? error.name : 'Error',
        message: error instanceof Error ? error.message : String(error),
      },
    }
    self.postMessage(response)
  }
})
