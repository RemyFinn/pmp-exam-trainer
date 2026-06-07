import { useState } from 'react'
import { LogIn } from 'lucide-react'
import { api } from '../api/client'
import { Button, TextField, inputClass, panelClass } from '../components/ui'

export function LoginView({ onLogin, notify }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    try {
      const user = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password }),
      })
      onLogin(user)
    } catch (error) {
      notify({ type: 'error', text: error.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-paper-50 px-4 py-10 text-ink-950">
      <form className={panelClass('w-full max-w-sm p-5')} onSubmit={submit}>
        <div className="mb-5">
          <h1 className="text-2xl font-semibold tracking-tight">PMP 练习系统</h1>
          <p className="mt-1 text-sm text-ink-400">登录后开始做题。</p>
        </div>
        <div className="grid gap-4">
          <TextField label="用户名">
            <input className={inputClass()} value={username} onChange={(event) => setUsername(event.target.value)} autoFocus />
          </TextField>
          <TextField label="密码">
            <input className={inputClass()} type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </TextField>
          <Button variant="primary" type="submit" disabled={loading || !username.trim() || !password}>
            <LogIn size={16} />
            登录
          </Button>
        </div>
      </form>
    </div>
  )
}
