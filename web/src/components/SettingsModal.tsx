import React, { useEffect, useState } from 'react'
import { X, Eye, EyeOff, Check, AlertCircle, Loader2 } from 'lucide-react'
import { getLLMSettings, updateLLMSettings, type LLMSettings, type LLMProviderInfo } from '../api'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SettingsModal({ open, onClose }: Props) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [providers, setProviders] = useState<Record<string, LLMProviderInfo>>({})
  const [providerKeyStatus, setProviderKeyStatus] = useState<Record<string, boolean>>({})
  const [provider, setProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiKeyPreview, setApiKeyPreview] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [keyChanged, setKeyChanged] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError('')
    setSuccess('')
    setKeyChanged(false)
    setApiKey('')
    getLLMSettings()
      .then((data: any) => {
        setProviders(data.providers)
        setProviderKeyStatus(data.provider_key_status || {})
        setProvider(data.provider)
        setBaseUrl(data.base_url)
        setModel(data.model)
        setApiKeyPreview(data.api_key_preview)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [open])

  // When provider changes, update base_url, model, and load saved key
  const handleProviderChange = async (pid: string) => {
    setProvider(pid)
    const p = providers[pid]
    if (p) {
      if (p.base_url) setBaseUrl(p.base_url)
      if (p.models.length > 0) setModel(p.models[0])
    }
    setError('')
    setSuccess('')
    setKeyChanged(false)
    setApiKey('')
    // Fetch saved key preview for this provider
    try {
      const res = await fetch(`/api/settings/llm/key/${pid}`)
      if (res.ok) {
        const data = await res.json()
        setApiKeyPreview(data.api_key_preview || '')
      } else {
        setApiKeyPreview('')
      }
    } catch {
      setApiKeyPreview('')
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const params: any = { provider, base_url: baseUrl, model }
      if (keyChanged && apiKey) {
        params.api_key = apiKey
      }
      await updateLLMSettings(params)
      setSuccess('配置已保存并生效')
      setKeyChanged(false)
      setApiKey('')
      // Refresh preview and key status
      const data: any = await getLLMSettings()
      setApiKeyPreview(data.api_key_preview)
      setProviderKeyStatus(data.provider_key_status || {})
    } catch (e: any) {
      setError(e.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const currentModels = providers[provider]?.models || []

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-card-bg border border-border-color/20 rounded-2xl shadow-2xl w-[480px] max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-color/10">
          <h2 className="text-base font-semibold text-text-primary">设置</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-border-color/10 text-text-secondary hover:text-text-primary transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
          </div>
        ) : (
          <div className="px-6 py-5 space-y-5">
            {/* Section: LLM Provider */}
            <div>
              <h3 className="text-sm font-medium text-text-primary mb-3">大模型配置</h3>

              {/* Provider Selection */}
              <label className="block text-xs text-text-secondary mb-1.5">提供商</label>
              <div className="grid grid-cols-3 gap-2 mb-4">
                {Object.entries(providers).map(([pid, pinfo]) => (
                  <button
                    key={pid}
                    onClick={() => handleProviderChange(pid)}
                    className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all relative ${
                      provider === pid
                        ? 'bg-accent/10 border-accent/30 text-accent'
                        : 'bg-sub-bg border-border-color/10 text-text-secondary hover:border-border-color/30 hover:text-text-primary'
                    }`}
                  >
                    {pinfo.name}
                    {providerKeyStatus[pid] && (
                      <span className="absolute -top-1 -right-1 w-2 h-2 bg-success rounded-full" title="已保存 Key" />
                    )}
                  </button>
                ))}
              </div>

              {/* API Key */}
              <label className="block text-xs text-text-secondary mb-1.5">API Key</label>
              <div className="relative mb-4">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={keyChanged ? apiKey : apiKeyPreview}
                  onChange={(e) => {
                    setApiKey(e.target.value)
                    setKeyChanged(true)
                  }}
                  onFocus={() => {
                    if (!keyChanged) {
                      setApiKey('')
                      setKeyChanged(true)
                    }
                  }}
                  placeholder="sk-..."
                  className="w-full bg-sub-bg border border-border-color/20 rounded-lg px-3 py-2.5 pr-10 text-sm text-text-primary placeholder:text-text-secondary/30 outline-none focus:border-accent/40 transition-colors font-mono"
                />
                <button
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-text-secondary hover:text-text-primary"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              {/* Base URL */}
              <label className="block text-xs text-text-secondary mb-1.5">Base URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
                className="w-full bg-sub-bg border border-border-color/20 rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/30 outline-none focus:border-accent/40 transition-colors font-mono mb-4"
              />

              {/* Model */}
              <label className="block text-xs text-text-secondary mb-1.5">模型</label>
              {currentModels.length > 0 ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-sub-bg border border-border-color/20 rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent/40 transition-colors appearance-none cursor-pointer"
                >
                  {currentModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  {model && !currentModels.includes(model) && (
                    <option value={model}>{model} (当前)</option>
                  )}
                </select>
              ) : (
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="模型名称"
                  className="w-full bg-sub-bg border border-border-color/20 rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/30 outline-none focus:border-accent/40 transition-colors"
                />
              )}
            </div>

            {/* Status Messages */}
            {error && (
              <div className="flex items-center gap-2 text-error text-xs bg-error/10 rounded-lg px-3 py-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                {error}
              </div>
            )}
            {success && (
              <div className="flex items-center gap-2 text-success text-xs bg-success/10 rounded-lg px-3 py-2">
                <Check className="w-3.5 h-3.5 shrink-0" />
                {success}
              </div>
            )}

            {/* Save Button */}
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl py-2.5 text-sm font-medium transition-all flex items-center justify-center gap-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              {saving ? '保存中...' : '保存配置'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
