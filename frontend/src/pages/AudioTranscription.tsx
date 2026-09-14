import { useState, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Mic, Upload, AlertTriangle } from 'lucide-react'
import api from '../services/api'

export default function AudioTranscription() {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: status } = useQuery({
    queryKey: ['audio-status'],
    queryFn: async () => (await api.get('/audio/status')).data,
    refetchInterval: 30000,
  })

  const transcribeMutation = useMutation({
    mutationFn: async (f: File) => {
      const formData = new FormData()
      formData.append('file', f)
      return (await api.post('/audio/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })).data
    },
    onSuccess: (data) => setResult(data),
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setResult(null)
    }
  }

  const handleTranscribe = () => {
    if (file) transcribeMutation.mutate(file)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Mic className="text-cyan-400" size={22} />
        <h1 className="text-xl font-bold text-[#f1f5f9]">Audio Transcription</h1>
      </div>

      {status && !status.available && (
        <div className="mb-6 p-4 bg-amber-400/10 border border-amber-400/30 rounded-lg flex gap-3">
          <AlertTriangle className="text-amber-400 shrink-0 mt-0.5" size={18} />
          <div>
            <p className="text-sm font-medium text-amber-400">Local transcription model unavailable</p>
            <p className="text-xs text-[#94a3b8] mt-1">{status.reason}</p>
          </div>
        </div>
      )}

      <div className="bg-[#111827] border border-[#334155] rounded-lg p-6">
        <input
          ref={fileInputRef} type="file" accept="audio/*" onChange={handleFileSelect}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="w-full py-8 border-2 border-dashed border-[#334155] rounded-lg flex flex-col items-center gap-2 hover:border-cyan-400/50 transition-colors"
        >
          <Upload className="text-[#64748b]" size={24} />
          <span className="text-sm text-[#94a3b8]">
            {file ? file.name : 'Click to select an audio file (wav, mp3, m4a...)'}
          </span>
        </button>

        <button
          onClick={handleTranscribe}
          disabled={!file || transcribeMutation.isPending || status?.available === false}
          className="w-full mt-4 py-2.5 bg-cyan-400/20 text-cyan-400 border border-cyan-400/30 rounded text-sm font-medium hover:bg-cyan-400/30 transition-colors disabled:opacity-40"
        >
          {transcribeMutation.isPending ? 'Transcribing locally...' : 'Transcribe'}
        </button>

        {result && (
          <div className="mt-5">
            {result.success ? (
              <>
                <p className="text-xs text-[#64748b] uppercase tracking-wide mb-2">
                  Transcript {result.language ? `(detected: ${result.language})` : ''}
                </p>
                <div className="bg-[#0a0e17] border border-[#334155] rounded p-4 text-sm text-[#f1f5f9] whitespace-pre-wrap">
                  {result.text || '(no speech detected)'}
                </div>
                {result.segments?.length > 0 && (
                  <div className="mt-3 space-y-1 max-h-48 overflow-y-auto">
                    {result.segments.map((s: any, i: number) => (
                      <div key={i} className="text-xs text-[#64748b] flex gap-2">
                        <span className="font-mono text-[#475569] shrink-0">
                          {s.start.toFixed(1)}s–{s.end.toFixed(1)}s
                        </span>
                        <span>{s.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="p-3 bg-red-400/10 border border-red-400/30 rounded text-red-400 text-sm">
                {result.error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
