import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { 
  Upload, 
  Sparkles, 
  FileText, 
  Loader2, 
  Trash2, 
  Plus,
  Monitor,
  Send,
  FileStack,
  ImagePlus
} from 'lucide-react'
import { useAppStore } from '../store'
import { uploadFile, startPipeline } from '../api'
import { formatFileSize } from '../lib/utils'

const CANVAS_OPTIONS = [
  { value: 'ppt169', label: '16:9', desc: '标准宽屏' },
  { value: 'ppt43', label: '4:3', desc: '传统投影' },
] as const

const PAGE_OPTIONS = [
  { value: '', label: '无限制' },
  { value: '5', label: '5页以内' },
  { value: '6-10', label: '6-10页' },
  { value: '11-15', label: '11-15页' },
  { value: '16-20', label: '16-20页' },
  { value: '20+', label: '20页以上' },
] as const

export default function IdleLayout() {
  const store = useAppStore()
  const [canvasFormat, setCanvasFormat] = useState<'ppt169' | 'ppt43'>('ppt169')
  const [pageCount, setPageCount] = useState('')
  const [showPageMenu, setShowPageMenu] = useState(false)
  const [loading, setLoading] = useState(false)
  const [enableImages, setEnableImages] = useState(false)
  const [error, setError] = useState('')

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      store.setFile(accepted[0])
      setError('')
    }
  }, [store])

  const { getRootProps, getInputProps, isDragActive, open: openFileDialog } = useDropzone({
    onDrop,
    noClick: true, // 禁用全局点击打开，我们通过专属的本地上传按钮打开
    multiple: false,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'text/html': ['.html'],
      'application/epub+zip': ['.epub'],
    },
  })

  const handleStart = async () => {
    if (!store.file && !store.inputText.trim()) {
      setError('请上传参考文件或输入您的 PPT 主题要求')
      return
    }
    setLoading(true)
    setError('')

    try {
      let fileId = ''
      let sourceFile = ''
      
      if (store.file) {
        const res = await uploadFile(store.file)
        fileId = res.file_id
        store.setFileId(fileId)
      }

      let userRequest = store.inputText.trim() || (store.file ? `请根据上传的文件制作一个专业的 PPT` : `请根据主题制作专业 PPT`)
      if (pageCount) {
        const pageLabel = PAGE_OPTIONS.find(o => o.value === pageCount)?.label || pageCount
        userRequest += `，页数要求: ${pageLabel}`
      }

      // 初始化消息流
      store.clearMessages()
      store.addMessage({
        role: 'user',
        content: userRequest + (store.file ? ` (已附带参考文件: \`${store.file.name}\`)` : '')
      })

      // 启动
      const res = await startPipeline({
        file_id: fileId || undefined,
        source_file: sourceFile || undefined,
        canvas_format: canvasFormat,
        auto_mode: false,
        enable_images: enableImages,
        user_request: userRequest,
      })

      store.setJobId(res.job_id)
      store.setCanvasFormat(canvasFormat)
      store.setPhase('running')
    } catch (e: any) {
      setError(e.message || '启动失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8 py-4">
      {/* 标题 */}
      <div className="text-center space-y-2">
        <h2 className="text-4xl font-bold text-text-primary tracking-tight flex items-center justify-center gap-2">
          <Sparkles className="w-8 h-8 text-accent animate-pulse" />
          PPT Master Agent
        </h2>
        <p className="text-text-secondary text-sm">
          一步开启高效任务处理新体验 · AI 原生 DrawingML 高品质排版
        </p>
      </div>

      {/* ─── 主输入对话大卡片 (融合拖拽上传 + 输入文本 + 技能胶囊) ─── */}
      <div 
        {...getRootProps()}
        className={`
          relative bg-card-bg rounded-2xl border p-4 space-y-3 shadow-xl transition-all duration-300
          ${isDragActive ? 'border-accent bg-accent/5 ring-2 ring-accent/20' : 'border-border-color/20 hover:border-border-color/30'}
        `}
      >
        <input {...getInputProps()} />

        {/* 拖入文件时的浮层遮罩 */}
        {isDragActive && (
          <div className="absolute inset-0 bg-accent/10 backdrop-blur-sm rounded-2xl flex flex-col items-center justify-center gap-3 text-accent pointer-events-none z-30">
            <Upload className="w-12 h-12 animate-bounce" />
            <span className="font-bold text-base">松开鼠标，直接上传参考文件</span>
            <span className="text-xs opacity-80">支持 PDF/DOCX/XLSX/PPTX 格式</span>
          </div>
        )}

        {/* 顶部标签 */}
        <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-wider">
          <Sparkles className="w-3.5 h-3.5" />
          全能助手 PPT 模式
        </div>
        
        {/* 输入框核心区 */}
        <div className="space-y-3">
          {/* 上传的文件 Badge 胶囊列表 */}
          {store.file && (
            <div className="flex items-center gap-2 bg-success/10 border border-success/20 text-success rounded-lg py-1.5 px-3 w-fit text-xs animate-fadeIn">
              <FileText className="w-3.5 h-3.5 shrink-0" />
              <span className="font-medium truncate max-w-sm">{store.file.name}</span>
              <span className="opacity-70">({formatFileSize(store.file.size)})</span>
              <button 
                onClick={(e) => { e.stopPropagation(); store.setFile(null) }}
                className="hover:bg-success/20 p-1 rounded-full ml-1 transition-all"
                title="移除文件"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}


          {/* 文本输入框 */}
          <textarea
            value={store.inputText}
            onChange={(e) => { store.setInputText(e.target.value); setError('') }}
            placeholder="试试安排任务，例如：'做一份关于商业银行并购管理的报告，要求内容翔实、10页左右'。或者直接把 PDF/PPTX/Word 资料拖到这里！"
            rows={3}
            className="w-full bg-transparent border-0 resize-none text-sm text-text-primary placeholder:text-text-secondary/30 outline-none focus:ring-0 leading-relaxed"
          />
        </div>

        {/* 底部工具栏 */}
        <div className="flex items-center justify-between border-t border-border-color/10 pt-3 shrink-0">
          <div className="flex items-center gap-1.5">
            {/* 本地上传胶囊按钮 */}
            <button
              onClick={openFileDialog}
              className="flex items-center gap-1 bg-border-color/5 hover:bg-border-color/10 text-text-secondary hover:text-text-primary rounded-lg py-1.5 px-3 text-xs transition-all border border-border-color/5 font-medium"
              title="本地上传文件"
            >
              <Plus className="w-3.5 h-3.5" />
              本地上传
            </button>

            {/* 页数选择 */}
            <div className="relative">
              <button
                onClick={() => setShowPageMenu(!showPageMenu)}
                className={`flex items-center gap-1 rounded-lg py-1.5 px-3 text-xs transition-all border font-medium ${
                  pageCount 
                    ? 'bg-accent/10 text-accent border-accent/20' 
                    : 'bg-border-color/5 hover:bg-border-color/10 text-text-secondary hover:text-text-primary border-border-color/5'
                }`}
              >
                <FileStack className="w-3.5 h-3.5" />
                {pageCount ? PAGE_OPTIONS.find(o => o.value === pageCount)?.label : '无限制'}
              </button>
              {showPageMenu && (
                <div className="absolute bottom-full left-0 mb-2 bg-card-bg border border-border-color/20 rounded-xl shadow-xl py-1.5 min-w-[140px] z-50 animate-slideDown">
                  {PAGE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => { setPageCount(opt.value); setShowPageMenu(false) }}
                      className={`w-full text-left px-4 py-2 text-xs transition-all flex items-center justify-between ${
                        pageCount === opt.value
                          ? 'text-accent bg-accent/5 font-medium'
                          : 'text-text-secondary hover:text-text-primary hover:bg-border-color/5'
                      }`}
                    >
                      {opt.label}
                      {pageCount === opt.value && <span className="text-accent">✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 画布格式选择 */}
            <div className="relative">
              <button
                onClick={() => setCanvasFormat(canvasFormat === 'ppt169' ? 'ppt43' : 'ppt169')}
                className="flex items-center gap-1 bg-border-color/5 hover:bg-border-color/10 text-text-secondary hover:text-text-primary rounded-lg py-1.5 px-3 text-xs transition-all border border-border-color/5 font-medium"
                title="切换画布格式"
              >
                <Monitor className="w-3.5 h-3.5" />
                {CANVAS_OPTIONS.find(o => o.value === canvasFormat)?.label}
              </button>
            </div>

            {/* AI 图片生成开关 */}
            <button
              onClick={() => setEnableImages(!enableImages)}
              className={`flex items-center gap-1 rounded-lg py-1.5 px-3 text-xs transition-all border font-medium ${
                enableImages
                  ? 'bg-accent/10 text-accent border-accent/20'
                  : 'bg-border-color/5 hover:bg-border-color/10 text-text-secondary hover:text-text-primary border-border-color/5'
              }`}
              title="AI 图片生成（较慢）"
            >
              <ImagePlus className="w-3.5 h-3.5" />
              {enableImages ? 'AI 配图' : '无配图'}
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-text-secondary/40 hidden sm:inline">
              Ctrl + Enter
            </span>
            {/* 发送按钮 */}
            <button
              onClick={handleStart}
              disabled={loading || (!store.file && !store.inputText.trim())}
              className={`w-9 h-9 flex items-center justify-center rounded-full transition-all hover:scale-105 active:scale-95 ${
                (store.file || store.inputText.trim()) && !loading
                  ? 'bg-accent hover:bg-accent-light text-white shadow-md shadow-accent/20'
                  : 'bg-border-color/20 text-text-secondary/40 cursor-not-allowed'
              }`}
              title="启动生成"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <p className="text-error text-xs text-center font-medium bg-error/10 py-2 rounded-xl border border-error/20">
          ⚠️ {error}
        </p>
      )}

    </div>
  )
}
