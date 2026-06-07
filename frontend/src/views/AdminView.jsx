import { useEffect, useState } from 'react'
import { FilePenLine, Search, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import { OPTION_LABELS } from '../constants'
import { letters } from '../utils/format'
import {
  AnswerLettersControl,
  Button,
  CheckboxControl,
  Screen,
  SelectControl,
  TextField,
  inputClass,
  panelClass,
} from '../components/ui'
import { cn } from '../lib/utils'

export function AdminView({ exams, reloadExams, notify, run }) {
  const [questions, setQuestions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [examFilter, setExamFilter] = useState('')
  const [search, setSearch] = useState('')
  const [form, setForm] = useState(emptyQuestion(exams[0]?.code || 'sim7'))

  const selectedQuestion = questions.find((item) => item.id === selectedId)

  async function loadQuestions() {
    let path = examFilter ? `/api/questions?mode=exam&exam=${encodeURIComponent(examFilter)}` : '/api/questions?mode=admin'
    if (search.trim()) path += `&search=${encodeURIComponent(search.trim())}`
    const data = await api(path)
    setQuestions(data)
  }

  useEffect(() => {
    loadQuestions().catch((error) => notify({ type: 'error', text: error.message }))
  }, [examFilter])

  useEffect(() => {
    if (selectedQuestion) setForm(questionToForm(selectedQuestion))
  }, [selectedQuestion])

  function resetForm() {
    setSelectedId(null)
    setForm(emptyQuestion(exams[0]?.code || 'sim7'))
  }

  function confirmClear() {
    if (!confirm(selectedId ? '确认清空当前编辑内容并切换到新增题目？' : '确认清空当前新增内容？')) return
    resetForm()
  }

  async function save(event) {
    event.preventDefault()
    const payload = formToPayload(form)
    const error = validatePayload(payload)
    if (error) return notify({ type: 'error', text: error })
    await run(async () => {
      if (selectedId) {
        await api(`/api/questions/${selectedId}`, { method: 'PATCH', body: JSON.stringify(payload) })
      } else {
        await api('/api/questions', { method: 'POST', body: JSON.stringify(payload) })
      }
      await loadQuestions()
      await reloadExams()
    }, selectedId ? '题目已保存' : '题目已新增')
  }

  async function remove() {
    if (!selectedId) return
    if (!confirm('确认删除？')) return
    await run(async () => {
      await api(`/api/questions/${selectedId}`, { method: 'DELETE' })
      resetForm()
      await loadQuestions()
      await reloadExams()
    }, '题目已删除')
  }

  return (
    <Screen>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">题库管理</h2>
          <p className="mt-1 text-sm text-ink-400">筛选、编辑和维护题库。</p>
        </div>
        <Button variant="primary" onClick={resetForm}>
          <FilePenLine size={16} />
          新增题目
        </Button>
      </div>

      <div className="grid gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
        <section className={panelClass('p-4')}>
          <div className="grid gap-3">
            <TextField label="套卷">
              <SelectControl
                value={examFilter || 'all'}
                onValueChange={(value) => setExamFilter(value === 'all' ? '' : value)}
                options={[{ value: 'all', label: '全部套卷' }, ...exams.map((exam) => ({ value: exam.code, label: exam.title }))]}
                ariaLabel="筛选套卷"
              />
            </TextField>
            <TextField label="搜索">
              <div className="relative">
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
                <input className={inputClass('pl-9')} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="关键词" />
              </div>
            </TextField>
            <Button variant="secondary" onClick={() => run(loadQuestions)}>
              搜索
            </Button>
          </div>

          <div className="mt-4 grid max-h-[64vh] gap-2 overflow-auto pr-1" aria-label="题目列表">
            {questions.map((question) => (
              <button
                key={question.id}
                className={cn(
                  'rounded-lg border border-transparent bg-paper-50/72 px-3 py-2.5 text-left transition hover:border-ink-950/[0.055] hover:bg-white',
                  selectedId === question.id && 'border-ink-950/[0.1] bg-white shadow-hairline',
                )}
                onClick={() => setSelectedId(question.id)}
              >
                <strong className="block font-latin text-sm tabular-nums">
                  {question.exam_code.toUpperCase()}-{question.number} · {question.correct_answer}
                </strong>
                <div className="mt-1 line-clamp-2 text-sm leading-6 text-ink-400">{question.stem}</div>
              </button>
            ))}
          </div>
        </section>

        <QuestionEditor
          exams={exams}
          form={form}
          setForm={setForm}
          selectedId={selectedId}
          onSave={save}
          onDelete={remove}
          onClear={confirmClear}
        />
      </div>
    </Screen>
  )
}

function emptyQuestion(examCode) {
  return {
    exam_code: examCode,
    number: '',
    stem: '',
    is_multi: false,
    correct_answer: '',
    explanation: '',
    options: OPTION_LABELS.map((label) => ({ label, text: '' })),
  }
}

function questionToForm(question) {
  const optionMap = new Map(question.options.map((option) => [option.label, option.text]))
  return {
    exam_code: question.exam_code,
    number: question.number,
    stem: question.stem,
    is_multi: question.is_multi,
    correct_answer: question.correct_answer,
    explanation: question.explanation,
    options: OPTION_LABELS.map((label) => ({ label, text: optionMap.get(label) || '' })),
  }
}

function formToPayload(form) {
  return {
    ...form,
    number: Number(form.number),
    stem: form.stem.trim(),
    correct_answer: form.correct_answer.trim(),
    explanation: form.explanation.trim(),
    options: form.options.filter((option) => option.text.trim()),
  }
}

function validatePayload(payload) {
  if (!Number.isInteger(payload.number) || payload.number < 1) return '请输入有效题号。'
  if (!payload.stem) return '请输入题干。'
  if (!payload.correct_answer) return '请选择标准答案。'
  if (payload.options.length < 2) return '至少保留两个选项。'

  const optionLabels = new Set(payload.options.map((option) => option.label))
  const missingAnswer = letters(payload.correct_answer).find((label) => !optionLabels.has(label))
  if (missingAnswer) return `标准答案 ${missingAnswer} 对应的选项还没有填写。`
  return ''
}

function QuestionEditor({ exams, form, setForm, selectedId, onSave, onDelete, onClear }) {
  function setOption(label, text) {
    setForm((previous) => ({
      ...previous,
      options: previous.options.map((option) => (option.label === label ? { ...option, text } : option)),
    }))
  }

  return (
    <form className={panelClass('p-4')} onSubmit={onSave}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">{selectedId ? '编辑题目' : '新增题目'}</h3>
          <p className="text-sm text-ink-400">{selectedId ? `ID ${selectedId}` : 'New'}</p>
        </div>
      </div>

      <div className="grid gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label="套卷">
            <SelectControl
              value={form.exam_code}
              onValueChange={(value) => setForm({ ...form, exam_code: value })}
              options={exams.map((exam) => ({ value: exam.code, label: exam.title }))}
              ariaLabel="选择题目套卷"
            />
          </TextField>
          <TextField label="题号">
            <input
              className={inputClass()}
              type="number"
              min="1"
              value={form.number}
              onChange={(event) => setForm({ ...form, number: event.target.value })}
              required
            />
          </TextField>
        </div>

        <TextField label="题干">
          <textarea className={inputClass('min-h-[170px] resize-y py-3 leading-7')} value={form.stem} onChange={(event) => setForm({ ...form, stem: event.target.value })} required />
        </TextField>

        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_160px]">
          <TextField label="标准答案">
            <AnswerLettersControl
              value={form.correct_answer}
              isMulti={form.is_multi}
              onChange={(value) => setForm({ ...form, correct_answer: value })}
            />
          </TextField>
          <CheckboxControl checked={form.is_multi} onCheckedChange={(checked) => setForm({ ...form, is_multi: checked })}>
            多选题
          </CheckboxControl>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {form.options.map((option) => (
            <TextField key={option.label} label={option.label}>
              <input className={inputClass()} value={option.text} onChange={(event) => setOption(option.label, event.target.value)} />
            </TextField>
          ))}
        </div>

        <TextField label="解析">
          <textarea
            className={inputClass('min-h-[190px] resize-y py-3 leading-7')}
            value={form.explanation}
            onChange={(event) => setForm({ ...form, explanation: event.target.value })}
          />
        </TextField>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button variant="primary" type="submit">
          保存
        </Button>
        <Button variant="secondary" onClick={onClear}>
          清空
        </Button>
        {selectedId && (
          <Button variant="danger" onClick={onDelete}>
            <Trash2 size={16} />
            删除
          </Button>
        )}
      </div>
    </form>
  )
}
