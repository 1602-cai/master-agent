import React from 'react'
import { ChatMessage, useAppStore } from '../store'
import { Sparkles, User, ShieldAlert } from 'lucide-react'
import OutlineCard from './OutlineCard'
import ConfirmationCard from './ConfirmationCard'
import ResultActions from './ResultActions'

export default function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isAi = msg.role === 'ai'
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  if (isSystem) {
    return (
      <div className="flex justify-center text-[10px] text-text-secondary/50 uppercase tracking-widest font-mono">
        — {msg.content} —
      </div>
    )
  }

  return (
    <div className={`flex gap-3 max-w-[90%] ${isUser ? 'ml-auto flex-row-reverse' : ''}`}>
      {/* 头像 */}
      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center font-bold text-xs
        ${isAi ? 'bg-accent text-white' : 'bg-chat-user-bg border border-border-color/20 text-text-secondary'}
      `}>
        {isAi ? <Sparkles className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
      </div>

      {/* 气泡体 */}
      <div className="space-y-1">
        {/* 名称与时间 */}
        <div className={`flex items-center gap-1.5 text-[10px] text-text-secondary/60 ${isUser ? 'justify-end' : ''}`}>
          <span className="font-bold">{isAi ? 'SkyClaw' : '我'}</span>
          {isAi && <span className="bg-accent/10 text-accent scale-90 px-1 rounded text-[8px] font-black">智选模型</span>}
          <span>·</span>
          <span>{new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}</span>
        </div>

        {/* 内容 */}
        <div className={`rounded-card px-4 py-3 text-xs leading-relaxed border shadow-sm
          ${isUser 
            ? 'bg-chat-user-bg text-text-primary border-border-color/10 rounded-tr-none' 
            : 'bg-card-bg text-text-primary border-border-color/20 rounded-tl-none'}
        `}>
          {/* 纯文本渲染 */}
          <p className="whitespace-pre-wrap select-text">{msg.content}</p>

          {/* 条件渲染 1: 八项确认卡片 */}
          {msg.eightConfirmations && (
            <div className="mt-3">
              <ConfirmationCard confirmations={msg.eightConfirmations} />
            </div>
          )}

          {/* 条件渲染 2: 幻灯片大纲时间线 */}
          {msg.isOutline && (
            <div className="mt-3">
              <OutlineCard />
            </div>
          )}

          {/* 条件渲染 3: 后续下载和操作面板 */}
          {msg.isResultActions && (
            <div className="mt-3">
              <ResultActions />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
