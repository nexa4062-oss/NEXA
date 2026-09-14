import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, ArrowRight } from 'lucide-react'

/**
 * Pre-login step: collects the Employee ID before the actual
 * authentication form. This does NOT authenticate anything itself -
 * it only identifies which employee is about to log in and hands that
 * value forward to the existing Login page, which still performs the
 * real, unchanged authentication against /api/auth/login.
 */
export default function EmployeeIdentify() {
  const [employeeId, setEmployeeId] = useState('')
  const navigate = useNavigate()

  const handleContinue = (e: React.FormEvent) => {
    e.preventDefault()
    if (!employeeId.trim()) return
    navigate('/login', { state: { employeeId: employeeId.trim() } })
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

        <form onSubmit={handleContinue} className="bg-[#111827] border border-[#334155] rounded-lg p-6 space-y-4">
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Employee ID</label>
            <input
              type="text" value={employeeId} onChange={e => setEmployeeId(e.target.value)}
              autoFocus
              className="w-full px-3 py-2.5 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none transition-colors"
              placeholder="e.g. EMP-001" required
            />
            <p className="text-[10px] text-[#475569] mt-2">
              Enter your organizational Employee ID to continue to sign-in. You'll enter your password on the next screen.
            </p>
          </div>
          <button type="submit"
            className="w-full py-2.5 bg-cyan-400/20 text-cyan-400 border border-cyan-400/30 rounded text-sm font-medium hover:bg-cyan-400/30 transition-colors flex items-center justify-center gap-2">
            Continue <ArrowRight size={14} />
          </button>
        </form>

        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-emerald-400">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>LOCAL MODE — AIR-GAPPED</span>
        </div>
      </div>
    </div>
  )
}
