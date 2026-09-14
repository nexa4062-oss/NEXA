import { useQuery } from '@tanstack/react-query'
import { FileText, Lock, Globe } from 'lucide-react'
import api from '../services/api'

const classColors: Record<string, string> = {
  public: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  internal: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  confidential: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
  restricted: 'text-red-400 bg-red-400/10 border-red-400/30',
  highly_restricted: 'text-red-500 bg-red-500/10 border-red-500/30',
}

export default function Documents() {
  const { data, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.get('/documents/').then(r => r.data),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">Documents</h1>
        <p className="text-sm text-[#64748b]">Only showing documents you are authorized to access</p>
      </div>

      {isLoading ? (
        <p className="text-[#64748b]">Loading...</p>
      ) : (
        <div className="bg-[#111827] border border-[#334155] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#334155] text-[#94a3b8] text-xs uppercase tracking-wide">
                <th className="text-left p-3">Document</th>
                <th className="text-left p-3">Type</th>
                <th className="text-left p-3">Classification</th>
                <th className="text-left p-3">Size</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Date</th>
              </tr>
            </thead>
            <tbody>
              {data?.documents?.map((doc: any) => (
                <tr key={doc.id} className="border-b border-[#334155]/50 hover:bg-[#1a2332] transition-colors">
                  <td className="p-3 flex items-center gap-2">
                    <FileText size={16} className="text-cyan-400" />
                    <span className="text-[#f1f5f9]">{doc.filename}</span>
                  </td>
                  <td className="p-3 text-[#94a3b8] font-mono text-xs">{doc.mime_type?.split('/')[1] || 'unknown'}</td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs ${classColors[doc.classification] || classColors.internal}`}>
                      {doc.classification === 'public' ? <Globe size={10} /> : <Lock size={10} />}
                      {doc.classification?.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-3 text-[#94a3b8] font-mono text-xs">
                    {doc.size ? `${(doc.size / 1024).toFixed(1)} KB` : 'N/A'}
                  </td>
                  <td className="p-3">
                    <span className={`text-xs ${doc.is_indexed ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {doc.is_indexed ? 'Indexed' : 'Pending'}
                    </span>
                  </td>
                  <td className="p-3 text-[#94a3b8] text-xs font-mono">
                    {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'N/A'}
                  </td>
                </tr>
              ))}
              {(!data?.documents || data.documents.length === 0) && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-[#64748b]">
                    No documents available. Upload documents through the Knowledge Center.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
