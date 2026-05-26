import { create } from 'zustand'
import { HarnessEvent, messageIdForEvent, projectHarnessEvent } from './harnessEvents'

export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'ai' | 'tool' | 'system'
  content: string
  timestamp: string
  toolName?: string
  eightConfirmations?: string
  isOutline?: boolean
  isResultActions?: boolean
}

export interface SvgPageData {
  page: number
  filename: string
  svgContent: string
}

export interface OutlineItem {
  page: number
  title: string
  summary: string
  status: 'pending' | 'generating' | 'completed'
}

export interface HistoryJob {
  job_id: string
  status: 'pending' | 'running' | 'confirming' | 'completed' | 'failed'
  project_name: string
  source_file?: string
  created_at?: string
  pinned_at?: string | null
  error?: string
}

export interface SkillInfo {
  name: string
  description: string
  version: string
  icon: string
  requires: string[]
  installed: boolean
  active: boolean
}

export interface MarketplaceSkill {
  id: string
  name: string
  description: string
  version: string
  author: string
  icon: string
  category: string
  installed: boolean
}

interface AppStore {
  // === 状态 ===
  phase: 'idle' | 'running' | 'confirming' | 'done' | 'error'
  
  // === 历史任务 ===
  historyJobs: HistoryJob[]
  
  // === 输入 ===
  file: File | null
  fileId: string
  url: string
  inputText: string

  // === 配置 ===
  canvasFormat: 'ppt169' | 'ppt43'

  // === 任务 ===
  jobId: string
  skillUiType: string // 'svg_slides' | 'code_editor' | 'interactive_table' | 'markdown'
  currentStep: number // 1-7
  currentStepName: string
  logs: LogEntry[]
  errorMessage: string

  // === 对话消息流 ===
  messages: ChatMessage[]

  // === 大纲 ===
  outline: OutlineItem[]

  // === SVG 实时预览 ===
  svgPages: SvgPageData[]
  currentPreviewPage: number // 当前右侧预览的页码
  totalPlannedPages: number

  // === 结果文件 ===
  pptxUrl: string
  pptxSize: number
  totalPages: number
  durationMs: number
  notes: Record<string, string>

  // === 技能管理 ===
  activeSkills: SkillInfo[]
  marketplaceSkills: MarketplaceSkill[]
  skillsLoading: boolean

  // === Actions ===
  setFile: (f: File | null) => void
  setUrl: (url: string) => void
  setFileId: (id: string) => void
  setInputText: (text: string) => void
  setCanvasFormat: (format: 'ppt169' | 'ppt43') => void
  setHistoryJobs: (jobs: HistoryJob[]) => void
  setJobId: (id: string) => void
  setSkillUiType: (uiType: string) => void
  setPhase: (phase: AppStore['phase']) => void
  setCurrentStep: (step: number, name?: string) => void
  
  addLog: (log: Omit<LogEntry, 'id'>) => void
  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  clearMessages: () => void

  setOutline: (items: OutlineItem[]) => void
  updateOutlineStatus: (page: number, status: OutlineItem['status']) => void

  updateSvgPage: (page: number, svgContent: string, filename?: string) => void
  setCurrentPreviewPage: (page: number) => void
  
  setPipelineResult: (result: { pptxUrl: string; pptxSize: number; totalPages: number; durationMs: number }) => void
  setNotes: (notes: Record<string, string>) => void
  setError: (msg: string) => void
  applyHarnessEvent: (event: HarnessEvent, options?: { replay?: boolean }) => Promise<void>
  loadJobState: (jobId: string) => Promise<void>
  reset: () => void

  // === 技能管理 Actions ===
  fetchActiveSkills: () => Promise<void>
  fetchMarketplace: () => Promise<void>
  installSkill: (skillId: string) => Promise<boolean>
  uninstallSkill: (skillId: string) => Promise<boolean>
}

const initialState = {
  phase: 'idle' as const,
  historyJobs: [] as HistoryJob[],
  file: null as File | null,
  fileId: '',
  url: '',
  inputText: '',
  canvasFormat: 'ppt169' as const,
  jobId: '',
  skillUiType: 'svg_slides',
  currentStep: 0,
  currentStepName: '',
  logs: [] as LogEntry[],
  errorMessage: '',
  messages: [] as ChatMessage[],
  outline: [] as OutlineItem[],
  svgPages: [] as SvgPageData[],
  currentPreviewPage: 1,
  totalPlannedPages: 0,
  pptxUrl: '',
  pptxSize: 0,
  totalPages: 0,
  durationMs: 0,
  notes: {} as Record<string, string>,
  activeSkills: [] as SkillInfo[],
  marketplaceSkills: [] as MarketplaceSkill[],
  skillsLoading: false,
}

