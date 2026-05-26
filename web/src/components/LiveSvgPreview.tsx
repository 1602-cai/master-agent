import React from 'react'
import { useAppStore } from '../store'
import { ChevronLeft, ChevronRight, Eye, Layers, Loader2, Sparkles } from 'lucide-react'

// Rewrite all id="..." attributes and url(#...)/href="#..." references in an
// SVG so each rendering of a page uses a unique id namespace. Inlining multiple
// SVGs with shared ids (e.g. `bgGrad`, `lineGrad`) into the same document causes
// gradient/pattern refs to resolve to whichever defs block appears first, making
// every thumbnail render with the same colors as page 1.
function namespaceSvgIds(svgContent: string, scope: string): string {
  const ids = new Set<string>()
  const idRegex = /\sid="([^"]+)"/g
  let m: RegExpExecArray | null
  while ((m = idRegex.exec(svgContent)) !== null) {
    ids.add(m[1])
  }
  if (ids.size === 0) return svgContent
  let out = svgContent
  for (const oldId of ids) {
    const safe = oldId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const newId = `${scope}__${oldId}`
    out = out
      .replace(new RegExp(`(\\sid=")${safe}(")`, 'g'), `$1${newId}$2`)
      .replace(new RegExp(`url\\(#${safe}\\)`, 'g'), `url(#${newId})`)
      .replace(new RegExp(`((?:xlink:)?href=")#${safe}(")`, 'g'), `$1#${newId}$2`)
  }
  return out
}

// 让 SVG 自适应容器：去掉固定 width/height，保留 viewBox
function makeResponsiveSvg(svgContent: string, scope?: string): string {
  // Remove fixed width/height, add responsive style preserving aspect ratio
  let cleaned = sanitizeSvgContent(svgContent)
    .replace(/<svg([^>]*)\swidth=["'][^"']*["']/g, '<svg$1')
    .replace(/<svg([^>]*)\sheight=["'][^"']*["']/g, '<svg$1')
  if (scope) cleaned = namespaceSvgIds(cleaned, scope)
  // Inject responsive style on <svg> tag
  cleaned = cleaned.replace(
    /<svg([^>]*)>/,
    '<svg$1 style="width:100%;height:auto;display:block">'
  )
  return cleaned
}

function sanitizeSvgContent(svgContent: string): string {
  return svgContent
    .replace(/<\s*script\b[^>]*>.*?<\s*\/\s*script\s*>/gis, '')
    .replace(/<\s*foreignObject\b[^>]*>.*?<\s*\/\s*foreignObject\s*>/gis, '')
    .replace(/\s+on[a-zA-Z]+\s*=\s*(['"]).*?\1/gis, '')
    .replace(/\s+(?:href|xlink:href)\s*=\s*(['"])(?:javascript:|data:text\/html|https?:\/\/)[^'"]*\1/gi, '')
    .replace(/url\(\s*(['"]?)(?:javascript:|https?:\/\/)[^)]+\1\s*\)/gi, 'none')
}

export default function LiveSvgPreview() {
  const store = useAppStore()
  const { svgPages, currentPreviewPage, outline, phase } = store

  const currentPageData = svgPages.find((p) => p.page === currentPreviewPage)

  const handlePrev = () => {
    if (currentPreviewPage > 1) {
      store.setCurrentPreviewPage(currentPreviewPage - 1)
    }
  }

  const handleNext = () => {
    if (currentPreviewPage < svgPages.length) {
      store.setCurrentPreviewPage(currentPreviewPage + 1)
    }
  }

  // 大图渲染加载状态
  if (svgPages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-text-secondary gap-4 p-8">
        {phase === 'running' ? (
          <>
            <Loader2 className="w-10 h-10 animate-spin text-accent" />
            <div className="text-center space-y-1 animate-pulse">
              <p className="text-sm font-semibold text-text-primary">正在构思和编写第一页幻灯片...</p>
              <p className="text-[11px] text-text-secondary">AI Executor 正在全力以赴渲染原生 SVG 代码</p>
            </div>
          </>
        ) : (
          <>
            <Layers className="w-10 h-10 text-border-color/30" />
            <p className="text-xs">等待设计阶段完成，实时 SVG 画布即可点亮</p>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden p-6 gap-5">
      {/* 顶部标题栏 */}
      <div className="flex justify-between items-center shrink-0">
        <div className="space-y-0.5">
          <h4 className="text-xs font-bold text-text-secondary uppercase tracking-widest flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            实时原生 SVG 渲染画布
          </h4>
          <p className="text-[11px] text-text-secondary/70">
            {currentPageData?.filename || `page_${currentPreviewPage.toString().padStart(2, '0')}.svg`}
          </p>
        </div>

        <div className="flex items-center gap-1.5 bg-card-bg/80 border border-border-color/10 rounded-btn p-1 text-xs">
          <button
            onClick={handlePrev}
            disabled={currentPreviewPage === 1}
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-border-color/20 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="px-2 font-mono font-bold">
            {currentPreviewPage} / {Math.max(svgPages.length, store.totalPlannedPages)}
          </span>
          <button
            onClick={handleNext}
            disabled={currentPreviewPage === svgPages.length}
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-border-color/20 disabled:opacity-30"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* SVG 大画布 */}
      <div className="flex-1 bg-transparent rounded-card overflow-hidden border border-border-color/10 shadow-inner flex items-center justify-center relative group min-h-0">
        {currentPageData?.svgContent ? (
          <div
            className="w-full max-h-full flex items-center justify-center p-2"
            dangerouslySetInnerHTML={{ __html: makeResponsiveSvg(currentPageData.svgContent, `main_p${currentPreviewPage}`) }}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <p className="text-xs">第 {currentPreviewPage} 页正在排版生成中...</p>
          </div>
        )}
      </div>

      {/* 底部缩略图条 */}
      <div className="shrink-0 space-y-2">
        <h5 className="text-[10px] font-bold text-text-secondary/60 uppercase tracking-wider">
          幻灯片缩略图序列 ({svgPages.length} 页已点亮)
        </h5>
        <div className="flex gap-2.5 overflow-x-auto pb-2 scrollbar-thin">
          {Array.from({ length: Math.max(svgPages.length, store.totalPlannedPages) }).map((_, idx) => {
            const pageNum = idx + 1
            const pData = svgPages.find((p) => p.page === pageNum)
            const isSelected = currentPreviewPage === pageNum

            return (
              <button
                key={pageNum}
                onClick={() => {
                  if (pData) store.setCurrentPreviewPage(pageNum)
                }}
                disabled={!pData}
                className={`
                  relative shrink-0 w-24 aspect-video rounded border overflow-hidden transition-all bg-[#0d0e12]
                  ${isSelected ? 'border-accent ring-2 ring-accent/20' : 'border-border-color/10'}
                  ${!pData ? 'opacity-30 cursor-not-allowed' : 'hover:border-accent/40'}
                `}
              >
                {pData?.svgContent ? (
                  <div
                    className="w-full h-full pointer-events-none overflow-hidden"
                    dangerouslySetInnerHTML={{ __html: makeResponsiveSvg(pData.svgContent, `thumb_p${pageNum}`) }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[10px] font-mono font-bold text-text-secondary/40">
                    P{pageNum}
                  </div>
                )}
                {/* 页码徽章 */}
                <div className="absolute bottom-1 right-1 bg-black/60 text-white text-[9px] px-1 rounded font-mono font-black scale-90">
                  P{pageNum}
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
