import React, { useEffect, useState, useRef } from 'react'
import ReactDOM from 'react-dom'
import { useAppStore } from '../store'
import { connectWebSocket, disconnectWebSocket } from '../ws'
import { 
  Plus, 
  FolderOpen, 
  Loader2, 
  FileText,
  PanelLeftClose,
  PanelLeft,
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Trash2,
  Settings,
  Sparkles,
  Puzzle
} from 'lucide-react'
import SettingsModal from './SettingsModal'
import ClawSkillMarket from './ClawSkillMarket'

export default function Sidebar() {
  const { 
    phase, 
    jobId, 
    historyJobs, 
    setHistoryJobs, 
    loadJobState, 
    reset 
  } = useAppStore()

  const [loadingJobId, setLoadingJobId] = useState<string | null>(null)
  const [isProjectExpanded, setIsProjectExpanded] = useState(true)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [menuJobId, setMenuJobId] = useState<string | null>(null)
  const [menuPos, setMenuPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 })
  const [renamingJobId, setRenamingJobId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [showSkillMarket, setShowSkillMarket] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭菜单
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuJobId(null)
      }
    }
    if (menuJobId) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuJobId])

  // 1. 定期刷新历史 Job 列表
  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/jobs')
      if (res.ok) {
        const data = await res.json()
        setHistoryJobs(data.jobs || [])
      }
    } catch (e) {
      console.warn('Fetch history jobs failed:', e)
    }
  }

  useEffect(() => {
    fetchJobs()
    const timer = setInterval(fetchJobs, 8000) // 8秒轮询刷新一次
    return () => clearInterval(timer)
  }, [])

  // 2. 点击新建项目
  const handleNewProject = () => {
    disconnectWebSocket()
    reset()
  }

  // 3. 点击加载历史项目
  const handleLoadJob = async (id: string) => {
    if (loadingJobId) return
    // 如果已经是当前活动项目，不重复加载
    if (id === jobId && phase !== 'idle') return
    setLoadingJobId(id)
    disconnectWebSocket()
    try {
      await loadJobState(id)
      // 如果项目是运行中或确认中，重新建立 WS 推送
      connectWebSocket(id)
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingJobId(null)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-success'
      case 'running': return 'bg-accent animate-pulse'
      case 'confirming': return 'bg-warning animate-pulse'
      case 'failed': return 'bg-error'
      default: return 'bg-text-secondary/30'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed': return '已完成'
      case 'running': return '正在生成'
      case 'confirming': return '待确认'
      case 'failed': return '已失败'
      default: return '就绪'
    }
  }

  const handleRename = async (id: string) => {
    const trimmed = renameValue.trim()
    if (!trimmed) return
    try {
      const res = await fetch(`/api/jobs/${id}/rename`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      })
      if (res.ok) {
        setHistoryJobs(historyJobs.map(j => j.job_id === id ? { ...j, project_name: trimmed } : j))
      }
    } catch {}
    setRenamingJobId(null)
  }

  const handlePin = async (id: string) => {
    try {
      const res = await fetch(`/api/jobs/${id}/pin`, { method: 'PATCH' })
      if (res.ok) fetchJobs()
    } catch {}
    setMenuJobId(null)
  }

  const handleDelete = async (id: string) => {
    try {
      // Cancel first if running, then delete
      await fetch(`/api/jobs/${id}/cancel`, { method: 'POST' }).catch(() => {})
      const res = await fetch(`/api/jobs/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setHistoryJobs(historyJobs.filter(j => j.job_id !== id))
        if (id === jobId) reset()
      }
    } catch {}
    setMenuJobId(null)
  }

  return (
    <div className="flex h-screen bg-app-bg text-text-primary select-none border-r border-border-color/10">
      
      {/* ─── 侧边栏 SIDEBAR (项目历史 & 菜单) ─── */}
      <div className={`bg-sub-bg flex flex-col justify-between py-5 px-3 border-r border-border-color/10 transition-all duration-300 ${isSidebarCollapsed ? 'w-[56px] px-1.5' : 'w-[240px]'}`}>
        
        <div className="flex flex-col gap-4 overflow-hidden">
          {/* Header Title */}
          <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center' : 'justify-between'} px-2`}>
            {!isSidebarCollapsed && (
              <span className="font-semibold text-base tracking-wide bg-gradient-to-r from-text-primary to-text-primary/70 bg-clip-text text-transparent">
                PPT Master Agent
              </span>
            )}
            <button
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              className="text-text-secondary hover:text-text-primary transition-colors p-1 rounded-md hover:bg-border-color/10"
              title={isSidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
            >
              {isSidebarCollapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
          </div>

          {/* 新建项目大按钮 */}
          <button 
            onClick={handleNewProject}
            className={`flex items-center justify-center gap-2 w-full bg-accent hover:bg-accent-hover text-white rounded-xl transition-all font-medium text-sm shadow-md shadow-accent/10 hover:shadow-accent/20 group hover:scale-[1.01] active:scale-[0.99] ${isSidebarCollapsed ? 'p-2.5' : 'py-3 px-4'}`}
            title="新建项目"
          >
            <Plus className="w-4 h-4 group-hover:rotate-90 transition-all duration-300" />
            {!isSidebarCollapsed && '新建项目'}
          </button>


          {/* 历史项目列表 */}
          <div className="flex flex-col flex-1 overflow-hidden mt-2">
            {isSidebarCollapsed ? (
              <div className="flex justify-center py-2">
                <FolderOpen className="w-4 h-4 text-text-secondary/50" />
              </div>
            ) : (
            <button 
              onClick={() => setIsProjectExpanded(!isProjectExpanded)}
              className="flex items-center justify-between px-3 py-2 text-text-secondary hover:text-text-primary text-xs font-semibold uppercase tracking-wider"
            >
              <div className="flex items-center gap-2">
                <FolderOpen className="w-3.5 h-3.5" />
                项目历史
              </div>
              {isProjectExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
            )}

            {isProjectExpanded && !isSidebarCollapsed && (
              <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-1 mt-1 scrollbar-thin">
                {historyJobs.length === 0 ? (
                  <div className="text-center py-8 text-text-secondary/40 text-xs flex flex-col items-center gap-2">
                    <FileText className="w-6 h-6 opacity-40" />
                    暂无生成项目
                  </div>
                ) : (
                  historyJobs.map((job) => {
                    const isCurrent = job.job_id === jobId && phase !== 'idle'
                    const displayTitle = job.project_name || job.source_file || `未命名项目_${job.job_id}`
                    const isPinned = !!job.pinned_at
                    const isRenaming = renamingJobId === job.job_id
                    
                    return (
                      <div key={job.job_id} className="relative group/item">
                        <button
                          disabled={loadingJobId === job.job_id}
                          onClick={() => handleLoadJob(job.job_id)}
                          className={`flex flex-col items-start text-left w-full p-2.5 rounded-lg text-sm transition-all group ${
                            isCurrent 
                              ? 'bg-accent/10 border border-accent/20 text-accent font-medium' 
                              : 'hover:bg-border-color/5 text-text-secondary hover:text-text-primary border border-transparent'
                          }`}
                        >
                          <div className="flex items-center justify-between w-full gap-1">
                            {isPinned && <Pin className="w-3 h-3 text-accent shrink-0" />}
                            {isRenaming ? (
                              <input
                                autoFocus
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                onBlur={() => handleRename(job.job_id)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleRename(job.job_id)
                                  if (e.key === 'Escape') setRenamingJobId(null)
                                }}
                                onClick={(e) => e.stopPropagation()}
                                className="flex-1 bg-card-bg border border-accent/30 rounded px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-accent"
                              />
                            ) : (
                              <span className="truncate flex-1 pr-1" title={displayTitle}>
                                {displayTitle}
                              </span>
                            )}
                            
                            {/* 状态徽章 */}
                            {loadingJobId === job.job_id ? (
                              <Loader2 className="w-3 h-3 animate-spin text-accent shrink-0" />
                            ) : (
                              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${getStatusColor(job.status)}`} title={getStatusText(job.status)} />
                            )}
                          </div>

                          {job.source_file && (
                            <span className="text-[11px] text-text-secondary/50 truncate w-full mt-0.5 group-hover:text-text-secondary/70">
                              📄 {job.source_file}
                            </span>
                          )}
                        </button>

                        {/* 三点菜单按钮 */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (menuJobId === job.job_id) {
                              setMenuJobId(null)
                            } else {
                              const rect = e.currentTarget.getBoundingClientRect()
                              setMenuPos({ top: rect.bottom + 4, left: rect.right - 128 })
                              setMenuJobId(job.job_id)
                            }
                          }}
                          className="absolute right-1.5 top-1.5 w-6 h-6 rounded-md flex items-center justify-center opacity-0 group-hover/item:opacity-100 hover:bg-border-color/20 transition-all"
                        >
                          <MoreHorizontal className="w-3.5 h-3.5 text-text-secondary" />
                        </button>

                        {/* 下拉菜单 (Portal 到 body) */}
                        {menuJobId === job.job_id && ReactDOM.createPortal(
                          <div
                            ref={menuRef}
                            className="fixed z-[9999] w-32 bg-card-bg border border-border-color/20 rounded-lg shadow-xl py-1 text-xs"
                            style={{ top: menuPos.top, left: menuPos.left }}
                          >
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                setRenameValue(job.project_name || '')
                                setRenamingJobId(job.job_id)
                                setMenuJobId(null)
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-border-color/10 text-text-primary"
                            >
                              <Pencil className="w-3.5 h-3.5" /> 重命名
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handlePin(job.job_id)
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-border-color/10 text-text-primary"
                            >
                              {isPinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
                              {isPinned ? '取消置顶' : '置顶'}
                            </button>
                            <div className="border-t border-border-color/10 my-0.5" />
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDelete(job.job_id)
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-error/10 text-error"
                            >
                              <Trash2 className="w-3.5 h-3.5" /> 删除
                            </button>
                          </div>,
                          document.body
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            )}
          </div>
        </div>

        {/* ─── 底部按钮 ─── */}
        <div className={`pt-3 border-t border-border-color/10 flex flex-col gap-1 ${isSidebarCollapsed ? 'px-0.5' : ''}`}>
          <button
            onClick={() => setShowSkillMarket(true)}
            className={`flex items-center w-full rounded-lg text-text-secondary hover:text-text-primary hover:bg-border-color/10 transition-all ${isSidebarCollapsed ? 'justify-center p-2.5' : 'gap-2.5 px-3 py-2.5 text-sm'}`}
            title="ClawSkill 市场"
          >
            <div className="relative">
              <Puzzle className="w-4 h-4" />
              <Sparkles className="w-2 h-2 absolute -top-0.5 -right-0.5 text-accent" />
            </div>
            {!isSidebarCollapsed && '技能市场'}
          </button>
          <button
            onClick={() => setShowSettings(true)}
            className={`flex items-center w-full rounded-lg text-text-secondary hover:text-text-primary hover:bg-border-color/10 transition-all ${isSidebarCollapsed ? 'justify-center p-2.5' : 'gap-2.5 px-3 py-2.5 text-sm'}`}
            title="设置"
          >
            <Settings className="w-4 h-4" />
            {!isSidebarCollapsed && '设置'}
          </button>
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsModal open={showSettings} onClose={() => setShowSettings(false)} />

      {/* ClawSkill Market Modal */}
      <ClawSkillMarket open={showSkillMarket} onClose={() => setShowSkillMarket(false)} />
    </div>
  )
}