export const useAppStore = create<AppStore>((set, get) => ({
  ...initialState,

  setFile: (f) => set({ file: f }),
  setUrl: (url) => set({ url }),
  setFileId: (id) => set({ fileId: id }),
  setInputText: (text) => set({ inputText: text }),
  setCanvasFormat: (format) => set({ canvasFormat: format }),
  setHistoryJobs: (jobs) => set({ historyJobs: jobs }),
  setJobId: (id) => {
    set({ jobId: id })
    try { localStorage.setItem('ppt_active_job', id) } catch {}
  },
  setSkillUiType: (uiType) => set({ skillUiType: uiType }),
  setPhase: (phase) => set({ phase }),
  setCurrentStep: (step, name) => set((state) => ({
    currentStep: step,
    currentStepName: name !== undefined ? name : state.currentStepName
  })),

  addLog: (log) => set((state) => ({
    logs: [...state.logs.slice(-499), { ...log, id: Date.now().toString() + Math.random().toString(36).slice(2) }],
  })),

  addMessage: (msg) => set((state) => ({
    messages: [
      ...state.messages,
      {
        ...msg,
        id: Date.now().toString() + Math.random().toString(36).slice(2),
        timestamp: new Date().toISOString()
      }
    ]
  })),

  clearMessages: () => set({ messages: [] }),

  setOutline: (items) => set({ outline: items, totalPlannedPages: items.length }),
  
  updateOutlineStatus: (page, status) => set((state) => ({
    outline: state.outline.map((item) =>
      item.page === page ? { ...item, status } : item
    )
  })),

  updateSvgPage: (page, svgContent, filename) => set((state) => {
    const list = [...state.svgPages]
    const idx = list.findIndex((p) => p.page === page)
    const newPage = { page, svgContent, filename: filename || `page_${page.toString().padStart(2, '0')}.svg` }
    if (idx >= 0) {
      list[idx] = newPage
    } else {
      list.push(newPage)
    }
    list.sort((a, b) => a.page - b.page)

    // 联动更新大纲状态为已完成
    const updatedOutline = state.outline.map((item) =>
      item.page === page ? { ...item, status: 'completed' as const } : item
    )

    return {
      svgPages: list,
      outline: updatedOutline,
      currentPreviewPage: page, // 实时渲染自动切到最新生成的页
    }
  }),

  setCurrentPreviewPage: (page) => set({ currentPreviewPage: page }),

  setPipelineResult: (result) => set({
    pptxUrl: result.pptxUrl,
    pptxSize: result.pptxSize,
    totalPages: result.totalPages,
    durationMs: result.durationMs,
    phase: 'done',
  }),

  setNotes: (notes) => set({ notes }),

  setError: (msg) => set({ errorMessage: msg, phase: 'error' }),

  applyHarnessEvent: async (event, options) => {
    const projection = projectHarnessEvent(event)
    const replay = options?.replay || false
    const timestamp = event.ts || event.timestamp || new Date().toISOString()

    if (projection.currentStep) {
      set({
        currentStep: projection.currentStep.step,
        currentStepName: projection.currentStep.name,
      })
    }

    if (projection.phase) {
      set({ phase: projection.phase })
    }

    if (projection.errorMessage) {
      set({ errorMessage: projection.errorMessage })
    }

    if (projection.outline) {
      set({ outline: projection.outline, totalPlannedPages: projection.outline.length })
    }

    if (projection.log) {
      const id = messageIdForEvent(event, 'log')
      set((state) => {
        if (state.logs.some((log) => log.id === id)) return {}
        return { logs: [...state.logs.slice(-499), { ...projection.log!, id }] }
      })
    }

    if (projection.chat) {
      const id = messageIdForEvent(event, 'chat')
      set((state) => {
        if (state.messages.some((msg) => msg.id === id)) return {}
        return { messages: [...state.messages, { ...projection.chat!, id, timestamp: projection.chat!.timestamp || timestamp }] }
      })
    }

    if (projection.svgArtifact) {
      const state = get()
      const page = projection.svgArtifact.page
      if (state.jobId && page) {
        try {
          const pageName = projection.svgArtifact.filename.replace(/\.svg$/i, '')
          const res = await fetch(`/api/projects/${state.jobId}/svg/${pageName}`)
          if (res.ok) {
            const data = await res.json()
            get().updateSvgPage(page, data.svg, projection.svgArtifact.filename)
          }
        } catch (e) {
          if (!replay) console.warn('Load SVG artifact from event failed:', e)
        }
      }
    }

    if (projection.resultActions) {
      const state = get()
      if (!state.jobId) return
      try {
        const res = await fetch(`/api/status/${state.jobId}`)
        if (res.ok) {
          const data = await res.json()
          const result = data.result || {}
          get().setPipelineResult({
            pptxUrl: `/api/download/${state.jobId}`,
            pptxSize: result.pptx_size || state.pptxSize || 0,
            totalPages: result.total_pages || state.svgPages.length,
            durationMs: result.duration_ms || state.durationMs || 0,
          })
        } else {
          get().setPipelineResult({
            pptxUrl: `/api/download/${state.jobId}`,
            pptxSize: state.pptxSize || 0,
            totalPages: state.svgPages.length,
            durationMs: state.durationMs || 0,
          })
        }
      } catch {
        const latest = get()
        get().setPipelineResult({
          pptxUrl: `/api/download/${latest.jobId}`,
          pptxSize: latest.pptxSize || 0,
          totalPages: latest.svgPages.length,
          durationMs: latest.durationMs || 0,
        })
      }
    }
  },
  
  loadJobState: async (jobId) => {
    try {
      set({ jobId, phase: 'running', logs: [], messages: [], svgPages: [], outline: [] })
      try { localStorage.setItem('ppt_active_job', jobId) } catch {}
      
      // 1. 获取基础状态
      const statusRes = await fetch(`/api/status/${jobId}`)
      if (!statusRes.ok) throw new Error('Job not found')
      const statusData = await statusRes.json()
      
      const backendStatus = statusData.status // pending, running, confirming, completed, failed
      let mappedPhase: AppStore['phase'] = 'idle'
      if (backendStatus === 'running') mappedPhase = 'running'
      else if (backendStatus === 'confirming') mappedPhase = 'confirming'
      else if (backendStatus === 'completed') mappedPhase = 'done'
      else if (backendStatus === 'failed') mappedPhase = 'error'
      else if (backendStatus === 'pending') mappedPhase = 'running'

      set({
        phase: mappedPhase,
        skillUiType: statusData.skill_ui_type || 'svg_slides',
        currentStep: statusData.current_step || 0,
        currentStepName: statusData.current_step_name || '',
        errorMessage: statusData.error || '',
      })

      // 2. 加载大纲设计和 spec
      try {
        const specRes = await fetch(`/api/projects/${jobId}/spec`)
        if (specRes.ok) {
          const specData = await specRes.json()
          if (specData.design_spec) {
            // 解析大纲
            const lines = specData.design_spec.split('\n')
            const parsedOutline: OutlineItem[] = []
            let pageNum = 0
            for (const line of lines) {
              const m = line.match(/^(?:#+)\s*(?:第\s*(\d+)\s*页|Page\s*(\d+))[\s·:：-]*([^\n]*)/i)
              if (m) {
                pageNum = parseInt(m[1] || m[2])
                parsedOutline.push({
                  page: pageNum,
                  title: m[3].trim() || `第 ${pageNum} 页`,
                  summary: '',
                  status: 'completed'
                })
              } else if (pageNum > 0 && line.trim().startsWith('-')) {
                const last = parsedOutline[parsedOutline.length - 1]
                if (last) last.summary += line.trim() + '\n'
              }
            }
            if (parsedOutline.length > 0) {
              set({ outline: parsedOutline, totalPlannedPages: parsedOutline.length })
            }
          }
        }
      } catch (e) {
        console.warn('Load outline failed:', e)
      }

      // 3. 加载已有 SVGs
      try {
        const svgsRes = await fetch(`/api/projects/${jobId}/svgs`)
        if (svgsRes.ok) {
          const svgsData = await svgsRes.json()
          if (svgsData.svgs && Array.isArray(svgsData.svgs)) {
            const list: SvgPageData[] = []
            for (const item of svgsData.svgs) {
              // 逐页获取真实 SVG 内容
              const pageName = item.page // page_01 等
              const detailRes = await fetch(`/api/projects/${jobId}/svg/${pageName}`)
              if (detailRes.ok) {
                const detailData = await detailRes.json()
                const pNum = parseInt(pageName.replace(/[^\d]/g, '')) || 1
                list.push({
                  page: pNum,
                  filename: item.filename,
                  svgContent: detailData.svg
                })
              }
            }
            list.sort((a, b) => a.page - b.page)
            set({ svgPages: list })
          }
        }
      } catch (e) {
        console.warn('Load SVGs failed:', e)
      }

      // 4. 加载演讲稿 notes
      try {
        const notesRes = await fetch(`/api/projects/${jobId}/notes`)
        if (notesRes.ok) {
          const notesData = await notesRes.json()
          set({ notes: notesData.notes || {} })
        }
      } catch (e) {
        console.warn('Load notes failed:', e)
      }

      // 5. 设置结果
      if (backendStatus === 'completed' && statusData.result) {
        set({
          pptxUrl: `/api/download/${jobId}`,
          pptxSize: statusData.result.pptx_size || 0,
          totalPages: statusData.result.total_pages || 0,
          durationMs: statusData.result.duration_ms || 0,
        })
      }

      // 6. Replay historical events through the same projection path as WebSocket
      try {
        const eventsRes = await fetch(`/api/projects/${jobId}/events`)
        if (eventsRes.ok) {
          const eventsData = await eventsRes.json()
          const events = eventsData.events || []
          for (const ev of events) {
            await get().applyHarnessEvent(ev, { replay: true })
          }
        }
      } catch (e) {
        console.warn('Load events for chat replay failed:', e)
      }

      // Only add minimal fallback if events API had no displayable events
      if (get().messages.length === 0) {
        const timestamp = new Date().toISOString()
        if (mappedPhase === 'done') {
          set((state) => ({ messages: [...state.messages, { id: 'msg-done', role: 'ai', content: `🎉 **PPT 已就绪**，可预览或下载。`, timestamp, isResultActions: true }] }))
        } else if (mappedPhase === 'confirming') {
          set((state) => ({ messages: [...state.messages, { id: 'msg-confirm', role: 'ai', content: `⏸ 待确认设计提案`, timestamp, eightConfirmations: statusData.result?.eight_confirmations || '' }] }))
        } else if (mappedPhase === 'error') {
          set((state) => ({ messages: [...state.messages, { id: 'msg-err', role: 'ai', content: `❌ 失败: ${statusData.error || '未知错误'}`, timestamp }] }))
        }
      }

    } catch (err: any) {
      set({ errorMessage: `加载项目失败: ${err.message}`, phase: 'error' })
    }
  },

  reset: () => {
    try { localStorage.removeItem('ppt_active_job') } catch {}
    set((state) => ({
      ...initialState,
      historyJobs: state.historyJobs, // 保留历史项目列表
    }))
  },

  // === 技能管理 Actions 实现 ===
  fetchActiveSkills: async () => {
    try {
      const res = await fetch('/api/skills')
      if (res.ok) {
        const data = await res.json()
        set({ activeSkills: data })
      }
    } catch (e) {
      console.warn('Fetch active skills failed:', e)
    }
  },

  fetchMarketplace: async () => {
    set({ skillsLoading: true })
    try {
      const res = await fetch('/api/skills/marketplace')
      if (res.ok) {
        const data = await res.json()
        set({ marketplaceSkills: data })
      }
    } catch (e) {
      console.warn('Fetch marketplace failed:', e)
    } finally {
      set({ skillsLoading: false })
    }
  },

  installSkill: async (skillId: string) => {
    try {
      const res = await fetch(`/api/skills/install/${skillId}`, { method: 'POST' })
      if (res.ok) {
        await get().fetchActiveSkills()
        await get().fetchMarketplace()
        return true
      }
      return false
    } catch (e) {
      console.warn('Install skill failed:', e)
      return false
    }
  },

  uninstallSkill: async (skillId: string) => {
    try {
      const res = await fetch(`/api/skills/uninstall/${skillId}`, { method: 'POST' })
      if (res.ok) {
        await get().fetchActiveSkills()
        await get().fetchMarketplace()
        return true
      }
      return false
    } catch (e) {
      console.warn('Uninstall skill failed:', e)
      return false
    }
  },
}))
