import { useQuery } from '@tanstack/react-query'
import { Cpu, HardDrive, MemoryStick, Monitor } from 'lucide-react'
import api from '../services/api'

export default function Hardware() {
  const { data: hw } = useQuery({
    queryKey: ['hardware-full'],
    queryFn: () => api.get('/hardware/').then(r => r.data),
    refetchInterval: 5000,
  })

  const { data: compat } = useQuery({
    queryKey: ['hardware-compat'],
    queryFn: () => api.get('/hardware/compatibility').then(r => r.data),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">Hardware Dashboard</h1>
        <p className="text-sm text-[#64748b]">System hardware monitoring and model compatibility</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* CPU */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Cpu className="text-cyan-400" size={18} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">CPU</span>
          </div>
          <p className="text-sm text-[#f1f5f9] font-mono truncate">{hw?.cpu?.name || 'Detecting...'}</p>
          <div className="mt-2 space-y-1 text-xs text-[#94a3b8]">
            <div className="flex justify-between">
              <span>Cores</span>
              <span className="font-mono text-[#f1f5f9]">{hw?.cpu?.cores_physical || 0} / {hw?.cpu?.cores_logical || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>Usage</span>
              <span className="font-mono text-[#f1f5f9]">{hw?.cpu?.usage_percent || 0}%</span>
            </div>
          </div>
          <div className="mt-2 w-full h-2 bg-[#0a0e17] rounded-full overflow-hidden">
            <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${hw?.cpu?.usage_percent || 0}%` }} />
          </div>
        </div>

        {/* RAM */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <MemoryStick className="text-amber-400" size={18} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">RAM</span>
          </div>
          <p className="text-sm text-[#f1f5f9] font-mono">{hw?.memory?.total_gb || 0} GB Total</p>
          <div className="mt-2 space-y-1 text-xs text-[#94a3b8]">
            <div className="flex justify-between">
              <span>Available</span>
              <span className="font-mono text-[#f1f5f9]">{hw?.memory?.available_gb || 0} GB</span>
            </div>
            <div className="flex justify-between">
              <span>Used</span>
              <span className="font-mono text-[#f1f5f9]">{hw?.memory?.used_gb || 0} GB</span>
            </div>
          </div>
          <div className="mt-2 w-full h-2 bg-[#0a0e17] rounded-full overflow-hidden">
            <div className="h-full bg-amber-400 rounded-full" style={{ width: `${hw?.memory?.usage_percent || 0}%` }} />
          </div>
        </div>

        {/* GPU */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Monitor className="text-emerald-400" size={18} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">GPU</span>
          </div>
          <p className="text-sm text-[#f1f5f9] font-mono truncate">{hw?.gpu?.gpus?.[0]?.name || 'No GPU detected'}</p>
          <div className="mt-2 space-y-1 text-xs text-[#94a3b8]">
            <div className="flex justify-between">
              <span>VRAM</span>
              <span className="font-mono text-[#f1f5f9]">{hw?.gpu?.total_vram_mb ? `${Math.round(hw.gpu.total_vram_mb / 1024)} GB` : 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span>CUDA</span>
              <span className={`font-mono ${hw?.gpu?.cuda_available ? 'text-emerald-400' : 'text-red-400'}`}>
                {hw?.gpu?.cuda_available ? 'Available' : 'Unavailable'}
              </span>
            </div>
          </div>
          {hw?.gpu?.gpus?.[0] && (
            <div className="mt-2 w-full h-2 bg-[#0a0e17] rounded-full overflow-hidden">
              <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${hw.gpu.gpus[0].utilization_percent || 0}%` }} />
            </div>
          )}
        </div>

        {/* Disk */}
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <HardDrive className="text-purple-400" size={18} />
            <span className="text-xs text-[#94a3b8] uppercase tracking-wide">Disk</span>
          </div>
          {hw?.disk?.partitions?.slice(0, 2).map((p: any, i: number) => (
            <div key={i} className="mb-2">
              <div className="flex justify-between text-xs text-[#94a3b8]">
                <span className="font-mono">{p.device}</span>
                <span className="font-mono text-[#f1f5f9]">{p.free_gb} GB free</span>
              </div>
              <div className="mt-1 w-full h-1.5 bg-[#0a0e17] rounded-full overflow-hidden">
                <div className="h-full bg-purple-400 rounded-full" style={{ width: `${p.used_percent}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Model Compatibility */}
      {compat && (
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4">
          <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">Model Compatibility Assessment</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-xs">
            <div className="text-[#94a3b8]">RAM: <span className="text-[#f1f5f9] font-mono">{compat.ram_gb} GB</span></div>
            <div className="text-[#94a3b8]">VRAM: <span className="text-[#f1f5f9] font-mono">{compat.vram_gb} GB</span></div>
            <div className="text-[#94a3b8]">CUDA: <span className={compat.cuda_available ? 'text-emerald-400' : 'text-red-400'}>{compat.cuda_available ? 'Yes' : 'No'}</span></div>
            <div className="text-[#94a3b8]">Max Model: <span className="text-cyan-400 font-mono">{compat.max_model_size}</span></div>
          </div>
          <div className="space-y-2">
            {compat.recommendations?.map((r: any, i: number) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className={`w-2 h-2 rounded-full ${r.feasible ? 'bg-emerald-400' : 'bg-red-400'}`} />
                <span className="font-mono text-[#f1f5f9] w-24">{r.size}</span>
                <span className="text-[#94a3b8]">{r.note}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
