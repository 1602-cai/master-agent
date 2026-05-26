import React, { useState } from 'react'
import { useAppStore } from '../store'
import { CheckCircle2, SplitSquareHorizontal, Loader2, ListChecks } from 'lucide-react'
import { confirmDesign } from '../api'

export default function ConfirmationCard({ confirmations }: { confirmations: string }) {
  const store = useAppStore()
  const { jobId } = store
  const [submitting, setSubmitting] = useState(false)
  const [confirmed, setConfirmed] = useState(false)

  const handleAction = async (action: 'confirm' | 'split') => {
    if (!jobId) return
    setSubmitting(true)
    try {
      // 往对话流中添加一条系统/用户确认消息
      store.addMessage({
        role: 'user',
        content: action === 'confirm' ? '✅ 我确认！直接开始生成幻灯片。' : '📦 开启 Split 暂停模式，请在 Phase A 完成后暂停。'
      })

      await confirmDesign(jobId, action)
      setConfirmed(true)
      store.setPhase('running')
    } catch (e: any) {
      store.addMessage({
        role: 'system',
        content: `❌ 操作提交失败: ${e.message}`
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-[#1a1b20] rounded-btn border border-accent/20 p-4 space-y-3 shadow-inner">
      <div className="flex items-center gap-2 text-xs font-bold text-accent">
        <ListChecks className="w-4 h-4" />
        AI 策略师设计的排版方案
      </div>

      {/* 方案内容 */}
      <div className="max-h-56 overflow-y-auto text-[11px] text-text-secondary whitespace-pre-wrap leading-relaxed bg-black/30 rounded p-3 select-text border border-border-color/10">
        {confirmations}
      </div>

      {/* 按钮群 */}
      <div className="flex gap-2 shrink-0 pt-1">
        <button
          onClick={() => handleAction('confirm')}
          disabled={submitting || confirmed}
          className="flex-1 py-2 bg-accent hover:bg-accent-light disabled:opacity-50 text-white text-[11px] font-bold rounded-btn transition-all flex items-center justify-center gap-1.5"
        >
          {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
          {confirmed ? '已确认' : '确认方案，直接生成'}
        </button>

        <button
          onClick={() => handleAction('split')}
          disabled={submitting || confirmed}
          className="py-2 px-3 bg-border-color/10 hover:bg-warning/20 hover:text-warning disabled:opacity-50 text-text-secondary text-[11px] rounded-btn transition-all flex items-center gap-1 border border-border-color/20"
          title="Split 模式：生成完大纲和图片后先暂停"
        >
          <SplitSquareHorizontal className="w-3.5 h-3.5" />
          分步执行
        </button>
      </div>
    </div>
  )
}
