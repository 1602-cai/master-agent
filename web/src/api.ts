const BASE = '/api'

export async function uploadFile(file: File): Promise<{ file_id: string; filename: string; size: number }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: formData })
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
  return res.json()
}

export async function uploadUrl(url: string): Promise<{ file_id: string; filename: string; size: number }> {
  const res = await fetch(`${BASE}/upload_url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error(`URL upload failed: ${res.statusText}`)
  return res.json()
}

export async function startPipeline(params: {
  file_id?: string
  source_file?: string
  canvas_format?: string
  auto_mode?: boolean
  enable_images?: boolean
  user_request?: string
}): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${BASE}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`Start failed: ${res.statusText}`)
  return res.json()
}

export async function getStatus(jobId: string): Promise<any> {
  const res = await fetch(`${BASE}/status/${jobId}`)
  if (!res.ok) throw new Error(`Status failed: ${res.statusText}`)
  return res.json()
}

export async function confirmDesign(jobId: string, action: 'confirm' | 'split' | 'modify', feedback?: string): Promise<{ status: string; action: string; feedback: string }> {
  const res = await fetch(`${BASE}/confirm/${jobId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, feedback }),
  })
  if (!res.ok) throw new Error(`Confirm failed: ${res.statusText}`)
  return res.json()
}

export async function cancelJob(jobId: string): Promise<{ status: string; cancelled: boolean }> {
  const res = await fetch(`${BASE}/jobs/${jobId}/cancel`, { method: 'POST' })
  if (!res.ok) throw new Error(`Cancel failed: ${res.statusText}`)
  return res.json()
}

export async function downloadPptx(jobId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/download/${jobId}`)
  if (!res.ok) throw new Error(`Download failed: ${res.statusText}`)
  return res.blob()
}

export async function getSvgs(jobId: string): Promise<{ svgs: { page: string; filename: string; size: number }[]; total: number }> {
  const res = await fetch(`${BASE}/projects/${jobId}/svgs`)
  if (!res.ok) throw new Error(`Get SVGs failed: ${res.statusText}`)
  return res.json()
}

export async function getSvgContent(jobId: string, page: string): Promise<{ page: string; svg: string }> {
  const res = await fetch(`${BASE}/projects/${jobId}/svg/${page}`)
  if (!res.ok) throw new Error(`Get SVG failed: ${res.statusText}`)
  return res.json()
}

export async function getNotes(jobId: string): Promise<{ notes: Record<string, string> }> {
  const res = await fetch(`${BASE}/projects/${jobId}/notes`)
  if (!res.ok) throw new Error(`Get notes failed: ${res.statusText}`)
  return res.json()
}

export async function getSpec(jobId: string): Promise<{ design_spec: string; spec_lock: string; eight_confirmations: string }> {
  const res = await fetch(`${BASE}/projects/${jobId}/spec`)
  if (!res.ok) throw new Error(`Get spec failed: ${res.statusText}`)
  return res.json()
}

// ── LLM Settings ──

export interface LLMProviderInfo {
  name: string
  base_url: string
  models: string[]
}

export interface LLMSettings {
  provider: string
  base_url: string
  model: string
  api_key_set: boolean
  api_key_preview: string
  providers: Record<string, LLMProviderInfo>
}

export async function getLLMSettings(): Promise<LLMSettings> {
  const res = await fetch(`${BASE}/settings/llm`)
  if (!res.ok) throw new Error(`Get LLM settings failed: ${res.statusText}`)
  return res.json()
}

export async function updateLLMSettings(params: {
  provider: string
  api_key?: string
  base_url?: string
  model?: string
}): Promise<{ status: string; provider: string; base_url: string; model: string }> {
  const res = await fetch(`${BASE}/settings/llm`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || `Update LLM settings failed: ${res.statusText}`)
  }
  return res.json()
}
