import React, { useEffect, useState } from 'react'
import { useAppStore } from '../store'
import {
  X,
  Puzzle,
  Download,
  Trash2,
  Loader2,
  LayoutGrid,
  Sparkles,
  Github,
  Slack,
  FileText,
  Image,
  Figma,
  GraduationCap,
  Code2,
  BarChart3,
  Search,
  RefreshCw,
  Table2,
  Mail,
  Languages,
  Video,
  ScanEye,
  Database,
  Webhook,
  Users,
  UserCircle,
  ShieldCheck,
  Share2,
  Globe,
  Calendar,
} from 'lucide-react'

interface ClawSkillMarketProps {
  open: boolean
  onClose: () => void
}

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  figma: Figma,
  slack: Slack,
  github: Github,
  image: Image,
  'file-text': FileText,
  'graduation-cap': GraduationCap,
  'code-2': Code2,
  'bar-chart-3': BarChart3,
  puzzle: Puzzle,
  search: Search,
  table: Table2,
  mail: Mail,
  languages: Languages,
  video: Video,
  'scan-eye': ScanEye,
  database: Database,
  webhook: Webhook,
  users: Users,
  'user-circle': UserCircle,
  'shield-check': ShieldCheck,
  'share-2': Share2,
  globe: Globe,
  calendar: Calendar,
}

function getIcon(iconName: string) {
  return iconMap[iconName] || Puzzle
}

