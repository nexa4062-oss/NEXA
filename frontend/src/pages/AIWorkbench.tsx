import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, Paperclip, X, FileText, Trash2, Download } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'
import { useWorkbenchStore, type Message } from '../store/workbench'

const ACCEPTED_TYPES = '.pptx,.ppt,.pdf,.docx,.txt,.md,.xlsx,.xlsm,.xls,.csv,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp'

export default function AIWorkbench() {
  const {
    messages, input, attachments, currentModel, currentTask, language,
    setMessages, setInput, setAttachments, setCurrentModel, setCurrentTask, setLanguage, clearConversation,
  } = useWorkbenchStore()
  const [isStreaming, setIsStreaming] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    for (const file of files) {
      setIsUploading(true)
      try {
        const form = new FormData()
        form.append('file', file)
        form.append('classification', 'INTERNAL')
        const uploadRes = await api.post('/documents/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        const documentId = uploadRes.data.id

        // Index it so its content becomes searchable by RAG for this chat.
        await api.post(`/knowledge/index/${documentId}`)

        setAttachments(prev => [...prev, {
          document_id: documentId,
          filename: file.name,
          mime_type: file.type || 'application/octet-stream',
        }])
        toast.success(`${file.name} attached`)
      } catch (err: any) {
        toast.error(err.response?.data?.detail || `Failed to upload ${file.name}`)
      } finally {
        setIsUploading(false)
      }
    }
  }

  const removeAttachment = (documentId: string) => {
    setAttachments(prev => prev.filter(a => a.document_id !== documentId))
  }

  const sendMessage = async () => {
    if ((!input.trim() && attachments.length === 0) || isStreaming) return

    const attachedNames = attachments.map(a => a.filename)
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: attachedNames.length
        ? `${input}${input ? '\n\n' : ''}[Attached: ${attachedNames.join(', ')}]`
        : input,
    }
    setMessages(prev => [...prev, userMsg])
    const pendingAttachments = attachments
    setInput('')
    setAttachments([])
    setIsStreaming(true)

    try {
      const response = await fetch('/api/agents/execute/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          query: input,
          mode: 'balanced',
          enable_rag: true,
          language: language || undefined,
          attachments: pendingAttachments.map(a => ({
            document_id: a.document_id,
            filename: a.filename,
            mime_type: a.mime_type,
          })),
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantContent = ''
      const assistantId = (Date.now() + 1).toString()

      setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') break

          try {
            const event = JSON.parse(data)
            if (event.type === 'token') {
              assistantContent += event.content
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: assistantContent } : m
              ))
            } else if (event.type === 'status') {
              setCurrentTask(event.phase || '')
              setCurrentModel(event.message || '')
            } else if (event.type === 'done') {
              setCurrentModel(event.model_used || '')
              setCurrentTask(event.task_type || '')
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, model: event.model_used, taskType: event.task_type, generatedFile: event.generated_file || undefined } : m
              ))
            } else if (event.type === 'denied') {
              setCurrentTask('permission_check')
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: event.message || 'Permission denied for this request.' } : m
              ))
              toast.error(`Blocked: missing '${event.missing_permission}' permission`)
            } else if (event.type === 'approval_required') {
              setCurrentTask('hitl_gate')
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? {
                  ...m,
                  content: `Waiting for Human Approval — this action (${event.task_type}) requires sign-off before it runs. An authorized approver can approve or reject it from Administration → Agentic AI.`,
                } : m
              ))
              toast('Waiting for human approval', { icon: '🟡' })
            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: event.message || 'Something went wrong.' } : m
              ))
            }
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: 'Error: Failed to get response. Check if the backend and Ollama are running.'
      }])
    } finally {
      setIsStreaming(false)
    }
  }

  const downloadGeneratedFile = async (file: { filename: string; download_url: string }) => {
    try {
      // download_url from the API already includes the '/api' prefix, but
      // the axios client's baseURL is also '/api' - strip it to avoid
      // doubling, same pattern as FileGeneration.tsx's download button.
      const path = file.download_url.replace(/^\/api/, '')
      const res = await api.get(path, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = file.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download the generated file')
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">AI Workbench</h1>
          <p className="text-sm text-[#64748b]">Local AI assistant with secure RAG</p>
        </div>
        {currentModel && (
          <div className="flex items-center gap-3">
            <div className="text-xs text-[#94a3b8] bg-[#111827] border border-[#334155] rounded px-2 py-1 font-mono">
              Model: {currentModel}
            </div>
            {currentTask && (
              <div className="text-xs text-cyan-400 bg-cyan-400/10 border border-cyan-400/30 rounded px-2 py-1 font-mono">
                {currentTask}
              </div>
            )}
          </div>
        )}
        {messages.length > 0 && (
          <button
            onClick={clearConversation}
            disabled={isStreaming}
            title="Clear this conversation"
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[#64748b] hover:text-red-400 border border-[#334155] hover:border-red-400/40 rounded transition-colors disabled:opacity-50"
          >
            <Trash2 size={12} /> New chat
          </button>
        )}
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          title="Language the assistant should reply in"
          className="px-2.5 py-1.5 bg-[#111827] border border-[#334155] rounded text-xs text-[#94a3b8] focus:border-cyan-400 focus:outline-none"
        >
          <option value="">Reply language: Auto</option>
          <option value="Hindi">हिन्दी Hindi</option>
          <option value="Tamil">தமிழ் Tamil</option>
          <option value="Telugu">తెలుగు Telugu</option>
          <option value="Kannada">ಕನ್ನಡ Kannada</option>
          <option value="Malayalam">മലയാളം Malayalam</option>
          <option value="Bengali">বাংলা Bengali</option>
          <option value="Marathi">मराठी Marathi</option>
          <option value="Gujarati">ગુજરાતી Gujarati</option>
          <option value="Punjabi">ਪੰਜਾਬੀ Punjabi</option>
          <option value="Spanish">Español Spanish</option>
          <option value="French">Français French</option>
          <option value="German">Deutsch German</option>
          <option value="Arabic">العربية Arabic</option>
          <option value="Chinese">中文 Chinese</option>
          <option value="Japanese">日本語 Japanese</option>
          <option value="English">English</option>
        </select>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto bg-[#111827] border border-[#334155] rounded-lg p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-[#64748b] py-16">
            <p className="text-lg mb-2">Ask anything</p>
            <p className="text-sm">Questions, document analysis, coding tasks, file generation</p>
            <p className="text-xs mt-2 text-[#64748b]">Attach a PPT, PDF, Word doc, Excel sheet, text file, or an image (photo, handwritten note, engineering drawing) with the paperclip button — images are analyzed directly by a local vision model via Ollama</p>
            <p className="text-xs mt-4">The system will automatically route to the best available model</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg px-4 py-3 ${
              msg.role === 'user'
                ? 'bg-cyan-400/10 border border-cyan-400/30 text-[#f1f5f9]'
                : 'bg-[#1a2332] border border-[#334155] text-[#e2e8f0]'
            }`}>
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              {msg.generatedFile && (
                <button
                  onClick={() => downloadGeneratedFile(msg.generatedFile!)}
                  className="mt-3 flex items-center gap-2 text-xs font-mono px-3 py-2 rounded-lg bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 hover:bg-cyan-400/20 transition-colors"
                >
                  <Download size={14} />
                  {msg.generatedFile.filename} ({(msg.generatedFile.size / 1024).toFixed(1)} KB) — Download
                </button>
              )}
              {msg.model && (
                <p className="text-xs text-[#64748b] mt-2 font-mono">
                  via {msg.model} | {msg.taskType}
                </p>
              )}
            </div>
          </div>
        ))}
        {isStreaming && (
          <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
            <Loader2 size={14} className="animate-spin" />
            <span>Generating...</span>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      {/* Attachments */}
      {attachments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {attachments.map((a) => (
            <div
              key={a.document_id}
              className="flex items-center gap-2 text-xs bg-[#111827] border border-[#334155] rounded-full pl-3 pr-2 py-1.5 text-[#e2e8f0]"
            >
              <FileText size={12} className="text-cyan-400" />
              <span className="max-w-[160px] truncate">{a.filename}</span>
              <button
                onClick={() => removeAttachment(a.document_id)}
                className="text-[#64748b] hover:text-red-400"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="mt-4 flex gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={handleFileSelect}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isStreaming || isUploading}
          title="Attach a PPT, PDF, Word doc, Excel sheet, text file, or image (analyzed by a local vision model)"
          className="px-3 py-3 bg-[#111827] border border-[#334155] rounded-lg text-[#94a3b8] hover:text-cyan-400 hover:border-cyan-400/50 transition-colors disabled:opacity-50"
        >
          {isUploading ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
        </button>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          placeholder="Ask a question, analyze a document, write code..."
          className="flex-1 px-4 py-3 bg-[#111827] border border-[#334155] rounded-lg text-sm text-[#f1f5f9] focus:border-cyan-400 focus:outline-none"
          disabled={isStreaming}
        />
        <button
          onClick={sendMessage}
          disabled={isStreaming || (!input.trim() && attachments.length === 0)}
          className="px-4 py-3 bg-cyan-400/20 border border-cyan-400/30 rounded-lg text-cyan-400 hover:bg-cyan-400/30 transition-colors disabled:opacity-50"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
