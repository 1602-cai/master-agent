import React from 'react'
import { useAppStore } from '../store'
import { CheckCircle, Circle, PlayCircle, Eye, AlignLeft } from 'lucide-react'

export default function OutlineCard() {
  const store = useAppStore()
  const { outline, currentPreviewPage, svgPages } = store

  const handlePageClick = (page: number) => {
    // 只有生成了该页 SVG 时才能切换展示
    const hasSvg = svgPages.some((p) => p.page === page)
    if (hasSvg) {
      store.setCurrentPreviewPage(page)
    }
  }

  return (
    <div className="bg-[#1a1b20] rounded-btn border border-border-color/10 p-4 space-y-3 shadow-inner">
      <div className="flex items-center gap-2 text-xs font-bold text-accent">
        <AlignLeft className="w-4 h-4" />
        PPT 大纲与内容结构
      </div>

      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
        {outline.map((item, idx) => {
          const hasSvg = svgPages.some((p) => p.page === item.page)
          const isSelected = currentPreviewPage === item.page
          
          let icon = <Circle className="w-4 h-4 text-border-color/30 shrink-0" />
          if (item.status === 'completed' || hasSvg) {
            icon = <CheckCircle className="w-4 h-4 text-success shrink-0 fill-success/10" />
          } else if (item.status === 'generating') {
            icon = <PlayCircle className="w-4 h-4 text-accent animate-pulse shrink-0 fill-accent/10" />
          }

          return (
            <div
              key={`${item.page}-${idx}`}
              onClick={() => handlePageClick(item.page)}
              className={`
                flex items-start gap-2.5 p-2 rounded transition-all group
                ${hasSvg ? 'cursor-pointer hover:bg-border-color/10' : 'opacity-60'}
                ${isSelected ? 'bg-border-color/10 border-l-2 border-accent pl-1.5' : ''}
              `}
            >
              {icon}

              <div className="flex-1 space-y-0.5 min-w-0">
                <div className="flex justify-between items-center gap-1">
                  <span className="text-xs font-bold text-text-primary truncate">
                    P{item.page.toString().padStart(2, '0')} · {item.title}
                  </span>
                  {hasSvg && (
                    <span className="text-[9px] text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5 shrink-0 bg-accent/10 text-accent px-1 rounded">
                      <Eye className="w-2.5 h-3.5" /> 预览
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-text-secondary/80 truncate select-text">
                  {item.summary}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
