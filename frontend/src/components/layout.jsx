import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Database,
  GraduationCap,
  Lightbulb,
  Layers3,
  ListChecks,
  LogOut,
  RefreshCw,
  Target,
  Users,
  XCircle,
} from 'lucide-react'
import { FONT_OPTIONS } from '../constants'
import { cn } from '../lib/utils'
import { Button, SelectControl } from './ui'

export function Sidebar({ view, totals, user, onLogout }) {
  const isAdmin = user?.role === 'admin'
  return (
    <aside className="relative border-b border-white/25 bg-[radial-gradient(circle_at_30%_0%,rgba(138,112,77,0.06),transparent_34%),linear-gradient(180deg,rgba(251,250,247,0.64),rgba(245,241,234,0.48))] px-4 py-4 backdrop-blur-2xl after:pointer-events-none after:absolute after:bottom-0 after:left-0 after:h-px after:w-full after:bg-gradient-to-r after:from-transparent after:via-ink-950/[0.07] after:to-transparent lg:sticky lg:top-0 lg:h-dvh lg:border-b-0 lg:px-5 lg:after:bottom-6 lg:after:left-auto lg:after:right-0 lg:after:top-6 lg:after:h-auto lg:after:w-px lg:after:bg-gradient-to-b">
      <div className="flex items-center gap-3">
        <div className="grid size-10 place-items-center rounded-lg bg-ink-950 text-paper-50">
          <GraduationCap size={22} />
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold tracking-tight">PMP 练习系统</h1>
          <p className="text-xs font-medium text-ink-400">Local trainer</p>
        </div>
      </div>

      <nav className="mt-5 grid grid-cols-4 gap-2 lg:grid-cols-1">
        <NavItem active={view === 'home'} to="/" icon={<BookOpen size={17} />} label="练习" />
        <NavItem active={view === 'strategies'} to="/strategies" icon={<Lightbulb size={17} />} label="思路" />
        <NavItem active={view === 'wrong'} to="/wrong" icon={<Target size={17} />} label="错题" />
        {isAdmin && <NavItem active={view === 'admin'} to="/admin" icon={<Database size={17} />} label="题库" />}
        {isAdmin && <NavItem active={view === 'users'} to="/users" icon={<Users size={17} />} label="用户" />}
      </nav>

      <div className="mt-5 grid grid-cols-3 gap-2 lg:grid-cols-1">
        <Metric label="题目" value={totals.questions} icon={<Layers3 size={15} />} />
        <Metric label="错题" value={totals.wrong} icon={<Target size={15} />} />
        <Metric label="记录" value={totals.attempts} icon={<ListChecks size={15} />} />
      </div>

      <div className="mt-5 flex items-center justify-between gap-2 rounded-xl bg-white/24 px-3 py-2 text-sm text-ink-600 ring-1 ring-white/20 backdrop-blur-2xl">
        <div className="min-w-0">
          <div className="truncate font-semibold text-ink-900">{user?.display_name || user?.username}</div>
          <div className="mt-0.5 text-xs text-ink-400">{isAdmin ? '管理员' : '普通用户'}</div>
        </div>
        <Button variant="icon" className="size-8" onClick={onLogout} aria-label="退出登录" title="退出登录">
          <LogOut size={15} />
        </Button>
      </div>
    </aside>
  )
}

function NavItem({ active, to, icon, label }) {
  return (
    <Button as={Link} to={to} variant={active ? 'primary' : 'ghost'} className="justify-start">
      {icon}
      {label}
    </Button>
  )
}

function Metric({ label, value, icon }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-xl border border-white/[0.28] bg-white/24 px-2.5 py-2.5 shadow-[0_8px_22px_rgba(42,35,28,0.045)] backdrop-blur-2xl ring-1 ring-white/20">
      <div className="hidden size-7 place-items-center rounded-lg border border-white/20 bg-white/20 text-ink-500 backdrop-blur-xl sm:grid">{icon}</div>
      <div className="min-w-0">
        <strong className="block font-latin text-[15px] leading-none tabular-nums text-ink-950">{value}</strong>
        <div className="mt-1 text-[11px] font-semibold leading-none text-ink-500">{label}</div>
      </div>
    </div>
  )
}

export function TopBar({ onRefresh, loading, fontMode, setFontMode }) {
  return (
    <header className="mx-auto mb-4 flex w-full max-w-6xl flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">PMP Practice</p>
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">练习</h2>
      </div>
      <div className="flex items-center gap-2">
        <SelectControl
          value={fontMode}
          onValueChange={setFontMode}
          options={FONT_OPTIONS}
          ariaLabel="选择界面字体"
          prefix="字体"
          triggerClassName="min-h-10 w-[128px] border-0 bg-white/50 hover:bg-white/65"
        />
        <Button variant="ghost" onClick={onRefresh} disabled={loading}>
          <RefreshCw size={16} className={cn(loading && 'animate-spin')} />
          刷新
        </Button>
      </div>
    </header>
  )
}

export function Notice({ notice, onClose }) {
  const Icon = notice.type === 'error' ? AlertCircle : CheckCircle2
  return (
    <motion.div
      className={cn(
        'mx-auto mb-4 flex max-w-6xl items-center gap-2 rounded-lg border px-3 py-2 text-sm shadow-quiet',
        notice.type === 'error'
          ? 'border-[#b36a5c]/[0.12] bg-[#f5e7e3] text-[#7f3e36]'
          : 'border-[#708b68]/[0.12] bg-[#edf4e8] text-[#496a45]',
      )}
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      role="status"
      aria-live="polite"
    >
      <Icon size={17} />
      <div className="min-w-0 flex-1 leading-5">{notice.text}</div>
      <button type="button" onClick={onClose} aria-label="关闭提示" className="text-current">
        <XCircle size={17} />
      </button>
    </motion.div>
  )
}
