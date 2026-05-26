import React, { useEffect } from 'react'
import { useAppStore } from '../store'
import { connectWebSocket, disconnectWebSocket } from '../ws'
import ChatMessages from '../components/ChatMessages'
import ArtifactRenderer from '../components/ArtifactRenderer'
import StatusBar from '../components/StatusBar'

export default function WorkLayout() {
  const store = useAppStore()

  // 挂载时连接 WS 保持长连接进度推送
  useEffect(() => {
    if (store.jobId) {
      connectWebSocket(store.jobId)
    }
    return () => {
      disconnectWebSocket()
    }
  }, [store.jobId])

  return (
    <div className="flex flex-col h-full relative overflow-hidden">
      {/* 双栏容器 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左栏: 40% 宽，负责对话框 */}
        <div className="w-[40%] border-r border-border-color/20 flex flex-col bg-[#16171a] overflow-hidden">
          <ChatMessages />
        </div>

        {/* 右栏: 60% 宽，Plugin-based 产物预览 (由 Skill 元数据决定渲染器) */}
        <div className="w-[60%] flex flex-col bg-app-bg overflow-hidden relative">
          <ArtifactRenderer uiType={store.skillUiType} />
        </div>
      </div>

      {/* 底部固定全局状态栏 */}
      <StatusBar />
    </div>
  )
}
