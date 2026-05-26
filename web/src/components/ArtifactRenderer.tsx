import React from 'react'
import LiveSvgPreview from './LiveSvgPreview'

/**
 * Plugin-based artifact renderer.
 * Routes to the correct preview component based on the skill's declared ui_type.
 * This enables the platform to support multiple skills with different output types.
 */

interface ArtifactRendererProps {
  uiType: string
}

function DefaultMarkdownView() {
  return (
    <div className="flex items-center justify-center h-full text-text-secondary text-sm">
      <div className="text-center space-y-2">
        <div className="text-4xl">📄</div>
        <p>Markdown 文档预览</p>
        <p className="text-xs opacity-60">此 Skill 产出 Markdown 内容</p>
      </div>
    </div>
  )
}

function CodeEditorView() {
  return (
    <div className="flex items-center justify-center h-full text-text-secondary text-sm">
      <div className="text-center space-y-2">
        <div className="text-4xl">💻</div>
        <p>代码编辑器</p>
        <p className="text-xs opacity-60">此 Skill 产出代码文件</p>
      </div>
    </div>
  )
}

function DataTableView() {
  return (
    <div className="flex items-center justify-center h-full text-text-secondary text-sm">
      <div className="text-center space-y-2">
        <div className="text-4xl">📊</div>
        <p>数据透视表</p>
        <p className="text-xs opacity-60">此 Skill 产出数据表格与图表</p>
      </div>
    </div>
  )
}

export default function ArtifactRenderer({ uiType }: ArtifactRendererProps) {
  switch (uiType) {
    case 'svg_slides':
      return <LiveSvgPreview />
    case 'code_editor':
      return <CodeEditorView />
    case 'interactive_table':
      return <DataTableView />
    case 'markdown':
      return <DefaultMarkdownView />
    default:
      return <LiveSvgPreview />
  }
}
