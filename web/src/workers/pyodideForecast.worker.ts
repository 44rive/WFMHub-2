import { loadPyodide } from 'pyodide'
import type { WorkerResponse } from '../compatibility/types'

async function runProbe(): Promise<Record<string, unknown>> {
  const indexURL = new URL('/vendor/pyodide/', self.location.origin).href
  const pyodide = await loadPyodide({
    indexURL,
    lockFileURL: `${indexURL}pyodide-lock.json`,
  })
  await pyodide.loadPackage(['scikit-learn', 'statsmodels'])
  const raw = await pyodide.runPythonAsync(`
import json
import numpy as np
import sklearn
import statsmodels
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing

interval = np.arange(48, dtype=float)
volume = 100.0 + 1.75 * interval + 8.0 * np.sin(interval / 3.0)
features = np.column_stack((interval, interval % 4, interval % 12))

model = HistGradientBoostingRegressor(
    max_iter=24,
    max_depth=3,
    min_samples_leaf=2,
    random_state=42,
)
model.fit(features, volume)
tree_prediction = float(model.predict(np.array([[48.0, 0.0, 0.0]]))[0])

baseline = ExponentialSmoothing(volume, trend="add", initialization_method="estimated").fit()
statistical_prediction = float(baseline.forecast(1)[0])

json.dumps({
    "python": __import__("sys").version.split()[0],
    "numpy": np.__version__,
    "scikitLearn": sklearn.__version__,
    "statsmodels": statsmodels.__version__,
    "histGradientBoostingPrediction": round(tree_prediction, 4),
    "exponentialSmoothingPrediction": round(statistical_prediction, 4),
})
`)
  return JSON.parse(String(raw)) as Record<string, unknown>
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
