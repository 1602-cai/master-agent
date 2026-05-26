import React, { useState } from 'react'
import { useAppStore } from '../store'
import { Download, FileText, RotateCcw, FileSpreadsheet } from 'lucide-react'
import { getNotes } from '../api'

export default function ResultActions() {
  const store = useAppStore()
  const { pptxUrl, totalPages, durationMs, pptxSize, notes, jobId } = store
  const [showNotes, setShowNotes] = useState(false)
  const [notesData, setNotesData] = useState<Record<string, string>>(notes)
  const [loadingNotes, setLoadingNotes] = useState(false)

  const handleDownload = async () => {
    if (!pptxUrl) return
    try {
      const res = await fetch(pptxUrl)
      if (!res.ok) {
        alert('PPTX 文件尚未就绪，请稍后重试')
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const disposition = res.headers.get('content-disposition') || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      a.download = match ? match[1] : `presentation_${jobId}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('下载失败，请重试')
    }
  }

  const toggleNotes = async () => {
    if (showNotes) {
      setShowNotes(false)
      return
    }

    if (Object.keys(notesData).length > 0) {
      setShowNotes(true)
      return
    }

    if (!jobId) return
    setLoadingNotes(true)
    try {
      const data = await getNotes(jobId)
      setNotesData(data.notes || {})
      store.setNotes(data.notes || {})
      setShowNotes(true)
    } catch (e) {
      console.error('Failed to fetch notes:', e)
    } finally {
      setLoadingNotes(false)
    }
  }

  return (
    <div className="space-y-3 bg-[#1a1b20] rounded-btn border border-success/20 p-4 shadow-inner">
      <div className="flex items-center gap-2 text-xs font-bold text-success">
        <FileSpreadsheet className="w-4 h-4" />
        幻灯片资产打包完成
      </div>

      {/* 操作按钮组 */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={handleDownload}
          className="flex-1 min-w-[120px] py-2.5 bg-success hover:bg-success/80 text-white text-[11px] font-bold rounded-btn transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-success/15"
        >
          <Download className="w-3.5 h-3.5" />
          下载 PPTX 文件
        </button>

        <button
          onClick={toggleNotes}
          disabled={loadingNotes}
          className="py-2.5 px-3 bg-border-color/10 hover:bg-accent/10 hover:text-accent border border-border-color/20 text-text-secondary text-[11px] rounded-btn transition-all flex items-center gap-1"
        >
          <FileText className="w-3.5 h-3.5" />
          {loadingNotes ? '加载中...' : showNotes ? '收起演讲稿' : '获取旁白稿'}
        </button>

        <button
          onClick={() => store.reset()}
          className="py-2.5 px-3 bg-border-color/10 hover:bg-error/10 hover:text-error border border-border-color/20 text-text-secondary text-[11px] rounded-btn transition-all flex items-center gap-1"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          重新生成
        </button>
      </div>

      {/* 演讲稿展示 */}
      {showNotes && (
        <div className="mt-3 bg-black/40 rounded p-3 text-[11px] text-text-secondary/90 max-h-52 overflow-y-auto leading-relaxed border border-border-color/10 select-text">
          {notesData._total ? (
            <div className="whitespace-pre-wrap">{notesData._total}</div>
          ) : (
            Object.entries(notesData)
              .filter(([k]) => k !== '_total')
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, content]) => (
                <div key={key} className="space-y-1 border-b border-border-color/5 pb-2 mb-2 last:border-0 last:pb-0 last:mb-0">
                  <h6 className="font-bold text-accent font-mono">{key} · 演讲旁白：</h6>
                  <p className="whitespace-pre-wrap">{content}</p>
                </div>
              ))
          )}
        </div>
      )}
    </div>
  )
}
