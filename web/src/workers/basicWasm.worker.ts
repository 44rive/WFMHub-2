import type { WorkerResponse } from '../compatibility/types'

const wasmAnswerModule = new Uint8Array([
  0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00, 0x01, 0x05, 0x01, 0x60, 0x00, 0x01, 0x7f, 0x03,
  0x02, 0x01, 0x00, 0x07, 0x0a, 0x01, 0x06, 0x61, 0x6e, 0x73, 0x77, 0x65, 0x72, 0x00, 0x00, 0x0a,
  0x06, 0x01, 0x04, 0x00, 0x41, 0x2a, 0x0b,
])

self.addEventListener('message', async () => {
  try {
    const instance = await WebAssembly.instantiate(wasmAnswerModule)
    const answer = (instance.instance.exports.answer as () => number)()
    if (answer !== 42) {
      throw new Error(`WebAssembly returned ${answer}, expected 42`)
    }
    const response: WorkerResponse = {
      ok: true,
      details: { answer, worker: true, webAssembly: true },
    }
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
