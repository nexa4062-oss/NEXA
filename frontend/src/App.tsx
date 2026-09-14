import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuth } from './store/auth'
import Login from './pages/Login'
import EmployeeIdentify from './pages/EmployeeIdentify'
import ToolCenter from './pages/ToolCenter'
import AudioTranscription from './pages/AudioTranscription'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AIWorkbench from './pages/AIWorkbench'
import KnowledgeCenter from './pages/KnowledgeCenter'
import Documents from './pages/Documents'
import ModelControl from './pages/ModelControl'
import CodeLab from './pages/CodeLab'
import FileGeneration from './pages/FileGeneration'
import AuditCenter from './pages/AuditCenter'
import SovereigntyMonitor from './pages/SovereigntyMonitor'
import Administration from './pages/Administration'
import Hardware from './pages/Hardware'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/identify" replace />
  return <>{children}</>
}

export default function App() {
  const { isAuthenticated, fetchUser } = useAuth()

  useEffect(() => {
    if (isAuthenticated) fetchUser()
  }, [isAuthenticated])

  return (
    <Routes>
      <Route path="/identify" element={<EmployeeIdentify />} />
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="workbench" element={<AIWorkbench />} />
        <Route path="knowledge" element={<KnowledgeCenter />} />
        <Route path="documents" element={<Documents />} />
        <Route path="models" element={<ModelControl />} />
        <Route path="code" element={<CodeLab />} />
        <Route path="tools" element={<ToolCenter />} />
        <Route path="audio" element={<AudioTranscription />} />
        <Route path="generate" element={<FileGeneration />} />
        <Route path="audit" element={<AuditCenter />} />
        <Route path="sovereignty" element={<SovereigntyMonitor />} />
        <Route path="admin" element={<Administration />} />
        <Route path="hardware" element={<Hardware />} />
      </Route>
    </Routes>
  )
}
