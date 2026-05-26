import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store'
import MessageBubble from './MessageBubble'
import { Send, Loader2, Square } from 'lucide-react'
import { confirmDesign, cancelJob } from '../api'

export default function ChatMessages() {
  const store = useAppStore()
  const { messages, phase, jobId } = store
  const containerRef = useRef<HTMLDivElement>(null)
  const [feedback, setFeedback] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  // 消息自动滚动到最底部
  useEffect(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth'
    })
  }, [messages])

  const handleSendFeedback = async () => {
    if (!feedback.trim() || !jobId) return
    setSubmitting(true)
    try {
      store.addMessage({
        role: 'user',
        content: feedback.trim()
      })
      const reply = feedback.trim()
      setFeedback('')

      await confirmDesign(jobId, 'modify', reply)
      store.setPhase('running')
    } catch (e: any) {
      store.addMessage({
        role: 'system',
        content: `❌ 反馈提交失败: ${e.message}`
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = async () => {
    if (!jobId || cancelling) return
    setCancelling(true)
    try {
      await cancelJob(jobId)
      store.addMessage({
        role: 'system',
        content: '⏹ 任务已中断'
      })
      store.setPhase('error')
    } catch (e: any) {
      store.addMessage({
        role: 'system',
        content: `❌ 中断失败: ${e.message}`
      })
    } finally {
      setCancelling(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendFeedback()
    }
  }

  const isRunning = phase === 'running'
  const canSend = phase === 'confirming'
  const showInput = isRunning || canSend

  return (
    <div className="flex-1 flex flex-col overflow-hidden h-full relative">
      {/* 消息区域 */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-5 py-6 space-y-5"
      >
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
      </div>

      {/* 底部交互区 */}
      <div className="p-4 border-t border-border-color/10 shrink-0 bg-card-bg/40">
        {showInput ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 bg-app-bg border border-border-color/20 rounded-btn px-3 py-2">
              {isRunning && (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-accent shrink-0" />
              )}
              <input
                type="text"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                onKeyDown={handleKeyPress}
                disabled={submitting || isRunning}
                placeholder={
                  isRunning
                    ? 'AI 正在处理中...'
                    : '输入修改意见，或点上方确认按钮...'
                }
                className="flex-1 bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary/40"
              />
              {isRunning ? (
                <button
                  onClick={handleCancel}
                  disabled={cancelling}
                  title="中断任务"
                  className="w-7 h-7 flex items-center justify-center bg-error/90 text-white rounded hover:bg-error disabled:opacity-40 transition-all shrink-0"
                >
                  {cancelling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3 h-3" />}
                </button>
              ) : (
                <button
                  onClick={handleSendFeedback}
                  disabled={submitting || !feedback.trim()}
                  className="w-7 h-7 flex items-center justify-center bg-accent text-white rounded hover:bg-accent-light disabled:opacity-40 transition-all shrink-0"
                >
                  {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>
            <p className="text-[10px] text-text-secondary/50 text-center">
              {isRunning ? '点击 ■ 可中断当前任务' : '按 Enter 发送修改意见'}
            </p>
          </div>
        ) : (
          <div className="flex items-center justify-center py-2 text-xs text-text-secondary/50 gap-2">
            {phase === 'done' && (
              <span>✨ 任务已完成，恭喜你已成功生成精致演示幻灯片！</span>
            )}
            {phase === 'error' && (
              <span>任务已结束，可以新建任务重试</span>
            )}
            {phase === 'idle' && (
              <span>选择模板和素材，开始创建 PPT</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
