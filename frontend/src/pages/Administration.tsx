import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Users, Shield, Settings, Bot, Check, X, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../services/api'

export default function Administration() {
  const [activeTab, setActiveTab] = useState('users')
  const queryClient = useQueryClient()

  const { data: users } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/users/').then(r => r.data),
    enabled: activeTab === 'users',
  })

  const { data: roles } = useQuery({
    queryKey: ['admin-roles'],
    queryFn: () => api.get('/roles/').then(r => r.data),
  })

  const { data: agenticSettings } = useQuery({
    queryKey: ['agentic-settings'],
    queryFn: () => api.get('/security/settings/agentic').then(r => r.data),
    enabled: activeTab === 'agentic',
  })

  const { data: approvals } = useQuery({
    queryKey: ['agent-approvals'],
    queryFn: () => api.get('/agents/approvals').then(r => r.data).catch(() => ({ approvals: [] })),
    enabled: activeTab === 'agentic',
    refetchInterval: activeTab === 'agentic' ? 8000 : false,
  })

  const toggleHitl = useMutation({
    mutationFn: (hitl_enabled: boolean) => api.put('/security/settings/agentic', { hitl_enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agentic-settings'] })
      toast.success('Human-in-the-Loop setting updated')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Failed to update setting'),
  })

  const resolveApproval = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' }) =>
      api.post(`/agents/approvals/${id}/${action}`),
    onSuccess: (_res, vars) => {
      queryClient.invalidateQueries({ queryKey: ['agent-approvals'] })
      toast.success(vars.action === 'approve' ? 'Approved — agent continued execution' : 'Rejected — agent stopped safely')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Action failed'),
  })

  const tabs = [
    { id: 'users', label: 'Users', icon: Users },
    { id: 'roles', label: 'Roles', icon: Shield },
    { id: 'agentic', label: 'Agentic AI', icon: Bot },
    { id: 'system', label: 'System', icon: Settings },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">Administration</h1>
        <p className="text-sm text-[#64748b]">System administration and user management</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#111827] border border-[#334155] rounded-lg p-1 w-fit">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded text-sm transition-colors ${
              activeTab === tab.id ? 'bg-cyan-400/20 text-cyan-400' : 'text-[#94a3b8] hover:text-[#f1f5f9]'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Users Tab */}
      {activeTab === 'users' && (
        <div className="bg-[#111827] border border-[#334155] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#334155] text-[#94a3b8] text-xs uppercase tracking-wide">
                <th className="text-left p-3">Employee</th>
                <th className="text-left p-3">Username</th>
                <th className="text-left p-3">Role</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Last Login</th>
              </tr>
            </thead>
            <tbody>
              {users?.users?.map((u: any) => (
                <tr key={u.id} className="border-b border-[#334155]/50 hover:bg-[#1a2332]">
                  <td className="p-3">
                    <div className="text-[#f1f5f9]">{u.display_name}</div>
                    <div className="text-xs text-[#64748b] font-mono">{u.employee_id}</div>
                  </td>
                  <td className="p-3 text-[#94a3b8] font-mono text-xs">{u.username}</td>
                  <td className="p-3 text-[#94a3b8] text-xs">{u.role_id}</td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      u.status === 'active' ? 'bg-emerald-400/10 text-emerald-400' : 'bg-red-400/10 text-red-400'
                    }`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="p-3 text-xs text-[#64748b] font-mono">
                    {u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Roles Tab */}
      {activeTab === 'roles' && (
        <div className="space-y-3">
          {roles?.roles?.map((r: any) => (
            <div key={r.id} className="bg-[#111827] border border-[#334155] rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-sm font-medium text-[#f1f5f9]">{r.display_name}</span>
                  {r.is_system && <span className="ml-2 text-xs text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">System</span>}
                </div>
                <span className="text-xs text-[#64748b] font-mono">{r.name}</span>
              </div>
              <p className="text-xs text-[#94a3b8] mb-2">{r.description}</p>
              <div className="flex flex-wrap gap-1">
                {r.permissions?.map((p: string) => (
                  <span key={p} className="text-xs px-1.5 py-0.5 bg-[#1a2332] border border-[#334155] rounded text-[#94a3b8] font-mono">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Agentic AI Tab */}
      {activeTab === 'agentic' && (
        <div className="space-y-4">
          <div className="bg-[#111827] border border-[#334155] rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-[#f1f5f9]">Human-in-the-Loop Approval</h3>
                <p className="text-xs text-[#64748b] mt-1 max-w-xl">
                  When OFF (default), authorized agentic workflows run fully automated.
                  When ON, actions marked sensitive ({(agenticSettings?.sensitive_actions || []).join(', ') || 'none configured'})
                  pause and wait for an authorized approver instead of executing immediately.
                </p>
              </div>
              <button
                onClick={() => toggleHitl.mutate(!agenticSettings?.hitl_enabled)}
                disabled={toggleHitl.isPending}
                className={`shrink-0 px-4 py-2 rounded-lg text-xs font-mono border transition-colors ${
                  agenticSettings?.hitl_enabled
                    ? 'bg-amber-400/10 border-amber-400/40 text-amber-400'
                    : 'bg-emerald-400/10 border-emerald-400/40 text-emerald-400'
                }`}
              >
                {agenticSettings?.hitl_enabled ? 'HITL: ON' : 'HITL: OFF'}
              </button>
            </div>
          </div>

          <div className="bg-[#111827] border border-[#334155] rounded-lg p-6">
            <h3 className="text-sm font-medium text-[#f1f5f9] mb-3 flex items-center gap-2">
              <Clock size={14} className="text-amber-400" /> Pending Approvals
            </h3>
            {(!approvals?.approvals || approvals.approvals.length === 0) && (
              <p className="text-xs text-[#64748b]">No actions waiting for approval.</p>
            )}
            <div className="space-y-2">
              {approvals?.approvals?.map((a: any) => (
                <div key={a.id} className="flex items-center justify-between bg-[#1a2332] border border-[#334155]/60 rounded-lg px-4 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="px-1.5 py-0.5 bg-cyan-400/10 text-cyan-400 rounded font-mono">{a.action_type}</span>
                      <span className="text-[#64748b]">requested by {a.requester_name || a.requested_by}</span>
                    </div>
                    <p className="text-sm text-[#e2e8f0] mt-1 truncate">{a.query_preview || a.reason}</p>
                  </div>
                  <div className="flex gap-2 shrink-0 ml-3">
                    <button
                      onClick={() => resolveApproval.mutate({ id: a.id, action: 'approve' })}
                      disabled={resolveApproval.isPending}
                      className="p-2 rounded bg-emerald-400/10 border border-emerald-400/30 text-emerald-400 hover:bg-emerald-400/20"
                      title="Approve"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => resolveApproval.mutate({ id: a.id, action: 'reject' })}
                      disabled={resolveApproval.isPending}
                      className="p-2 rounded bg-red-400/10 border border-red-400/30 text-red-400 hover:bg-red-400/20"
                      title="Reject"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* System Tab */}
      {activeTab === 'system' && (
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-6">
          <h3 className="text-sm font-medium text-[#f1f5f9] mb-4">System Configuration</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-2 border-b border-[#334155]/50">
              <span className="text-[#94a3b8]">Application Name</span>
              <span className="text-[#f1f5f9] font-mono">Sovereign AI Workbench</span>
            </div>
            <div className="flex justify-between py-2 border-b border-[#334155]/50">
              <span className="text-[#94a3b8]">Air-Gapped Mode</span>
              <span className="text-emerald-400 font-mono">ENABLED</span>
            </div>
            <div className="flex justify-between py-2 border-b border-[#334155]/50">
              <span className="text-[#94a3b8]">Max Upload Size</span>
              <span className="text-[#f1f5f9] font-mono">500 MB</span>
            </div>
            <div className="flex justify-between py-2 border-b border-[#334155]/50">
              <span className="text-[#94a3b8]">Sandbox Timeout</span>
              <span className="text-[#f1f5f9] font-mono">30s</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-[#94a3b8]">Session Timeout</span>
              <span className="text-[#f1f5f9] font-mono">60 min</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
