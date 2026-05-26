import React, { useEffect, useState } from 'react'
import { useAppStore } from '../store'
import { Loader2, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react'
import { formatDuration } from '../lib/utils'

export default function StatusBar() {
  const store = useAppStore()
  const [elapsed, setElapsed] = useState(0)

  // 耗时秒数计时器
  useEffect(() => {
    let timer: any = null
    if (store.phase === 'running' || store.phase === 'confirming') {
      const start = Date.now()
      timer = setInterval(() => {
        setElapsed(Math.floor((Date.now() - start)))
      }, 1000)
    }
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [store.phase])

  const statusColor = {
    idle: 'bg-border-color/20 text-text-secondary',
    running: 'bg-accent/10 border-accent/20 text-accent',
    confirming: 'bg-warning/10 border-warning/20 text-warning',
    done: 'bg-success/10 border-success/20 text-success',
    error: 'bg-error/10 border-error/20 text-error',
  }

  const icon = () => {
    switch (store.phase) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-accent" />
      case 'confirming':
        return <AlertCircle className="w-4 h-4 text-warning" />
      case 'done':
        return <CheckCircle2 className="w-4 h-4 text-success" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-error" />
      default:
        return null
    }
  }

  const phaseText = () => {
    switch (store.phase) {
      case 'running':
        return `任务运行中 · 步骤 ${store.currentStep}/7: ${store.currentStepName || '正在处理'}`
      case 'confirming':
        return `等待确认 · 请在左侧对话框中回复八项确认`
      case 'done':
        return `生成完成 · 共 ${store.totalPages || store.svgPages.length} 页 · 耗时 ${formatDuration(store.durationMs || elapsed)}`
      case 'error':
        return `生成失败 · 错误: ${store.errorMessage}`
      default:
        return '空闲'
    }
  }

  return (
    <div className={`h-11 border-t border-border-color/10 px-6 flex items-center justify-between text-xs font-medium shrink-0 bg-card-bg/60 backdrop-blur z-40 ${statusColor[store.phase]}`}>
      <div className="flex items-center gap-2.5">
        {icon()}
        <span className="text-text-primary">{phaseText()}</span>
        {(store.phase === 'running' || store.phase === 'confirming') && (
          <span className="text-text-secondary font-mono">
            (已耗时: {formatDuration(elapsed)})
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {store.phase === 'done' && (
          <button
            onClick={() => store.reset()}
            className="flex items-center gap-1 text-[11px] bg-accent/20 hover:bg-accent/30 text-text-primary px-2.5 py-1 rounded transition-all"
          >
            <RefreshCw className="w-3 h-3" /> 新建项目
          </button>
        )}
      </div>
    </div>
  )
}
