import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../services/api'

export default function AuditCenter() {
  const [action, setAction] = useState('')
  const [severity, setSeverity] = useState('')

  const { data } = useQuery({
    queryKey: ['audit-events', action, severity],
    queryFn: () => api.get('/audit/events', { params: { action: action || undefined, severity: severity || undefined, limit: 100 } }).then(r => r.data),
    refetchInterval: 10000,
  })

  const severityColors: Record<string, string> = {
    info: 'text-blue-400',
    warning: 'text-amber-400',
    error: 'text-red-400',
    critical: 'text-red-500',
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">Audit Center</h1>
        <p className="text-sm text-[#64748b]">Complete audit trail of system activities</p>
      </div>

      <div className="flex gap-3">
        <select
          value={action}
          onChange={(e) => setAction(e.target.value)}
          className="px-3 py-2 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9]"
        >
          <option value="">All Actions</option>
          <option value="login">Login</option>
          <option value="logout">Logout</option>
          <option value="login_failed">Login Failed</option>
          <option value="document_uploaded">Document Upload</option>
          <option value="document_accessed">Document Access</option>
          <option value="code_executed">Code Execution</option>
          <option value="rag_query">RAG Query</option>
          <option value="model_registered">Model Registered</option>
          <option value="file_generated">File Generated</option>
        </select>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="px-3 py-2 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9]"
        >
          <option value="">All Severity</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      <div className="bg-[#111827] border border-[#334155] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#334155] text-[#94a3b8] text-xs uppercase tracking-wide">
              <th className="text-left p-3">Time</th>
              <th className="text-left p-3">Action</th>
              <th className="text-left p-3">Resource</th>
              <th className="text-left p-3">Severity</th>
              <th className="text-left p-3">Details</th>
            </tr>
          </thead>
          <tbody>
            {data?.events?.map((e: any) => (
              <tr key={e.id} className="border-b border-[#334155]/50 hover:bg-[#1a2332]">
                <td className="p-3 text-xs text-[#94a3b8] font-mono whitespace-nowrap">
                  {new Date(e.created_at).toLocaleString()}
                </td>
                <td className="p-3 text-[#f1f5f9] font-mono text-xs">{e.action}</td>
                <td className="p-3 text-[#94a3b8] text-xs">{e.resource_type || '-'}</td>
                <td className="p-3">
                  <span className={`text-xs ${severityColors[e.severity] || 'text-[#94a3b8]'}`}>
                    {e.severity?.toUpperCase()}
                  </span>
                </td>
                <td className="p-3 text-xs text-[#64748b] max-w-[200px] truncate">
                  {e.details ? JSON.stringify(e.details).slice(0, 50) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
