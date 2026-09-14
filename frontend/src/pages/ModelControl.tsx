import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, Check, Zap, Play, AlertTriangle } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'

export default function ModelControl() {
  const queryClient = useQueryClient()

  const { data: health } = useQuery({
    queryKey: ['models-health'],
    queryFn: () => api.get('/models/health').then(r => r.data),
    refetchInterval: 15000,
  })

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.get('/models/').then(r => r.data),
  })

  const { data: discovered } = useQuery({
    queryKey: ['models-discover'],
    queryFn: () => api.get('/models/discover').then(r => r.data),
  })

  const testMutation = useMutation({
    mutationFn: (id: string) => api.post(`/models/${id}/test`).then(r => r.data),
    onSuccess: (data) => {
      if (data.success) {
        toast.success(`Model test passed (${data.latency_ms}ms)`)
      } else {
        // Surface the actual runtime error (e.g. "connection refused" /
        // "timed out") instead of a generic message, so failures caused
        // by Ollama not being reachable are actually diagnosable.
        toast.error(data.response ? `Model test failed: ${data.response}` : 'Model test failed', { duration: 6000 })
      }
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Model test request failed')
    },
  })

  const registerMutation = useMutation({
    mutationFn: (model: any) => api.post('/models/register', model),
    onSuccess: () => {
      toast.success('Model registered')
      queryClient.invalidateQueries({ queryKey: ['models'] })
      queryClient.invalidateQueries({ queryKey: ['models-discover'] })
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Model registration failed')
    },
  })

  const handleRegister = (m: any) => {
    const capabilities = []
    const name = m.name.toLowerCase()
    // Recognize all vision-capable families the backend router already
    // knows about (routing/service.py MODEL_CAPABILITY_MAP), not just
    // llava/*-vl - this previously missed "llama3.2-vision", "moondream",
    // "minicpm-v", and "bakllava".
    const isVision = name.includes('llava') || name.includes('vl')
      || name.includes('vision') || name.includes('moondream')
      || name.includes('minicpm-v') || name.includes('bakllava')
    if (isVision) capabilities.push('vision')
    if (name.includes('coder') || name.includes('code')) capabilities.push('coding')
    if (name.includes('embed')) capabilities.push('embedding')
    if (capabilities.length === 0) capabilities.push('general_reasoning')

    registerMutation.mutate({
      model_id: m.name,
      display_name: m.name,
      runtime: 'ollama',
      local_identifier: m.name,
      parameter_size: m.parameter_size || '',
      quantization: m.quantization || '',
      vision_support: isVision,
      coding_support: name.includes('coder') || name.includes('code'),
      reasoning_support: !name.includes('embed'),
      embedding_support: name.includes('embed'),
      capabilities,
      priority: 50,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">Model Control</h1>
        <p className="text-sm text-[#64748b]">Manage locally installed AI models</p>
      </div>

      {health?.ollama && health.ollama.status !== 'healthy' && (
        <div className="flex items-start gap-3 bg-red-400/10 border border-red-400/30 rounded-lg p-4">
          <AlertTriangle size={18} className="text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-red-400 font-medium">Ollama runtime is unreachable</p>
            <p className="text-xs text-[#94a3b8] mt-1">
              Every model test will fail while Ollama can't be reached, regardless of which model you pick.
              {health.ollama.url && <> Tried: <span className="font-mono">{health.ollama.url}</span>.</>}
              {health.ollama.error && <> Error: <span className="font-mono">{health.ollama.error}</span>.</>}
              {' '}Make sure Ollama is running, and if you're using Docker on Linux, confirm the backend's
              OLLAMA_URL / extra_hosts mapping resolves to the host.
            </p>
          </div>
        </div>
      )}

      {/* Registered Models */}
      <div>
        <h2 className="text-sm font-medium text-[#f1f5f9] mb-3">Registered Models</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {models?.models?.map((m: any) => (
            <div key={m.id} className="bg-[#111827] border border-[#334155] rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Cpu size={16} className="text-cyan-400" />
                  <span className="text-sm font-medium text-[#f1f5f9]">{m.display_name}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${m.enabled ? 'bg-emerald-400/10 text-emerald-400' : 'bg-red-400/10 text-red-400'}`}>
                  {m.status?.toUpperCase()}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-[#94a3b8]">
                <div>Runtime: <span className="text-[#f1f5f9] font-mono">{m.runtime}</span></div>
                <div>Context: <span className="text-[#f1f5f9] font-mono">{m.context_length || 'N/A'}</span></div>
                <div>Size: <span className="text-[#f1f5f9] font-mono">{m.parameter_size || 'N/A'}</span></div>
                <div>Quant: <span className="text-[#f1f5f9] font-mono">{m.quantization || 'N/A'}</span></div>
              </div>
              <div className="flex gap-2 mt-3 flex-wrap">
                {m.vision_support && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-400/10 text-purple-400">Vision</span>}
                {m.coding_support && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-400/10 text-blue-400">Coding</span>}
                {m.reasoning_support && <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-400/10 text-cyan-400">Reasoning</span>}
                {m.embedding_support && <span className="text-xs px-1.5 py-0.5 rounded bg-amber-400/10 text-amber-400">Embedding</span>}
              </div>
              <button
                onClick={() => testMutation.mutate(m.id)}
                className="mt-3 flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
              >
                <Play size={12} /> Test Model
              </button>
            </div>
          ))}
          {(!models?.models || models.models.length === 0) && (
            <p className="text-[#64748b] text-sm col-span-2">No models registered. Discover and register models below.</p>
          )}
        </div>
      </div>

      {/* Discovered Models */}
      <div>
        <h2 className="text-sm font-medium text-[#f1f5f9] mb-3">Discovered (Local Ollama)</h2>
        <div className="space-y-2">
          {discovered?.discovered?.map((m: any) => (
            <div key={m.name} className="bg-[#111827] border border-[#334155] rounded-lg p-3 flex items-center justify-between">
              <div>
                <span className="text-sm text-[#f1f5f9] font-mono">{m.name}</span>
                {m.installed !== false && (
                  <span className="text-xs text-[#64748b] ml-3">
                    {m.size ? `${(m.size / 1e9).toFixed(1)} GB` : ''} | {m.parameter_size} | {m.quantization}
                  </span>
                )}
                {m.installed === false && (
                  <p className="text-xs text-amber-400/80 mt-1">
                    {m.name} is not installed in the local Ollama environment.
                  </p>
                )}
              </div>
              {m.installed === false ? (
                <span className="text-xs text-[#64748b] flex items-center gap-1">Not installed</span>
              ) : m.registered ? (
                <span className="text-xs text-emerald-400 flex items-center gap-1"><Check size={12} /> Registered</span>
              ) : (
                <button
                  onClick={() => handleRegister(m)}
                  className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                >
                  <Zap size={12} /> Register
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
