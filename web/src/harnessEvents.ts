export interface HarnessEvent {
  seq?: number
  ts?: string
  timestamp?: string
  type: string
  message?: string
  payload?: Record<string, any>
}

export interface ChatProjection {
  role: 'user' | 'ai' | 'tool' | 'system'
  content: string
  timestamp: string
  eightConfirmations?: string
  isOutline?: boolean
  isResultActions?: boolean
}

export interface LogProjection {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
}

export interface OutlineProjection {
  page: number
  title: string
  summary: string
  status: 'pending' | 'generating' | 'completed'
}

export interface EventProjection {
  chat?: ChatProjection
  log?: LogProjection
  outline?: OutlineProjection[]
  phase?: 'running' | 'confirming' | 'done' | 'error'
  currentStep?: { step: number; name: string }
  svgArtifact?: { page: number; filename: string; path: string }
  svgStreaming?: { page: number; svg: string }
  resultActions?: boolean
  errorMessage?: string
}

const STEP_MAP: Record<string, { step: number; name: string }> = {
  source_processing: { step: 1, name: '源文件处理' },
  topic_research: { step: 1, name: '话题调研' },
  project_init: { step: 2, name: '项目初始化' },
  template_check: { step: 3, name: '模板检查' },
  strategist: { step: 4, name: '设计策略' },
  generate_spec: { step: 4, name: '设计文档生成' },
  image_acquisition: { step: 5, name: '图片获取' },
  executor: { step: 6, name: 'SVG 页面生成' },
  quality_check: { step: 6, name: '质量检查' },
  notes: { step: 6, name: '演讲稿生成' },
  export: { step: 7, name: '后处理与导出' },
}

function eventTimestamp(event: HarnessEvent): string {
  return event.ts || event.timestamp || new Date().toISOString()
}

function pageFromPath(path: string): number {
  const match = path.match(/page_(\d+)/) || path.match(/(\d+)/)
  return match ? parseInt(match[1], 10) : 0
}

function outlineFromPayloadPages(pages: any[]): OutlineProjection[] {
  return pages.map((item, index) => ({
    page: Number(item.page || item.page_number || index + 1),
    title: String(item.title || `第 ${index + 1} 页`),
    summary: String(item.summary || item.brief || ''),
    status: item.status === 'completed' || item.status === 'generating' ? item.status : 'pending',
  }))
}

