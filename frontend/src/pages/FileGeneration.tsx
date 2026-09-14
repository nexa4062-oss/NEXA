import { useState } from 'react'
import { FileText, Download, Loader2 } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'

export default function FileGeneration() {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [format, setFormat] = useState('docx')
  const [classification, setClassification] = useState('INTERNAL')
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedFile, setGeneratedFile] = useState<any>(null)

  const generate = async () => {
    if (!title.trim() || !content.trim()) {
      toast.error('Title and content are required')
      return
    }
    setIsGenerating(true)
    try {
      const res = await api.post('/generation/generate', { title, content, format, classification })
      setGeneratedFile(res.data)
      toast.success('File generated successfully')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Generation failed')
    } finally {
      setIsGenerating(false)
    }
  }

  const download = async () => {
    if (!generatedFile?.download_url) return
    try {
      // window.open()/plain navigation does not send the Authorization header,
      // so the protected download endpoint returns an unauthenticated (blank)
      // response. Fetch it through the authenticated api client instead and
      // save the blob ourselves.
      // download_url from the API already includes the '/api' prefix, but the
      // `api` client's baseURL is '/api' too - strip it here to avoid a
      // doubled '/api/api/...' path.
      const path = generatedFile.download_url.replace(/^\/api/, '')
      const res = await api.get(path, { responseType: 'blob' })
      const blobUrl = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = generatedFile.filename || 'download'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(blobUrl)
    } catch (err) {
      toast.error('Download failed')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">File Generation</h1>
        <p className="text-sm text-[#64748b]">Generate DOCX, PPTX, XLSX, PDF documents</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2.5 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9] focus:border-cyan-400 focus:outline-none"
              placeholder="Document title"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full px-3 py-2.5 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9]"
              >
                <option value="docx">Word (.docx)</option>
                <option value="pptx">PowerPoint (.pptx)</option>
                <option value="xlsx">Excel (.xlsx)</option>
                <option value="pdf">PDF (.pdf)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Classification</label>
              <select
                value={classification}
                onChange={(e) => setClassification(e.target.value)}
                className="w-full px-3 py-2.5 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9]"
              >
                <option value="PUBLIC">Public</option>
                <option value="INTERNAL">Internal</option>
                <option value="CONFIDENTIAL">Confidential</option>
                <option value="RESTRICTED">Restricted</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-[#94a3b8] uppercase tracking-wide mb-1.5">Content</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={10}
              className="w-full px-3 py-2.5 bg-[#111827] border border-[#334155] rounded text-sm text-[#f1f5f9] resize-none focus:border-cyan-400 focus:outline-none"
              placeholder="Enter document content..."
            />
          </div>

          <button
            onClick={generate}
            disabled={isGenerating}
            className="flex items-center gap-2 px-4 py-2.5 bg-cyan-400/20 border border-cyan-400/30 rounded text-sm text-cyan-400 hover:bg-cyan-400/30 transition-colors disabled:opacity-50"
          >
            {isGenerating ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
            Generate {format.toUpperCase()}
          </button>
        </div>

        <div>
          <h3 className="text-sm font-medium text-[#f1f5f9] mb-3">Generated File</h3>
          {generatedFile ? (
            <div className="bg-[#111827] border border-[#334155] rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <FileText className="text-cyan-400" size={20} />
                <span className="text-sm text-[#f1f5f9]">{generatedFile.filename}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-[#94a3b8]">
                <div>Format: <span className="text-[#f1f5f9] font-mono">{generatedFile.format}</span></div>
                <div>Size: <span className="text-[#f1f5f9] font-mono">{(generatedFile.size / 1024).toFixed(1)} KB</span></div>
                <div>Classification: <span className="text-[#f1f5f9] font-mono">{generatedFile.classification}</span></div>
              </div>
              <button
                onClick={download}
                className="flex items-center gap-2 px-3 py-2 bg-emerald-400/20 border border-emerald-400/30 rounded text-xs text-emerald-400 hover:bg-emerald-400/30"
              >
                <Download size={14} /> Download
              </button>
            </div>
          ) : (
            <div className="bg-[#111827] border border-[#334155] rounded-lg p-8 text-center text-[#64748b] text-sm">
              Generate a file to see it here
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
