import { motion } from 'framer-motion'
import { ArrowRight, BookOpen, Shuffle, Target } from 'lucide-react'
import { Badge, Screen, panelClass } from '../components/ui'

export function HomeView({ exams, totals, onStart }) {
  return (
    <Screen className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section className={panelClass('bg-white/58 p-4 sm:p-5')}>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">选择练习</h2>
            <p className="mt-1 text-sm text-ink-400">按套卷练习，或混合打乱后复盘错题。</p>
          </div>
          <Badge tone="blue">PostgreSQL · 个人记录</Badge>
        </div>
      <div className="divide-y divide-ink-950/[0.035]">
          {exams.map((exam) => (
            <ModeRow
              key={exam.code}
              title={exam.title.replace('PMP 仿真', '')}
              meta={`${exam.total_questions} 题`}
              extra={`${exam.wrong_questions} 错题`}
              icon={<BookOpen size={18} />}
              onClick={() => onStart({ type: 'exam', examCode: exam.code, label: exam.title })}
            />
          ))}
          <ModeRow
            title="混合随机"
            meta="720 题"
            extra="打乱顺序"
            icon={<Shuffle size={18} />}
            onClick={() => onStart({ type: 'mixed', label: '混合随机' })}
          />
          <ModeRow
            title="错题集"
            meta={`${totals.wrong} 题`}
            extra="动态维护"
            icon={<Target size={18} />}
            onClick={() => onStart({ type: 'wrong', label: '错题集' })}
          />
        </div>
      </section>

      <aside className="rounded-xl bg-ink-950 p-5 text-paper-50 shadow-quiet">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-paper-200/65">Overview</p>
        <div className="mt-6 grid gap-5">
          <DashboardNumber label="题目" value={totals.questions} />
          <DashboardNumber label="错题" value={totals.wrong} />
          <DashboardNumber label="作答记录" value={totals.attempts} />
        </div>
      </aside>
    </Screen>
  )
}

function DashboardNumber({ label, value }) {
  return (
    <div>
      <strong className="block font-latin text-3xl font-semibold leading-none tabular-nums">{value}</strong>
      <div className="mt-1 text-sm leading-5 text-paper-200/65">{label}</div>
    </div>
  )
}

function ModeRow({ title, meta, extra, icon, onClick }) {
  return (
    <motion.button
      className="group grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 py-3.5 text-left"
      onClick={onClick}
      whileHover={{ x: 2 }}
      whileTap={{ scale: 0.995 }}
    >
      <div className="grid size-9 place-items-center rounded-md bg-ink-950/[0.045] text-ink-600 transition group-hover:bg-ink-950 group-hover:text-paper-50">
        {icon}
      </div>
      <div className="min-w-0">
        <h3 className="truncate text-base font-semibold tracking-tight">{title}</h3>
        <p className="mt-0.5 text-sm text-ink-400">{meta} · {extra}</p>
      </div>
      <ArrowRight size={18} className="text-ink-400 transition group-hover:text-ink-950" />
    </motion.button>
  )
}
