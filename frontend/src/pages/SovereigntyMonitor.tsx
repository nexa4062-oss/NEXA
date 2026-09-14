import { useQuery, useMutation } from '@tanstack/react-query'
import { Shield, Globe, Lock, AlertTriangle, CheckCircle } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'

export default function SovereigntyMonitor() {
  const { data: status } = useQuery({
    queryKey: ['network-status'],
    queryFn: () => api.get('/network/status').then(r => r.data),
    refetchInterval: 10000,
  })

  const { data: events } = useQuery({
    queryKey: ['network-events'],
    queryFn: () => api.get('/network/events').then(r => r.data),
  })

  const testMutation = useMutation({
    mutationFn: () => api.post('/network/test-block').then(r => r.data),
    onSuccess: (data) => {
      if (data.all_blocked) {
        toast.success('All external connections blocked - system is air-gapped')
      } else {
        toast.error('WARNING: Some connections were not blocked!')
      }
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Sovereignty Monitor</h1>
          <p className="text-sm text-[#64748b]">Network isolation and data sovereignty verification</p>
        </div>
        <button
          onClick={() => testMutation.mutate()}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-400/20 border border-cyan-400/30 rounded text-sm text-cyan-400 hover:bg-cyan-400/30"
        >
          <Shield size={16} /> Test Air-Gap
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`border rounded-lg p-4 ${status?.air_gapped_mode ? 'bg-emerald-400/5 border-emerald-400/30' : 'bg-red-400/5 border-red-400/30'}`}>
          <div className="flex items-center gap-2 mb-2">
            {status?.air_gapped_mode ? <Lock className="text-emerald-400" size={20} /> : <Globe className="text-red-400" size={20} />}
            <span className="text-sm font-medium text-[#f1f5f9]">Air-Gap Mode</span>
          </div>
          <p className={`text-lg font-bold font-mono ${status?.air_gapped_mode ? 'text-emerald-400' : 'text-red-400'}`}>
            {status?.air_gapped_mode ? 'ACTIVE' : 'INACTIVE'}
          </p>
        </div>

        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="text-amber-400" size={20} />
            <span className="text-sm font-medium text-[#f1f5f9]">Blocked (24h)</span>
          </div>
          <p className="text-lg font-bold font-mono text-amber-400">{status?.blocked_connections_24h || 0}</p>
        </div>

        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="text-cyan-400" size={20} />
            <span className="text-sm font-medium text-[#f1f5f9]">Local Services</span>
          </div>
          <div className="space-y-1">
            {status?.status?.local_services && Object.entries(status.status.local_services).map(([svc, st]) => (
              <div key={svc} className="flex justify-between text-xs">
                <span className="text-[#94a3b8]">{svc}</span>
                <span className={st === 'healthy' ? 'text-emerald-400' : 'text-red-400'}>{st as string}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Blocked Domains */}
      <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
        <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">Blocked External Domains</h3>
        <div className="space-y-2">
          {status?.blocked_domains?.map((domain: string) => (
            <div key={domain} className="flex items-center gap-2 text-sm">
              <Lock size={12} className="text-red-400" />
              <span className="font-mono text-[#94a3b8]">{domain}</span>
              <span className="text-xs text-red-400">BLOCKED</span>
            </div>
          ))}
        </div>
      </div>

      {/* Events */}
      <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
        <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">Network Events</h3>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {events?.events?.map((e: any) => (
            <div key={e.id} className="flex items-center gap-3 text-xs py-1 border-b border-[#334155]/50">
              <span className={`w-2 h-2 rounded-full ${e.type === 'outbound_blocked' ? 'bg-red-400' : 'bg-emerald-400'}`} />
              <span className="text-[#94a3b8] font-mono w-40">{new Date(e.created_at).toLocaleString()}</span>
              <span className="text-[#f1f5f9]">{e.destination || e.source}</span>
              <span className={e.type === 'outbound_blocked' ? 'text-red-400' : 'text-emerald-400'}>{e.action}</span>
            </div>
          ))}
          {(!events?.events || events.events.length === 0) && (
            <p className="text-[#64748b] text-center py-4">No network events recorded</p>
          )}
        </div>
      </div>
    </div>
  )
}
