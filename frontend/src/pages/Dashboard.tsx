import { useQuery } from '@tanstack/react-query'
import { Shield, Cpu, HardDrive, Database, CheckCircle, AlertTriangle, XCircle, Lock, Unlock } from 'lucide-react'
import api from '../services/api'
import { useAuth } from '../store/auth'

function StatusBadge({ status }: { status: string }) {
  const styles = {
    healthy: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/30',
    unavailable: 'bg-red-400/10 text-red-400 border-red-400/30',
    unhealthy: 'bg-amber-400/10 text-amber-400 border-amber-400/30',
  }
  const icons = { healthy: CheckCircle, unavailable: XCircle, unhealthy: AlertTriangle }
  const Icon = icons[status as keyof typeof icons] || AlertTriangle
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs ${styles[status as keyof typeof styles] || styles.unhealthy}`}>
      <Icon size={12} />
      {status.toUpperCase()}
    </span>
  )
}

const ACCESS_MAP: Record<string, { accessible: string[], restricted: string[] }> = {
  super_admin: {
    accessible: ['All Documents', 'System Settings', 'User Management', 'Audit Logs', 'Security', 'All Features'],
    restricted: [],
  },
  department_manager: {
    accessible: ['Engineering SOP', 'Financial Forecast', 'Board Strategy', 'Quality Reports', 'Audit Logs'],
    restricted: ['HR Recruitment', 'System Settings', 'User Management'],
  },
  hr_manager: {
    accessible: ['Employee Handbook', 'HR Recruitment Plan', 'General Safety'],
    restricted: ['Engineering SOP', 'Financial Forecast', 'Board Strategy', 'System Settings'],
  },
  engineer: {
    accessible: ['Engineering SOP', 'Quality Reports', 'General Safety', 'Code Sandbox'],
    restricted: ['HR Documents', 'Financial Forecast', 'Board Strategy', 'User Management'],
  },
  finance: {
    accessible: ['Financial Forecast', 'General Safety'],
    restricted: ['Engineering SOP', 'HR Documents', 'Board Strategy', 'Code Sandbox'],
  },
  reviewer: {
    accessible: ['Quality Reports', 'General Safety'],
    restricted: ['HR Documents', 'Engineering SOP', 'Financial Forecast', 'Board Strategy', 'Code Sandbox'],
  },
}

export default function Dashboard() {
  const { user } = useAuth()

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: hardware } = useQuery({
    queryKey: ['hardware'],
    queryFn: () => api.get('/hardware/').then(r => r.data),
    refetchInterval: 15000,
  })

  const { data: modelsHealth } = useQuery({
    queryKey: ['models-health'],
    queryFn: () => api.get('/models/health').then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: networkStatus } = useQuery({
    queryKey: ['network-status'],
    queryFn: () => api.get('/network/status').then(r => r.data),
    refetchInterval: 30000,
  })

  const accessInfo = ACCESS_MAP[user?.role || ''] || { accessible: ['General Documents'], restricted: ['Administrative Features'] }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Command Center</h1>
          <p className="text-sm text-[#64748b]">System overview and status monitoring</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-emerald-400 font-mono">
            {health?.air_gapped ? 'AIR-GAPPED' : 'MONITORED'}
          </span>
        </div>
      </div>

      {/* Status Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <Shield className="text-cyan-400" size={20} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">Security</span>
          </div>
          <StatusBadge status={networkStatus?.status?.mode === 'air_gapped' ? 'healthy' : 'unhealthy'} />
          <p className="text-xs text-[#64748b] mt-2">
            Blocked: {networkStatus?.blocked_connections_24h || 0} (24h)
          </p>
        </div>

        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <Cpu className="text-cyan-400" size={20} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">Models</span>
          </div>
          <StatusBadge status={modelsHealth?.ollama?.status || 'unavailable'} />
          <p className="text-xs text-[#64748b] mt-2">
            Models: {modelsHealth?.ollama?.model_count || 0} available
          </p>
        </div>

        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <HardDrive className="text-cyan-400" size={20} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">Hardware</span>
          </div>
          <div className="font-mono text-sm text-[#f1f5f9]">
            {hardware?.gpu?.gpus?.[0]?.name || 'Detecting...'}
          </div>
          <p className="text-xs text-[#64748b] mt-2">
            VRAM: {hardware?.gpu?.total_vram_mb ? `${Math.round(hardware.gpu.total_vram_mb / 1024)}GB` : 'N/A'} |
            RAM: {hardware?.memory?.total_gb ? `${hardware.memory.total_gb}GB` : 'N/A'}
          </p>
        </div>

        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <Database className="text-cyan-400" size={20} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">System</span>
          </div>
          <StatusBadge status={health?.status || 'unavailable'} />
          <p className="text-xs text-[#64748b] mt-2">
            {health?.app || 'Connecting...'} v{health?.version || '?'}
          </p>
        </div>
      </div>

      {/* User Profile + Access + Resources */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Session Info */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">User Profile</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Name</span>
              <span className="text-[#f1f5f9] font-mono">{user?.display_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Employee ID</span>
              <span className="text-[#f1f5f9] font-mono">{user?.employee_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Role</span>
              <span className="text-cyan-400 font-mono text-xs">{user?.role_display || user?.role}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Department</span>
              <span className="text-[#f1f5f9] font-mono">{user?.department || 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Permissions</span>
              <span className="text-[#f1f5f9] font-mono">{user?.permissions?.length || 0}</span>
            </div>
          </div>
        </div>

        {/* Accessible Areas */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <h3 className="text-sm font-medium text-emerald-400 mb-3 flex items-center gap-2">
            <Unlock size={14} /> Accessible Areas
          </h3>
          <div className="space-y-1.5">
            {accessInfo.accessible.map(area => (
              <div key={area} className="flex items-center gap-2 text-xs">
                <CheckCircle size={12} className="text-emerald-400 flex-shrink-0" />
                <span className="text-[#f1f5f9]">{area}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Restricted Areas */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <h3 className="text-sm font-medium text-red-400 mb-3 flex items-center gap-2">
            <Lock size={14} /> Restricted by Policy
          </h3>
          {accessInfo.restricted.length === 0 ? (
            <p className="text-xs text-emerald-400">Full system access — Super Administrator</p>
          ) : (
            <div className="space-y-1.5">
              {accessInfo.restricted.map(area => (
                <div key={area} className="flex items-center gap-2 text-xs">
                  <Lock size={12} className="text-red-400/60 flex-shrink-0" />
                  <span className="text-[#64748b]">{area}</span>
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-[#475569] mt-3">Access controlled by organizational policy</p>
        </div>
      </div>

      {/* Resource Utilization */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">Resource Utilization</h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs text-[#94a3b8] mb-1">
                <span>CPU</span>
                <span className="font-mono">{hardware?.cpu?.usage_percent || 0}%</span>
              </div>
              <div className="w-full h-2 bg-[#0a0e17] rounded-full overflow-hidden">
                <div className="h-full bg-cyan-400 rounded-full transition-all" style={{ width: `${hardware?.cpu?.usage_percent || 0}%` }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-[#94a3b8] mb-1">
                <span>RAM</span>
                <span className="font-mono">{hardware?.memory?.usage_percent || 0}%</span>
              </div>
              <div className="w-full h-2 bg-[#0a0e17] rounded-full overflow-hidden">
                <div className="h-full bg-amber-400 rounded-full transition-all" style={{ width: `${hardware?.memory?.usage_percent || 0}%` }} />
              </div>
            </div>
            {hardware?.gpu?.gpus?.[0] && (
              <div>
                <div className="flex justify-between text-xs text-[#94a3b8] mb-1">
                  <span>GPU</span>
                  <span className="font-mono">{hardware.gpu.gpus[0].utilization_percent || 0}%</span>
                </div>
                <div className="w-full h-2 bg-[#0a0e17] rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-400 rounded-full transition-all" style={{ width: `${hardware.gpu.gpus[0].utilization_percent || 0}%` }} />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">Session Status</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Status</span>
              <span className="text-emerald-400 font-mono text-xs">ACTIVE</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Environment</span>
              <span className="text-[#f1f5f9] font-mono">{health?.environment || 'unknown'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Air-Gapped</span>
              <span className={`font-mono text-xs ${health?.air_gapped ? 'text-emerald-400' : 'text-amber-400'}`}>
                {health?.air_gapped ? 'YES' : 'NO'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#94a3b8]">Sovereignty</span>
              <span className="text-emerald-400 font-mono text-xs">ENFORCED</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
