import { useEffect, useState } from 'react'
import { KeyRound, UserPlus } from 'lucide-react'
import { api } from '../api/client'
import { Badge, Button, CheckboxControl, Screen, SelectControl, TextField, inputClass, panelClass } from '../components/ui'

export function UsersView({ notify, run }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ username: '', display_name: '', password: '', role: 'user' })

  async function loadUsers() {
    setUsers(await api('/api/users'))
  }

  useEffect(() => {
    loadUsers().catch((error) => notify({ type: 'error', text: error.message }))
  }, [])

  async function createUser(event) {
    event.preventDefault()
    await run(async () => {
      await api('/api/users', { method: 'POST', body: JSON.stringify(form) })
      setForm({ username: '', display_name: '', password: '', role: 'user' })
      await loadUsers()
    }, '用户已创建')
  }

  async function updateUser(user, patch) {
    await run(async () => {
      await api(`/api/users/${user.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
      await loadUsers()
    }, '用户已更新')
  }

  async function resetPassword(user) {
    const password = prompt(`给 ${user.username} 设置新密码`)
    if (!password) return
    await updateUser(user, { password })
  }

  return (
    <Screen>
      <div className="mb-4">
        <h2 className="text-2xl font-semibold tracking-tight">用户管理</h2>
        <p className="mt-1 text-sm text-ink-400">创建朋友账号，控制谁可以访问系统。</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <form className={panelClass('p-4')} onSubmit={createUser}>
          <div className="mb-4 flex items-center gap-2 font-semibold">
            <UserPlus size={17} />
            新增用户
          </div>
          <div className="grid gap-3">
            <TextField label="用户名">
              <input className={inputClass()} value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
            </TextField>
            <TextField label="显示名">
              <input className={inputClass()} value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} />
            </TextField>
            <TextField label="初始密码">
              <input className={inputClass()} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
            </TextField>
            <TextField label="角色">
              <SelectControl
                value={form.role}
                onValueChange={(value) => setForm({ ...form, role: value })}
                options={[
                  { value: 'user', label: '普通用户' },
                  { value: 'admin', label: '管理员' },
                ]}
                ariaLabel="选择用户角色"
              />
            </TextField>
            <Button variant="primary" type="submit" disabled={!form.username.trim() || form.password.length < 6}>
              创建
            </Button>
          </div>
        </form>

        <section className={panelClass('p-4')}>
          <div className="grid gap-2">
            {users.map((user) => (
              <div key={user.id} className="grid gap-3 rounded-lg bg-ink-950/[0.018] px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong>{user.display_name || user.username}</strong>
                    <Badge tone={user.role === 'admin' ? 'blue' : 'neutral'}>{user.role === 'admin' ? '管理员' : '普通用户'}</Badge>
                    {!user.is_active && <Badge tone="danger">已禁用</Badge>}
                  </div>
                  <div className="mt-1 font-latin text-sm text-ink-400">{user.username}</div>
                </div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <CheckboxControl
                    checked={user.is_active}
                    onCheckedChange={(checked) => updateUser(user, { is_active: checked })}
                    className="min-h-10"
                  >
                    启用
                  </CheckboxControl>
                  <Button variant="secondary" onClick={() => resetPassword(user)}>
                    <KeyRound size={16} />
                    重置密码
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </Screen>
  )
}
