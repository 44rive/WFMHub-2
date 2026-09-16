const API_BASE = 'http://127.0.0.1:8765/api'

export type Health = {
  status: string
  version: string
  architecture: string
}

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) {
    throw new Error(`Engine health request failed: ${response.status}`)
  }
  return response.json() as Promise<Health>
}
