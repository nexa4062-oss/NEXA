import { useState } from 'react'
import { Play, Loader2, Bug } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'

const STARTER_CODE = `def calculate_average(numbers):
    total = 0
    for i in range(1, len(numbers)):
        total += numbers[i]
    return total / len(numbers)

print(calculate_average([10, 20, 30, 40]))`

export default function CodeLab() {
  const [code, setCode] = useState(STARTER_CODE)
  const [language, setLanguage] = useState('python')
  const [stdin, setStdin] = useState('')
  const [issueDescription, setIssueDescription] = useState('')
  const [output, setOutput] = useState('')
  const [error, setError] = useState('')
  const [prompts, setPrompts] = useState<string[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [isDebugging, setIsDebugging] = useState(false)
  const [execTime, setExecTime] = useState(0)
  const [debugAnalysis, setDebugAnalysis] = useState('')
  const [debugModel, setDebugModel] = useState('')
  const [debugNotice, setDebugNotice] = useState('')

  const execute = async () => {
    if (!code.trim() || isRunning) return
    setIsRunning(true)
    setOutput('')
    setError('')
    setDebugAnalysis('')
    setDebugNotice('')

    try {
      const res = await api.post('/sandbox/execute', { code, language, stdin })
      setOutput(res.data.output || '')
      setError(res.data.error || '')
      setPrompts(res.data.prompts || [])
      setExecTime(res.data.execution_time_ms || 0)
      if (!res.data.success) {
        toast.error('Execution failed')
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Execution failed')
      setPrompts([])
      toast.error('Execution error')
    } finally {
      setIsRunning(false)
    }
  }

  const debugCode = async () => {
    if (!code.trim() || isDebugging) return
    setIsDebugging(true)
    setDebugAnalysis('')
    setDebugNotice('')

    try {
      const res = await api.post('/sandbox/debug', {
        code, language, stdin, issue_description: issueDescription || undefined,
      })
      setOutput(res.data.execution?.output || '')
      setError(res.data.execution?.error || '')
      setPrompts(res.data.execution?.prompts || [])
      setExecTime(res.data.execution?.execution_time_ms || 0)
      if (res.data.analysis) {
        setDebugAnalysis(res.data.analysis)
        setDebugModel(res.data.model_used || '')
      } else {
        setDebugNotice(res.data.error || 'AI analysis unavailable.')
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Debug request failed')
    } finally {
      setIsDebugging(false)
    }
  }

  return (
    <div className="space-y-4 h-[calc(100vh-3rem)] flex flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Code Laboratory</h1>
          <p className="text-sm text-[#64748b]">Sandboxed code execution</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="px-3 py-1.5 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9]"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="bash">Bash</option>
          </select>
          <button
            onClick={execute}
            disabled={isRunning || isDebugging}
            className="flex items-center gap-2 px-4 py-1.5 bg-emerald-400/20 border border-emerald-400/30 rounded text-sm text-emerald-400 hover:bg-emerald-400/30 transition-colors disabled:opacity-50"
          >
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Run
          </button>
          <button
            onClick={debugCode}
            disabled={isRunning || isDebugging}
            title="Run the code and have a local AI coding model explain what's wrong and propose a fix"
            className="flex items-center gap-2 px-4 py-1.5 bg-cyan-400/20 border border-cyan-400/30 rounded text-sm text-cyan-400 hover:bg-cyan-400/30 transition-colors disabled:opacity-50"
          >
            {isDebugging ? <Loader2 size={14} className="animate-spin" /> : <Bug size={14} />}
            Debug
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        {/* Editor */}
        <div className="flex flex-col gap-2 min-h-0">
          <div className="text-xs text-[#94a3b8] uppercase tracking-wide px-1">Editor</div>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="flex-1 p-4 bg-[#111827] border border-[#334155] rounded-lg font-mono text-sm text-[#f1f5f9] resize-none focus:border-cyan-400 focus:outline-none min-h-0"
            spellCheck={false}
          />
          <div>
            <div className="flex items-center justify-between mb-1 px-1">
              <span className="text-xs text-[#94a3b8] uppercase tracking-wide">
                Stdin (one value per line, for input())
              </span>
            </div>
            {prompts.length > 0 && (
              <div className="mb-1.5 px-1">
                <p className="text-[10px] text-cyan-400/80 uppercase tracking-wide mb-1">
                  This program asked for:
                </p>
                <ul className="space-y-0.5">
                  {prompts.map((p, i) => (
                    <li key={i} className="text-xs text-[#94a3b8]">
                      {i + 1}. <span className="text-[#e2e8f0]">{p.trim() || '(no prompt text)'}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <textarea
              value={stdin}
              onChange={(e) => setStdin(e.target.value)}
              placeholder={'e.g.\nAlice\n25'}
              rows={3}
              className="w-full p-3 bg-[#111827] border border-[#334155] rounded-lg font-mono text-xs text-[#f1f5f9] resize-none focus:border-cyan-400 focus:outline-none"
              spellCheck={false}
            />
          </div>
          <div>
            <div className="text-xs text-[#94a3b8] uppercase tracking-wide px-1 mb-1">
              What's wrong? (optional, helps Debug)
            </div>
            <input
              type="text"
              value={issueDescription}
              onChange={(e) => setIssueDescription(e.target.value)}
              placeholder="e.g. should print the average but the number looks wrong"
              className="w-full px-3 py-2 bg-[#111827] border border-[#334155] rounded-lg text-xs text-[#f1f5f9] focus:border-cyan-400 focus:outline-none"
            />
          </div>
        </div>

        {/* Output */}
        <div className="flex flex-col min-h-0 gap-3">
          <div className="flex flex-col" style={{ flex: debugAnalysis || debugNotice ? '0 0 40%' : '1 1 auto' }}>
            <div className="flex items-center justify-between mb-1 px-1">
              <span className="text-xs text-[#94a3b8] uppercase tracking-wide">Output</span>
              {execTime > 0 && (
                <span className="text-xs text-[#64748b] font-mono">{execTime}ms</span>
              )}
            </div>
            <div className="flex-1 p-4 bg-[#111827] border border-[#334155] rounded-lg font-mono text-sm overflow-auto">
              {output && <pre className="text-emerald-400 whitespace-pre-wrap">{output}</pre>}
              {error && <pre className="text-red-400 whitespace-pre-wrap">{error}</pre>}
              {!output && !error && (
                <span className="text-[#64748b]">Run or Debug code to see output</span>
              )}
            </div>
          </div>

          {(debugAnalysis || debugNotice) && (
            <div className="flex flex-col flex-1 min-h-0">
              <div className="flex items-center justify-between mb-1 px-1">
                <span className="text-xs text-[#94a3b8] uppercase tracking-wide">AI Debug Analysis</span>
                {debugModel && (
                  <span className="text-xs text-cyan-400 font-mono">via {debugModel}</span>
                )}
              </div>
              <div className="flex-1 p-4 bg-[#111827] border border-cyan-400/20 rounded-lg text-sm overflow-auto">
                {debugAnalysis && (
                  <pre className="text-[#e2e8f0] whitespace-pre-wrap font-mono text-xs">{debugAnalysis}</pre>
                )}
                {debugNotice && (
                  <p className="text-amber-400 text-xs">{debugNotice}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
