import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload, Search, FileText, Loader2 } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'

export default function KnowledgeCenter() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const queryClient = useQueryClient()

  const { data: stats } = useQuery({
    queryKey: ['knowledge-stats'],
    queryFn: () => api.get('/knowledge/stats').then(r => r.data),
  })

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      form.append('classification', 'INTERNAL')
      return api.post('/documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: (res) => {
      toast.success('Document uploaded successfully')
      // Trigger indexing
      api.post(`/knowledge/index/${res.data.id}`)
      queryClient.invalidateQueries({ queryKey: ['knowledge-stats'] })
    },
    onError: () => toast.error('Upload failed'),
  })

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setIsSearching(true)
    try {
      const res = await api.get('/knowledge/search', { params: { query: searchQuery } })
      setSearchResults(res.data.results)
    } catch {
      toast.error('Search failed')
    } finally {
      setIsSearching(false)
    }
  }

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    files.forEach(f => uploadMutation.mutate(f))
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">Knowledge Center</h1>
        <p className="text-sm text-[#64748b]">Organizational knowledge base with secure indexing</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-cyan-400 font-mono">{stats?.indexed_documents || 0}</p>
          <p className="text-xs text-[#94a3b8] mt-1">Indexed Documents</p>
        </div>
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-cyan-400 font-mono">{stats?.total_chunks || 0}</p>
          <p className="text-xs text-[#94a3b8] mt-1">Knowledge Chunks</p>
        </div>
        <div className="bg-[#111827] border border-[#334155] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400 font-mono">SECURE</p>
          <p className="text-xs text-[#94a3b8] mt-1">RAG Mode</p>
        </div>
      </div>

      {/* Upload Zone */}
      <div
        onDrop={handleFileDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border-2 border-dashed border-[#334155] rounded-lg p-8 text-center hover:border-cyan-400/50 transition-colors cursor-pointer"
        onClick={() => {
          const input = document.createElement('input')
          input.type = 'file'
          input.multiple = true
          input.accept = '.pdf,.docx,.txt,.md,.png,.jpg'
          input.onchange = (e) => {
            const files = Array.from((e.target as HTMLInputElement).files || [])
            files.forEach(f => uploadMutation.mutate(f))
          }
          input.click()
        }}
      >
        <Upload className="mx-auto text-[#64748b] mb-2" size={32} />
        <p className="text-sm text-[#94a3b8]">Drop files here or click to upload</p>
        <p className="text-xs text-[#64748b] mt-1">PDF, DOCX, TXT, images supported</p>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Search knowledge base..."
          className="flex-1 px-4 py-2.5 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9] focus:border-cyan-400 focus:outline-none"
        />
        <button
          onClick={handleSearch}
          disabled={isSearching}
          className="px-4 py-2.5 bg-cyan-400/20 border border-cyan-400/30 rounded text-cyan-400 hover:bg-cyan-400/30 transition-colors"
        >
          {isSearching ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
        </button>
      </div>

      {/* Results */}
      {searchResults.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-[#f1f5f9]">Results ({searchResults.length})</h3>
          {searchResults.map((r) => (
            <div key={r.chunk_id} className="bg-[#111827] border border-[#334155] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText size={14} className="text-cyan-400" />
                <span className="text-xs text-[#94a3b8] font-mono">
                  Page {r.page_number || 'N/A'} {r.section && `| ${r.section}`}
                </span>
              </div>
              <p className="text-sm text-[#e2e8f0]">{r.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
