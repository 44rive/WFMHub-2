import * as duckdb from '@duckdb/duckdb-wasm'
import duckdbEhWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'
import duckdbMvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url'
import duckdbEhWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import duckdbMvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'
import type { WorkerResponse } from '../compatibility/types'

const bundles: duckdb.DuckDBBundles = {
  mvp: { mainModule: duckdbMvpWasm, mainWorker: duckdbMvpWorker },
  eh: { mainModule: duckdbEhWasm, mainWorker: duckdbEhWorker },
}

async function openDatabase() {
  const bundle = await duckdb.selectBundle(bundles)
  if (!bundle.mainWorker) {
    throw new Error('DuckDB-Wasm did not select a browser worker')
  }
  const worker = new Worker(bundle.mainWorker)
  const database = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker)
  await database.instantiate(bundle.mainModule, bundle.pthreadWorker)
  await database.open({
    path: 'opfs://wfmhub2-compatibility.duckdb',
    accessMode: duckdb.DuckDBAccessMode.READ_WRITE,
  })
  return { database, bundle }
}

function counterFrom(rows: unknown[]): number {
  const row = rows[0] as { counter?: number | bigint } | undefined
  if (!row || row.counter === undefined) {
    throw new Error('DuckDB query returned no compatibility counter')
  }
  return Number(row.counter)
}

async function runProbe(): Promise<Record<string, unknown>> {
  if (!navigator.storage?.getDirectory) {
    throw new Error('Origin Private File System is unavailable')
  }

  const first = await openDatabase()
  let written: number
  const firstConnection = await first.database.connect()
  try {
    await firstConnection.query(`
      CREATE TABLE IF NOT EXISTS compatibility_counter (
        id INTEGER PRIMARY KEY,
        counter INTEGER NOT NULL
      );
      INSERT OR IGNORE INTO compatibility_counter VALUES (1, 0);
      UPDATE compatibility_counter SET counter = counter + 1 WHERE id = 1;
      CHECKPOINT;
    `)
    const result = await firstConnection.query(
      'SELECT counter FROM compatibility_counter WHERE id = 1',
    )
    written = counterFrom(result.toArray())
  } finally {
    await firstConnection.close()
    await first.database.terminate()
  }

  const second = await openDatabase()
  const secondConnection = await second.database.connect()
  let reopened: number
  try {
    const result = await secondConnection.query(
      'SELECT counter FROM compatibility_counter WHERE id = 1',
    )
    reopened = counterFrom(result.toArray())
  } finally {
    await secondConnection.close()
    await second.database.terminate()
  }
  if (reopened !== written) {
    throw new Error(`OPFS reopen returned ${reopened}; expected ${written}`)
  }
  return {
    duckdbWasm: duckdb.PACKAGE_VERSION,
    bundle: first.bundle.mainModule.includes('eh') ? 'exception-handling' : 'mvp',
    opfsCounter: reopened,
    checkpointAndReopen: true,
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
