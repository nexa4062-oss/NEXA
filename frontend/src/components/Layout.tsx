import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import {
  LayoutDashboard, MessageSquare, Database, FileText, Cpu,
  Code, FileOutput, Shield, Activity, Settings, HardDrive, LogOut,
  Wrench, Mic
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Command Center' },
  { path: '/workbench', icon: MessageSquare, label: 'AI Workbench' },
  { path: '/knowledge', icon: Database, label: 'Knowledge Center' },
  { path: '/documents', icon: FileText, label: 'Documents' },
  { path: '/models', icon: Cpu, label: 'Model Control' },
  { path: '/code', icon: Code, label: 'Code Laboratory' },
  { path: '/tools', icon: Wrench, label: 'Tool Center' },
  { path: '/audio', icon: Mic, label: 'Audio Transcription' },
  { path: '/generate', icon: FileOutput, label: 'File Generation' },
  { path: '/sovereignty', icon: Shield, label: 'Sovereignty Monitor' },
  { path: '/audit', icon: Activity, label: 'Audit Center' },
  { path: '/hardware', icon: HardDrive, label: 'Hardware' },
  { path: '/admin', icon: Settings, label: 'Administration' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#111827] border-r border-[#334155] flex flex-col shrink-0">
        <div className="p-4 border-b border-[#334155]">
          <h1 className="text-sm font-bold text-cyan-400 tracking-wide uppercase">Sovereign AI</h1>
          <p className="text-xs text-[#64748b] mt-0.5">Workbench v1.0</p>
        </div>

        <nav className="flex-1 py-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-cyan-400/10 text-cyan-400 border-r-2 border-cyan-400'
                  : 'text-[#94a3b8] hover:bg-[#1a2332] hover:text-[#f1f5f9]'
              )}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-[#334155]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-cyan-400/20 flex items-center justify-center text-xs text-cyan-400 font-bold">
              {user?.display_name?.charAt(0) || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[#f1f5f9] truncate">{user?.display_name || 'User'}</p>
              <p className="text-xs text-[#64748b] truncate">{user?.role_display || user?.role}</p>
            </div>
            <button onClick={handleLogout} className="text-[#64748b] hover:text-red-400 transition-colors">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-[#0a0e17]">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