export default function ClawSkillMarket({ open, onClose }: ClawSkillMarketProps) {
  const {
    activeSkills,
    marketplaceSkills,
    skillsLoading,
    fetchActiveSkills,
    fetchMarketplace,
    installSkill,
    uninstallSkill,
  } = useAppStore()

  const [installingId, setInstallingId] = useState<string | null>(null)
  const [uninstallingId, setUninstallingId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'active' | 'marketplace'>('active')

  useEffect(() => {
    if (open) {
      fetchActiveSkills()
      fetchMarketplace()
    }
  }, [open, fetchActiveSkills, fetchMarketplace])

  const handleInstall = async (skillId: string) => {
    setInstallingId(skillId)
    const success = await installSkill(skillId)
    setInstallingId(null)
    if (success) {
      // Refresh both lists
      await fetchActiveSkills()
      await fetchMarketplace()
    }
  }

  const handleUninstall = async (skillId: string) => {
    setUninstallingId(skillId)
    const success = await uninstallSkill(skillId)
    setUninstallingId(null)
    if (success) {
      await fetchActiveSkills()
      await fetchMarketplace()
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-card-bg border border-border-color/20 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-color/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">ClawSkill 市场</h2>
              <p className="text-xs text-text-secondary">扩展 Agent Harness 的能力</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-border-color/10 text-text-secondary hover:text-text-primary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 px-6 py-3 border-b border-border-color/10">
          <button
            onClick={() => setActiveTab('active')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'active'
                ? 'bg-accent/10 text-accent'
                : 'text-text-secondary hover:text-text-primary hover:bg-border-color/5'
            }`}
          >
            <LayoutGrid className="w-4 h-4" />
            已安装技能
            <span className="px-1.5 py-0.5 text-xs bg-border-color/20 rounded-full">
              {activeSkills.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('marketplace')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'marketplace'
                ? 'bg-accent/10 text-accent'
                : 'text-text-secondary hover:text-text-primary hover:bg-border-color/5'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            技能市场
            <span className="px-1.5 py-0.5 text-xs bg-border-color/20 rounded-full">
              {marketplaceSkills.length}
            </span>
          </button>
          <div className="flex-1" />
          <button
            onClick={() => {
              fetchActiveSkills()
              fetchMarketplace()
            }}
            disabled={skillsLoading}
            className="p-2 rounded-lg hover:bg-border-color/10 text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
            title="刷新列表"
          >
            <RefreshCw className={`w-4 h-4 ${skillsLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'active' ? (
            <div className="space-y-3">
              {activeSkills.length === 0 ? (
                <div className="text-center py-12 text-text-secondary">
                  <Puzzle className="w-12 h-12 mx-auto mb-4 opacity-40" />
                  <p>暂无已安装技能</p>
                  <p className="text-sm mt-1 opacity-60">从市场安装技能来扩展功能</p>
                </div>
              ) : (
                activeSkills.map((skill) => {
                  const Icon = getIcon(skill.icon)
                  return (
                    <div
                      key={skill.name}
                      className="flex items-center gap-4 p-4 rounded-xl border border-border-color/10 bg-sub-bg/50 hover:bg-sub-bg transition-colors"
                    >
                      <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
                        <Icon className="w-6 h-6 text-accent" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-text-primary truncate">{skill.name}</h3>
                          <span className="px-2 py-0.5 text-xs bg-success/10 text-success rounded-full">
                            运行中
                          </span>
                        </div>
                        <p className="text-sm text-text-secondary mt-0.5 truncate">
                          {skill.description}
                        </p>
                        <div className="flex items-center gap-2 mt-2 text-xs text-text-secondary/60">
                          <span>v{skill.version}</span>
                          <span>·</span>
                          <span>{skill.requires.join(', ')}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleUninstall(skill.name)}
                        disabled={uninstallingId === skill.name}
                        className="p-2 rounded-lg hover:bg-error/10 text-text-secondary hover:text-error transition-colors disabled:opacity-50"
                        title="卸载技能"
                      >
                        {uninstallingId === skill.name ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  )
                })
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {marketplaceSkills.length === 0 ? (
                <div className="text-center py-12 text-text-secondary">
                  <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-40" />
                  <p>市场暂无可用技能</p>
                </div>
              ) : (
                marketplaceSkills.map((skill) => {
                  const Icon = getIcon(skill.icon)
                  return (
                    <div
                      key={skill.id}
                      className={`flex items-center gap-4 p-4 rounded-xl border transition-colors ${
                        skill.installed
                          ? 'border-success/20 bg-success/5'
                          : 'border-border-color/10 bg-sub-bg/50 hover:bg-sub-bg'
                      }`}
                    >
                      <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
                        <Icon className="w-6 h-6 text-accent" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-text-primary truncate">{skill.name}</h3>
                          <span
                            className={`px-2 py-0.5 text-xs rounded-full ${
                              skill.installed
                                ? 'bg-success/10 text-success'
                                : 'bg-border-color/20 text-text-secondary'
                            }`}
                          >
                            {skill.installed ? '已安装' : skill.category}
                          </span>
                        </div>
                        <p className="text-sm text-text-secondary mt-0.5 truncate">
                          {skill.description}
                        </p>
                        <div className="flex items-center gap-2 mt-2 text-xs text-text-secondary/60">
                          <span>v{skill.version}</span>
                          <span>·</span>
                          <span>{skill.author}</span>
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          skill.installed ? handleUninstall(skill.id) : handleInstall(skill.id)
                        }
                        disabled={installingId === skill.id || uninstallingId === skill.id}
                        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                          skill.installed
                            ? 'bg-border-color/10 text-text-secondary hover:bg-error/10 hover:text-error'
                            : 'bg-accent text-white hover:bg-accent-hover'
                        }`}
                      >
                        {installingId === skill.id || uninstallingId === skill.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : skill.installed ? (
                          <>
                            <Trash2 className="w-4 h-4" />
                            卸载
                          </>
                        ) : (
                          <>
                            <Download className="w-4 h-4" />
                            安装
                          </>
                        )}
                      </button>
                    </div>
                  )
                })
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border-color/10 bg-sub-bg/30 rounded-b-2xl">
          <p className="text-xs text-text-secondary/60 text-center">
            ClawSkill 市场 · 动态扩展 Agent Harness 能力 · 更多技能即将上线
          </p>
        </div>
      </div>
    </div>
  )
}