export function projectHarnessEvent(event: HarnessEvent): EventProjection {
  const payload = event.payload || {}
  const msg = event.message || ''
  const timestamp = eventTimestamp(event)

  switch (event.type) {
    case 'job_started':
      return {
        phase: 'running',
        chat: { role: 'ai', content: `🚀 **任务已启动** — ${msg}`, timestamp },
        log: { timestamp, level: 'info', message: msg || '任务已启动' },
      }
    case 'job_resumed':
      return {
        phase: 'running',
        log: { timestamp, level: 'info', message: '用户已确认，继续生成' },
      }
    case 'step_start': {
      const stepKey = String(payload.step || '')
      const mapped = STEP_MAP[stepKey] || { step: 0, name: msg || stepKey }
      return {
        phase: 'running',
        currentStep: mapped,
        chat: { role: 'ai', content: `▶ ${msg || `正在进行 ${mapped.name}...`}`, timestamp },
        log: { timestamp, level: 'info', message: `▶ 步骤 ${mapped.step}: ${mapped.name}` },
      }
    }
    case 'step_done': {
      const stepKey = String(payload.step || '')
      const mapped = STEP_MAP[stepKey] || { step: 0, name: msg || stepKey }
      return {
        log: { timestamp, level: 'info', message: msg || `✓ 步骤 ${mapped.step}: ${mapped.name} 完成` },
        chat: msg ? { role: 'ai', content: `✅ ${msg}`, timestamp } : undefined,
      }
    }
    case 'outline': {
      const pages = Array.isArray(payload.pages) ? payload.pages : []
      return {
        outline: outlineFromPayloadPages(pages),
        chat: { role: 'ai', content: `📊 **PPT 结构大纲已生成**，共 ${pages.length || '?'} 页。`, timestamp, isOutline: true },
      }
    }
    case 'confirmation_required':
      return {
        phase: 'confirming',
        currentStep: { step: 4, name: '等待确认' },
        chat: {
          role: 'ai',
          content: `⏸ ${msg || '请确认设计方案'}`,
          timestamp,
          eightConfirmations: String(payload.content_preview || payload.content || ''),
        },
        log: { timestamp, level: 'warning', message: '⏸ 等待确认设计方案' },
      }
    case 'job_waiting':
      return {
        phase: 'confirming',
        currentStep: { step: 4, name: '等待确认' },
        log: { timestamp, level: 'warning', message: msg || '等待用户确认' },
      }
    case 'page_generating':
      return {
        log: { timestamp, level: 'info', message: `🖼 正在生成第 ${payload.page}/${payload.total} 页: ${payload.title || ''}` },
        chat: { role: 'ai', content: `🖼 正在生成第 ${payload.page}/${payload.total} 页: **${payload.title || ''}**`, timestamp },
      }
    case 'svg_streaming': {
      const page = Number(payload.page || 0)
      const svg = String(payload.svg || '')
      if (page && svg) {
        return { svgStreaming: { page, svg } }
      }
      return {}
    }
    case 'artifact_created': {
      const path = String(payload.path || '')
      const artType = String(payload.type || '')
      if (artType === 'svg' && path.includes('svg_output')) {
        const page = pageFromPath(path)
        return {
          svgArtifact: { page, filename: path.split('/').pop() || `page_${String(page).padStart(2, '0')}.svg`, path },
          log: { timestamp, level: 'info', message: `✨ 第 ${page} 页 SVG 生成完成` },
          chat: { role: 'ai', content: `✨ 第 ${page} 页 SVG 生成完成`, timestamp },
        }
      }
      return {
        log: { timestamp, level: 'info', message: `📎 产物已生成: ${path || artType}` },
      }
    }
    case 'page_error':
    case 'step_error': {
      const error = String(payload.error || msg || '未知错误')
      return {
        log: { timestamp, level: 'error', message: `❌ ${error}` },
        chat: { role: 'ai', content: event.type === 'page_error' ? `❌ 第 ${payload.page} 页生成失败: ${error}` : `❌ ${error}`, timestamp },
      }
    }
    case 'log': {
      const level = payload.level === 'error' ? 'error' : payload.level === 'warning' ? 'warning' : 'info'
      return {
        log: { timestamp, level, message: msg },
        chat: msg ? { role: 'ai', content: msg, timestamp } : undefined,
      }
    }
    case 'job_completed':
      return {
        phase: 'done',
        resultActions: true,
        chat: { role: 'ai', content: `🎉 **PPT 生成完成！** 可在右侧预览或点击下载。`, timestamp, isResultActions: true },
        log: { timestamp, level: 'info', message: '🎉 PPT 生成完成' },
      }
    case 'job_failed': {
      const error = msg || '未知错误'
      return {
        phase: 'error',
        errorMessage: error,
        chat: { role: 'ai', content: `❌ 任务失败: ${error}`, timestamp },
        log: { timestamp, level: 'error', message: `❌ ${error}` },
      }
    }
    case 'job_cancelled':
      return {
        phase: 'error',
        errorMessage: msg || '任务已被中断',
        chat: { role: 'system', content: msg || '任务已被中断', timestamp },
        log: { timestamp, level: 'warning', message: msg || '任务已被中断' },
      }
    default:
      return msg ? { log: { timestamp, level: 'info', message: msg } } : {}
  }
}

export function messageIdForEvent(event: HarnessEvent, suffix = 'chat'): string {
  return `evt-${event.seq || event.ts || Math.random().toString(36).slice(2)}-${suffix}`
}
