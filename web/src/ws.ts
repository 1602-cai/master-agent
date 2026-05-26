import { useAppStore } from './store'

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectAttempts = 0
let currentJobId: string | null = null
const MAX_RECONNECTS = 10
const RECONNECT_DELAY = 3000

export function connectWebSocket(jobId: string) {
  if (ws && currentJobId === jobId && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }
  disconnectWebSocket()
  currentJobId = jobId

  // 开发模式直接连后端; 生产模式用当前 host
  const isDev = import.meta.env.DEV
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = isDev ? 'localhost:8000' : window.location.host
  const url = `${protocol}//${host}/ws/progress/${jobId}`

  ws = new WebSocket(url)

  ws.onopen = () => {
    console.log('[WS] Connected to', url)
    reconnectAttempts = 0
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      handleMessage(msg)
    } catch (e) {
      console.error('[WS] Parse error:', e)
    }
  }

  ws.onclose = () => {
    console.log('[WS] Disconnected')
    const store = useAppStore.getState()
    ws = null
    // 只在任务进行中时重连
    if (store.phase === 'running' || store.phase === 'confirming') {
      scheduleReconnect(jobId)
    }
  }

  ws.onerror = () => {
    console.warn('[WS] 连接异常，等待重连...')
  }
}

function scheduleReconnect(jobId: string) {
  if (reconnectAttempts >= MAX_RECONNECTS) {
    console.log('[WS] Max reconnect attempts reached')
    return
  }
  reconnectTimer = setTimeout(() => {
    reconnectAttempts++
    console.log(`[WS] Reconnecting... attempt ${reconnectAttempts}`)
    connectWebSocket(jobId)
  }, RECONNECT_DELAY)
}

export function disconnectWebSocket() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (ws) {
    ws.close()
    ws = null
  }
  currentJobId = null
}

async function handleMessage(msg: any) {
  const store = useAppStore.getState()

  if (msg.type === 'harness_event' && msg.event) {
    await store.applyHarnessEvent(msg.event)
    return
  }

  // Non-event control messages
  if (msg.type === 'connected' || msg.type === 'pong') {
    return
  }

  console.log('[WS] Unhandled message type:', msg.type)
}
