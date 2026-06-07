import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from './api/client'
import { EXAM_ORDER } from './constants'
import { Notice, Sidebar, TopBar } from './components/layout'
import { HomeView } from './views/HomeView'
import { PracticeView } from './views/PracticeView'
import { StrategyView } from './views/StrategyView'
import { WrongItemsView } from './views/WrongItemsView'
import { AdminView } from './views/AdminView'

const ROUTE_TO_VIEW = {
  '/': 'home',
  '/strategies': 'strategies',
  '/wrong': 'wrong',
  '/admin': 'admin',
  '/practice': 'practice',
}

const VIEW_TO_ROUTE = {
  home: '/',
  strategies: '/strategies',
  wrong: '/wrong',
  admin: '/admin',
  practice: '/practice',
}

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const view = ROUTE_TO_VIEW[location.pathname]
  const [exams, setExams] = useState([])
  const [questions, setQuestions] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [mode, setMode] = useState(null)
  const [submitted, setSubmitted] = useState(new Map())
  const [fontMode, setFontMode] = useState(() => {
    const saved = localStorage.getItem('pmp-font-mode')
    return saved === 'system' ? 'system' : 'default'
  })
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState(null)

  const currentQuestion = questions[currentIndex]
  const submittedElapsed = useMemo(() => {
    let total = 0
    submitted.forEach((item) => {
      total += Math.max(0, Number(item.elapsed_seconds) || 0)
    })
    return total
  }, [submitted])
  const totals = useMemo(() => {
    return exams.reduce(
      (acc, exam) => ({
        questions: acc.questions + exam.total_questions,
        wrong: acc.wrong + exam.wrong_questions,
        attempts: acc.attempts + exam.attempts,
      }),
      { questions: 0, wrong: 0, attempts: 0 },
    )
  }, [exams])

  async function loadExams() {
    const data = await api('/api/exams')
    data.sort((a, b) => EXAM_ORDER.indexOf(a.code) - EXAM_ORDER.indexOf(b.code))
    setExams(data)
  }

  async function run(action, successMessage) {
    setLoading(true)
    try {
      const result = await action()
      if (successMessage) setNotice({ type: 'success', text: successMessage })
      return result
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
      throw error
    } finally {
      setLoading(false)
    }
  }

  async function startPractice(nextMode) {
    await run(async () => {
      let path = `/api/questions?mode=${nextMode.type}`
      if (nextMode.type === 'exam') path += `&exam=${encodeURIComponent(nextMode.examCode)}`
      if (nextMode.type === 'mixed') path += '&shuffle=1'
      const data = await api(path)
      if (data.length === 0) {
        setNotice({ type: 'info', text: '当前模式暂时没有题目。' })
        return
      }
      setQuestions(data)
      setSubmitted(new Map())
      setCurrentIndex(0)
      setMode(nextMode)
      navigate('/practice')
    })
  }

  function startPracticeFromQuestions(nextQuestions, startIndex = 0, nextMode = { type: 'wrong', label: '错题集' }) {
    if (nextQuestions.length === 0) {
      setNotice({ type: 'info', text: '当前没有可练习的题目。' })
      return
    }
    setQuestions(nextQuestions)
    setSubmitted(new Map())
    setCurrentIndex(Math.max(0, Math.min(startIndex, nextQuestions.length - 1)))
    setMode(nextMode)
    navigate('/practice')
  }

  async function openQuestionFromStrategy(question) {
    await run(async () => {
      const data = await api(`/api/questions?mode=exam&exam=${encodeURIComponent(question.exam_code)}`)
      const targetIndex = data.findIndex((item) => item.id === question.id)
      if (targetIndex < 0) {
        setNotice({ type: 'error', text: '没有找到对应题目。' })
        return
      }
      setQuestions(data)
      setSubmitted(new Map())
      setCurrentIndex(targetIndex)
      setMode({
        type: 'strategy',
        label: `${question.exam_code.toUpperCase()}-${question.number}`,
        backView: 'strategies',
      })
      navigate('/practice')
    })
  }

  async function refreshEverything() {
    await run(loadExams, '统计已刷新')
  }

  useEffect(() => {
    loadExams().catch((error) => setNotice({ type: 'error', text: error.message }))
  }, [])

  useEffect(() => {
    document.documentElement.dataset.font = fontMode
    localStorage.setItem('pmp-font-mode', fontMode)
  }, [fontMode])

  return (
    <div className="min-h-dvh bg-paper-50 text-ink-950">
      <a className="skip-link" href="#main">跳到主要内容</a>
      <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[236px_minmax(0,1fr)]">
        <Sidebar view={view || 'home'} totals={totals} />
        <main id="main" className="min-w-0 px-4 py-4 sm:px-6 lg:px-8">
          <TopBar onRefresh={refreshEverything} loading={loading} fontMode={fontMode} setFontMode={setFontMode} />
          <AnimatePresence>{notice && <Notice notice={notice} onClose={() => setNotice(null)} />}</AnimatePresence>
          <AnimatePresence mode="wait">
            {!view && <Navigate key="not-found" to="/" replace />}
            {view === 'home' && <HomeView key="home" exams={exams} totals={totals} onStart={startPractice} />}
            {view === 'strategies' && (
              <StrategyView
                key="strategies"
                exams={exams}
                notify={setNotice}
                run={run}
                reloadExams={loadExams}
                onOpenQuestion={openQuestionFromStrategy}
              />
            )}
            {view === 'practice' && !currentQuestion && <Navigate key="empty-practice" to="/" replace />}
            {view === 'practice' && currentQuestion && (
              <PracticeView
                key="practice"
                question={currentQuestion}
                index={currentIndex}
                total={questions.length}
                mode={mode}
                result={submitted.get(currentQuestion.id)}
                submittedElapsed={submittedElapsed}
                onBack={() => navigate(VIEW_TO_ROUTE[mode?.backView] || '/')}
                onPrevious={() => setCurrentIndex((value) => Math.max(0, value - 1))}
                onNext={() => setCurrentIndex((value) => Math.min(questions.length - 1, value + 1))}
                onSubmit={async (selectedOptions, elapsedSeconds) => {
                  const result = await run(async () => {
                    const response = await api('/api/attempts', {
                      method: 'POST',
                      body: JSON.stringify({
                        question_id: currentQuestion.id,
                        selected_options: selectedOptions,
                        mode: mode?.type || 'practice',
                        elapsed_seconds: elapsedSeconds,
                      }),
                    })
                    setSubmitted((previous) => new Map(previous).set(currentQuestion.id, response))
                    setQuestions((previous) =>
                      previous.map((item) =>
                        item.id === currentQuestion.id
                          ? {
                              ...item,
                              is_wrong_active: response.is_wrong_active,
                              wrong_count: response.wrong_count,
                              attempt_count: response.attempt_count,
                              last_wrong_at: response.last_wrong_at,
                            }
                          : item,
                      ),
                    )
                    await loadExams()
                    return response
                  })
                  return result
                }}
                onLearned={async () => {
                  await run(async () => {
                    await api(`/api/wrong-items/${currentQuestion.id}`, {
                      method: 'PATCH',
                      body: JSON.stringify({ learned: true }),
                    })
                    setQuestions((previous) => {
                      const next =
                        mode?.type === 'wrong'
                          ? previous.filter((item) => item.id !== currentQuestion.id)
                          : previous.map((item) =>
                              item.id === currentQuestion.id ? { ...item, is_wrong_active: false } : item,
                            )
                      setCurrentIndex((value) => Math.max(0, Math.min(value, next.length - 1)))
                      if (mode?.type === 'wrong' && next.length === 0) {
                        navigate(VIEW_TO_ROUTE[mode?.backView] || '/')
                        setNotice({ type: 'success', text: '错题集已清空。' })
                      }
                      return next
                    })
                    await loadExams()
                  }, '已移出错题集')
                }}
              />
            )}
            {view === 'admin' && (
              <AdminView key="admin" exams={exams} reloadExams={loadExams} notify={setNotice} run={run} />
            )}
            {view === 'wrong' && (
              <WrongItemsView
                key="wrong"
                exams={exams}
                reloadExams={loadExams}
                notify={setNotice}
                run={run}
                onStartPractice={startPracticeFromQuestions}
              />
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
