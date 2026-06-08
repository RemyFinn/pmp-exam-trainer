import { useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, Search, Target } from 'lucide-react'
import { api } from '../api/client'
import { EXAM_LABELS } from '../constants'
import { formatDateTime } from '../utils/format'
import { Badge, Button, CountStepper, Screen, SelectControl, TextField, inputClass, panelClass } from '../components/ui'

export function WrongItemsView({ exams, reloadExams, notify, run, onStartPractice }) {
  const [questions, setQuestions] = useState([])
  const [examFilter, setExamFilter] = useState('')
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [hasLoaded, setHasLoaded] = useState(false)

  async function loadWrongQuestions() {
    setIsLoading(true)
    let path = '/api/wrong-items'
    const params = []
    if (examFilter) params.push(`exam=${encodeURIComponent(examFilter)}`)
    if (search.trim()) params.push(`search=${encodeURIComponent(search.trim())}`)
    if (params.length) path += `?${params.join('&')}`
    try {
      const data = await api(path)
      setQuestions(data)
      setHasLoaded(true)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadWrongQuestions().catch((error) => notify({ type: 'error', text: error.message }))
  }, [examFilter])

  async function markLearned(questionId) {
    await run(async () => {
      await api(`/api/questions/${questionId}/wrong-item`, {
        method: 'PATCH',
        body: JSON.stringify({ learned: true }),
      })
      setQuestions((previous) => previous.filter((question) => question.id !== questionId))
      await reloadExams()
    }, '已移出错题集')
  }

  async function adjustWrongCount(question, delta) {
    const nextCount = Math.max(0, (Number(question.wrong_count) || 0) + delta)
    await run(async () => {
      const updated = await api(`/api/questions/${question.id}/statistics`, {
        method: 'PATCH',
        body: JSON.stringify({ wrong_count: nextCount }),
      })
      setQuestions((previous) =>
        nextCount === 0
          ? previous.filter((item) => item.id !== question.id)
          : previous
              .map((item) => (item.id === question.id ? updated : item))
              .sort((a, b) => {
                const wrongDiff = (Number(b.wrong_count) || 0) - (Number(a.wrong_count) || 0)
                if (wrongDiff !== 0) return wrongDiff
                return String(b.last_wrong_at || '').localeCompare(String(a.last_wrong_at || ''))
              }),
      )
      await reloadExams()
    }, nextCount === 0 ? '已从错题统计中移除' : '错题次数已调整')
  }

  async function adjustAttemptCount(question, delta) {
    const nextCount = Math.max(0, (Number(question.attempt_count) || 0) + delta)
    await run(async () => {
      const updated = await api(`/api/questions/${question.id}/statistics`, {
        method: 'PATCH',
        body: JSON.stringify({ attempt_count: nextCount }),
      })
      setQuestions((previous) => previous.map((item) => (item.id === question.id ? updated : item)))
      await reloadExams()
    }, '作答次数已调整')
  }

  function startFrom(index) {
    onStartPractice(questions, index, { type: 'wrong', label: '错题集', backView: 'wrong' })
  }

  const totalWrongAttempts = questions.reduce((sum, question) => sum + (Number(question.wrong_count) || 0), 0)

  return (
    <Screen>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">错题管理</h2>
          <p className="mt-1 text-sm text-ink-400">按错误次数复盘，学会后从错题集中移除。</p>
        </div>
        <Button variant="primary" onClick={() => startFrom(0)} disabled={isLoading || questions.length === 0}>
          <Target size={16} />
          开始错题练习
        </Button>
      </div>

      <section className={panelClass('p-4')}>
        <div className="grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)_auto] lg:items-end">
          <TextField label="套卷">
            <SelectControl
              value={examFilter || 'all'}
              onValueChange={(value) => setExamFilter(value === 'all' ? '' : value)}
              options={[{ value: 'all', label: '全部套卷' }, ...exams.map((exam) => ({ value: exam.code, label: exam.title }))]}
              ariaLabel="筛选错题套卷"
            />
          </TextField>
          <TextField label="搜索">
            <div className="relative">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
              <input
                className={inputClass('pl-9')}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="题干、解析或答案"
              />
            </div>
          </TextField>
          <Button variant="secondary" onClick={() => run(loadWrongQuestions)} disabled={isLoading}>
            搜索
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-sm text-ink-500">
          <Badge tone="danger">
            <div className="min-w-[3ch] text-right font-latin tabular-nums">{hasLoaded ? questions.length : '--'}</div>
            道错题
          </Badge>
          <Badge tone="neutral">
            累计错
            <div className="min-w-[4ch] text-right font-latin tabular-nums">{hasLoaded ? totalWrongAttempts : '--'}</div>
            次
          </Badge>
          <Badge tone="blue">错得多的优先</Badge>
        </div>

        <div className="mt-4 divide-y divide-ink-950/[0.035]">
          {isLoading && !hasLoaded && (
            <div className="flex h-14 items-center text-sm font-medium text-ink-400">
              正在加载错题...
            </div>
          )}

          {!isLoading && hasLoaded && questions.length === 0 && (
            <div className="py-12 text-center">
              <CheckCircle2 size={26} className="mx-auto text-ink-300" />
              <p className="mt-3 text-sm font-semibold text-ink-700">当前没有错题</p>
              <p className="mt-1 text-sm text-ink-400">继续练习后，答错的题会自动回到这里。</p>
            </div>
          )}

          {hasLoaded && questions.map((question, index) => (
            <div key={question.id} className="grid gap-3 py-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge tone="blue">
                    {EXAM_LABELS[question.exam_code] || question.exam_code.toUpperCase()} · 第 <div className="font-latin">{question.number}</div> 题
                  </Badge>
                  <Badge tone={question.is_multi ? 'accent' : 'neutral'}>{question.is_multi ? '多选' : '单选'}</Badge>
                  <CountStepper
                    label="错"
                    value={question.wrong_count}
                    onDecrease={() => adjustWrongCount(question, -1)}
                    onIncrease={() => adjustWrongCount(question, 1)}
                  />
                  <CountStepper
                    label="作答"
                    value={question.attempt_count}
                    tone="neutral"
                    onDecrease={() => adjustAttemptCount(question, -1)}
                    onIncrease={() => adjustAttemptCount(question, 1)}
                  />
                </div>
                <button
                  type="button"
                  className="group block w-full text-left"
                  onClick={() => startFrom(index)}
                >
                  <h3 className="line-clamp-2 text-[15px] font-semibold leading-6 text-ink-950 underline-offset-[5px] decoration-[0.6px] group-hover:underline">
                    {question.stem}
                  </h3>
                </button>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-400">
                  <div>答案 <div className="inline font-latin font-semibold text-ink-700">{question.correct_answer}</div></div>
                  <div>最近错题 {formatDateTime(question.last_wrong_at)}</div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Button variant="secondary" onClick={() => startFrom(index)}>
                  <ArrowRight size={16} />
                  练这题
                </Button>
                <Button variant="ghost" onClick={() => markLearned(question.id)}>
                  <CheckCircle2 size={16} />
                  学会了
                </Button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </Screen>
  )
}
