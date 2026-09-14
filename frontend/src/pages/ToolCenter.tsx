import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Wrench, Calculator, Play } from 'lucide-react'
import api from '../services/api'

export default function ToolCenter() {
  const [expression, setExpression] = useState('')
  const [calcResult, setCalcResult] = useState<any>(null)

  const { data: toolsData, isLoading } = useQuery({
    queryKey: ['tools-available'],
    queryFn: async () => (await api.get('/tools/available')).data,
  })

  const calcMutation = useMutation({
    mutationFn: async (expr: string) => (await api.post('/tools/calculate', { expression: expr })).data,
    onSuccess: (data) => setCalcResult(data),
  })

  const handleCalculate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!expression.trim()) return
    calcMutation.mutate(expression)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Wrench className="text-cyan-400" size={22} />
        <h1 className="text-xl font-bold text-[#f1f5f9]">Tool Center</h1>
      </div>

      <div className="bg-[#111827] border border-[#334155] rounded-lg p-5 mb-6">
        <h2 className="text-sm font-semibold text-[#f1f5f9] mb-3">Available Tools</h2>
        {isLoading && <p className="text-sm text-[#64748b]">Loading tools...</p>}
        {!isLoading && (!toolsData?.tools || toolsData.tools.length === 0) && (
          <p className="text-sm text-[#64748b]">No tools registered.</p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {toolsData?.tools?.map((t: any) => (
            <div key={t.id} className="bg-[#0a0e17] border border-[#334155] rounded p-3">
              <div className="text-sm font-medium text-cyan-400">{t.name}</div>
              <div className="text-xs text-[#64748b] mt-1">{t.description}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-[#111827] border border-[#334155] rounded-lg p-5">
        <div className="flex items-center gap-2 mb-3">
          <Calculator className="text-cyan-400" size={16} />
          <h2 className="text-sm font-semibold text-[#f1f5f9]">Calculator</h2>
        </div>
        <form onSubmit={handleCalculate} className="flex gap-2">
          <input
            type="text" value={expression} onChange={e => setExpression(e.target.value)}
            placeholder="e.g. (120 * 4) / 3"
            className="flex-1 px-3 py-2 bg-[#0a0e17] border border-[#334155] rounded text-[#f1f5f9] text-sm focus:border-cyan-400 focus:outline-none"
          />
          <button type="submit" disabled={calcMutation.isPending}
            className="px-4 py-2 bg-cyan-400/20 text-cyan-400 border border-cyan-400/30 rounded text-sm font-medium hover:bg-cyan-400/30 transition-colors flex items-center gap-2 disabled:opacity-50">
            <Play size={14} /> Run
          </button>
        </form>
        {calcResult && (
          <div className={`mt-3 p-3 rounded text-sm font-mono ${calcResult.success ? 'bg-emerald-400/10 border border-emerald-400/30 text-emerald-400' : 'bg-red-400/10 border border-red-400/30 text-red-400'}`}>
            {calcResult.success ? `= ${calcResult.result}` : `Error: ${calcResult.error}`}
          </div>
        )}
      </div>
    </div>
  )
}
