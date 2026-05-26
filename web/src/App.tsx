import React, { useEffect, useRef } from 'react'
import { useAppStore } from './store'
import { connectWebSocket } from './ws'
import Sidebar from './components/Sidebar'
import IdleLayout from './layouts/IdleLayout'
import WorkLayout from './layouts/WorkLayout'

function App() {
  const store = useAppStore()
  const restoredRef = useRef(false)

  // 刷新页面后自动恢复上次的活跃项目
  useEffect(() => {
    if (restoredRef.current) return
    restoredRef.current = true
    const savedJobId = localStorage.getItem('ppt_active_job')
    if (savedJobId && store.phase === 'idle' && !store.jobId) {
      store.loadJobState(savedJobId).then(() => {
        connectWebSocket(savedJobId)
      }).catch(() => {})
    }
  }, [])

  // 当 phase 为 running 时，轮询后端状态作为 WS 掉线的兜底
  useEffect(() => {
    if (store.phase !== 'running' || !store.jobId) return
    let failCount = 0
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${store.jobId}`)
        if (!res.ok) {
          failCount++
          // 后端不认识这个 job（可能重启了），如果已有 SVG 就视为完成
          if (failCount >= 3) {
            const s = useAppStore.getState()
            if (s.svgPages.length > 0) {
              s.setPipelineResult({
                pptxUrl: `/api/download/${s.jobId}`,
                pptxSize: 0,
                totalPages: s.svgPages.length,
                durationMs: 0,
              })
              s.addMessage({ role: 'ai', content: `🎉 **PPT 已生成完成。**（后端已重启，从缓存恢复）`, isResultActions: true })
            } else {
              s.setError('后端已重启，任务状态丢失。请重新开始。')
            }
          }
          return
        }
        failCount = 0
        const data = await res.json()
        if (data.status === 'completed' && data.result) {
          store.setPipelineResult({
            pptxUrl: `/api/download/${store.jobId}`,
            pptxSize: data.result.pptx_size || 0,
            totalPages: data.result.total_pages || store.svgPages.length,
            durationMs: data.result.duration_ms || 0,
          })
          store.addMessage({
            role: 'ai',
            content: `🎉 **PPT 生成完成！** 共 ${data.result.total_pages || store.svgPages.length} 页。`,
            isResultActions: true,
          })
        } else if (data.status === 'failed') {
          store.setError(data.error || '任务执行失败')
        }
      } catch {}
    }, 5000)
    return () => clearInterval(poll)
  }, [store.phase, store.jobId])

  return (
    <div className="flex h-screen bg-app-bg text-text-primary overflow-hidden">
      {/* 1. 左侧双栏导轨 & 侧边栏 */}
      <Sidebar />
      
      {/* 2. 右侧主工作区 */}
      <main className="flex-1 overflow-hidden relative flex flex-col h-full">
        {store.phase === 'idle' ? (
          <div className="flex-1 overflow-y-auto px-8 py-10">
            <IdleLayout />
          </div>
        ) : (
          <WorkLayout />
        )}
      </main>
    </div>
  )
}

export default App
