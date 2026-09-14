import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../store/auth'
import { Shield, Users, Lock } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../services/api'

interface SetupStatus {
  needs_setup: boolean
  has_demo_accounts: boolean
}

interface DemoAccount {
  username: string
  role: string
  display_name: string
  designation: string
  department: string
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  { username: 'admin_demo', role: 'Administrator', display_name: 'Demo Administrator', designation: 'System Administrator', department: 'IT' },
  { username: 'hr_manager_demo', role: 'HR Manager', display_name: 'Priya Sharma', designation: 'HR Manager', department: 'Human Resources' },
  { username: 'manager_demo', role: 'Dept. Manager', display_name: 'Rajesh Kumar', designation: 'Department Manager', department: 'Operations' },
  { username: 'engineer_demo', role: 'Engineer', display_name: 'Ankit Patel', designation: 'Senior Engineer', department: 'Engineering' },
  { username: 'finance_demo', role: 'Finance', display_name: 'Meera Iyer', designation: 'Finance Analyst', department: 'Finance' },
  { username: 'reviewer_demo', role: 'Reviewer', display_name: 'Suresh Nair', designation: 'Quality Reviewer', department: 'Quality' },
]

const DEMO_PASSWORD = 'DemoPass@2026!'

function FirstRunSetup({ onComplete }: { onComplete: () => void }) {
  const [form, setForm] = useState({
    username: '', password: '', confirmPassword: '',
    display_name: '', employee_id: '', email: '', organization_name: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    try {
      await api.post('/auth/setup', {
        username: form.username,
        password: form.password,
        display_name: form.display_name,
        employee_id: form.employee_id,
        email: form.email,
        organization_name: form.organization_name,
      })
      toast.success('Administrator account created successfully')
      onComplete()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Setup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-lg">
      <div className="text-center mb-6">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-400/10 mb-4">
          <Lock className="text-amber-400" size={32} />
        </div>
        <h1 className="text-2xl font-bold text-[#f1f5f9]">Initial Administrator Setup</h1>
        <p className="text-sm text-[#94a3b8] mt-2 max-w-md mx-auto">
          This is the first startup of the Sovereign AI Workbench. Create the organization's initial administrator account.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111827] border border-[#334155] rounded-lg p-6 space-y-4">
        {error && (
          <div className="p-3 bg-red-400/10 border border-red-400/30 rounded text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Username</label>
            <input type="text" value={form.username} onChange={e => setForm({...form, username: e.target.value})}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
              placeholder="admin" required minLength={3} />
          </div>
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Employee ID</label>
            <input type="text" value={form.employee_id} onChange={e => setForm({...form, employee_id: e.target.value})}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
              placeholder="EMP-001" required />
          </div>
        </div>

        <div>
          <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Display Name</label>
          <input type="text" value={form.display_name} onChange={e => setForm({...form, display_name: e.target.value})}
            className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
            placeholder="Full Name" required />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Email</label>
            <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
              placeholder="admin@org.local" />
          </div>
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Organization Name</label>
            <input type="text" value={form.organization_name} onChange={e => setForm({...form, organization_name: e.target.value})}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
              placeholder="Organization" required />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Password</label>
            <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
              placeholder="Min 8 characters" required minLength={8} />
          </div>
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Confirm Password</label>
            <input type="password" value={form.confirmPassword} onChange={e => setForm({...form, confirmPassword: e.target.value})}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
              placeholder="Repeat password" required minLength={8} />
          </div>
        </div>

        <button type="submit" disabled={loading}
          className="w-full py-2.5 bg-amber-400/20 text-amber-400 border border-amber-400/30 rounded text-sm font-medium hover:bg-amber-400/30 transition-colors disabled:opacity-50">
          {loading ? 'Creating Administrator...' : 'Create Administrator Account'}
        </button>
      </form>
    </div>
  )
}

function DemoAccountsPanel({ onSelectAccount }: { onSelectAccount: (username: string, password: string) => void }) {
  return (
    <div className="mt-6 w-full max-w-2xl">
      <div className="border border-amber-400/20 rounded-lg p-4 bg-amber-400/5">
        <div className="flex items-center gap-2 mb-3">
          <Users className="text-amber-400" size={16} />
          <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">
            Demo Accounts — Local Evaluation Only
          </span>
        </div>
        <p className="text-xs text-[#64748b] mb-3">
          These accounts exist for hackathon demonstration only. Not for production use.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {DEMO_ACCOUNTS.map(acct => (
            <div key={acct.username} className="bg-[#0a0e17] border border-[#334155] rounded p-3 flex flex-col">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-cyan-400">{acct.role}</span>
              </div>
              <span className="text-xs text-[#94a3b8] mb-0.5">{acct.display_name}</span>
              <span className="text-[10px] text-[#475569] font-mono mb-2">{acct.username}</span>
              <button
                onClick={() => onSelectAccount(acct.username, DEMO_PASSWORD)}
                className="mt-auto px-2 py-1 bg-cyan-400/10 text-cyan-400 border border-cyan-400/20 rounded text-[10px] font-medium hover:bg-cyan-400/20 transition-colors"
              >
                Use Demo Account
              </button>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-[#475569] mt-3 text-center">
          DEMO CREDENTIAL — LOCAL HACKATHON USE ONLY
        </p>
      </div>
    </div>
  )
}

export default function Login() {
  const location = useLocation()
  const prefillEmployeeId = (location.state as { employeeId?: string } | null)?.employeeId || ''
  const [username, setUsername] = useState(prefillEmployeeId)
  const [password, setPassword] = useState('')
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null)
  const [setupComplete, setSetupComplete] = useState(false)
  const [seedingDemo, setSeedingDemo] = useState(false)
  const { login, isLoading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/auth/setup-status').then(r => setSetupStatus(r.data)).catch(() => {})
  }, [setupComplete])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login(username, password)
      navigate('/')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Invalid credentials')
    }
  }

  const handleSetupComplete = async () => {
    setSetupComplete(true)
    setSetupStatus({ needs_setup: false, has_demo_accounts: false })
    toast.success('Setup complete! You can now log in.')
  }

  const handleSeedDemo = async () => {
    setSeedingDemo(true)
    try {
      const r = await api.post('/auth/seed-demo')
      if (r.data.seeded) {
        toast.success('Demo accounts created')
        setSetupStatus(prev => prev ? { ...prev, has_demo_accounts: true } : prev)
      } else {
        toast.error(r.data.message)
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to seed demo accounts')
    } finally {
      setSeedingDemo(false)
    }
  }

  const handleSelectDemoAccount = (demoUsername: string, demoPassword: string) => {
    setUsername(demoUsername)
    setPassword(demoPassword)
  }

  if (setupStatus === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0e17]">
        <div className="text-[#94a3b8] text-sm">Connecting to server...</div>
      </div>
    )
  }

  if (setupStatus.needs_setup) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0e17] px-4 py-8">
        <FirstRunSetup onComplete={handleSetupComplete} />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#0a0e17] px-4 py-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-400/10 mb-4">
            <Shield className="text-cyan-400" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-[#f1f5f9]">Sovereign AI Workbench</h1>
          <p className="text-sm text-[#64748b] mt-2">Air-Gapped Organizational Intelligence Platform</p>
        </div>

        <form onSubmit={handleLogin} className="bg-[#111827] border border-[#334155] rounded-lg p-6 space-y-4">
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Employee ID / Username</label>
            <input
              type="text" value={username} onChange={e => setUsername(e.target.value)}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none transition-colors"
              placeholder="Enter employee ID or username" required
            />
          </div>
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Password</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none transition-colors"
              placeholder="Enter password" required
            />
          </div>
          <button type="submit" disabled={isLoading}
            className="w-full py-2.5 bg-cyan-400/20 text-cyan-400 border border-cyan-400/30 rounded text-sm font-medium hover:bg-cyan-400/30 transition-colors disabled:opacity-50">
            {isLoading ? 'Authenticating...' : 'Authenticate'}
          </button>
        </form>

        <div className="mt-4 flex items-center justify-center gap-4">
          <div className="flex items-center gap-2 text-xs text-emerald-400">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>LOCAL MODE — AIR-GAPPED</span>
          </div>
          {!setupStatus.has_demo_accounts && (
            <button onClick={handleSeedDemo} disabled={seedingDemo}
              className="text-xs text-amber-400/70 hover:text-amber-400 transition-colors disabled:opacity-50">
              {seedingDemo ? 'Creating...' : 'Initialize Demo Accounts'}
            </button>
          )}
        </div>
      </div>

      {setupStatus.has_demo_accounts && (
        <DemoAccountsPanel onSelectAccount={handleSelectDemoAccount} />
      )}
    </div>
  )
}
