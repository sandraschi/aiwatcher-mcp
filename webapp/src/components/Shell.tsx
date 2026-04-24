import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Newspaper, Rss, Mail, Settings,
  ChevronLeft, ChevronRight, Radio, LayoutGrid, Wrench, HelpCircle,
} from 'lucide-react'
import clsx from 'clsx'
import { StatusBar } from './StatusBar'

const NAV = [
  { to: '/',         label: 'Dashboard', icon: LayoutDashboard },
  { to: '/news',     label: 'News Feed',  icon: Newspaper },
  { to: '/feeds',    label: 'Sources',    icon: Rss },
  { to: '/digest',   label: 'Digest',     icon: Mail },
  { to: '/apps',     label: 'Fleet Apps', icon: LayoutGrid },
  { to: '/tools',    label: 'Tools',      icon: Wrench },
  { to: '/help',     label: 'Docs',       icon: HelpCircle },
  { to: '/settings', label: 'Settings',   icon: Settings },
]

export function Shell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <motion.aside
        animate={{ width: collapsed ? 64 : 220 }}
        transition={{ type: 'spring', stiffness: 400, damping: 40 }}
        className="flex-shrink-0 flex flex-col border-r"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)', zIndex: 40 }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{ background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)' }}>
            <Radio className="w-4 h-4" style={{ color: 'var(--accent-amber)' }} />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                className="overflow-hidden"
              >
                <div className="text-sm font-semibold leading-tight" style={{ color: 'var(--text-primary)' }}>
                  AIWatcher
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>v0.1.0</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-2 flex flex-col gap-0.5 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
                isActive ? '' : 'hover:bg-zinc-800',
              )}
              style={({ isActive }) => isActive ? {
                background: 'rgba(245,158,11,0.12)',
                color: 'var(--accent-amber)',
              } : { color: 'var(--text-secondary)' }}
              title={collapsed ? label : undefined}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="truncate"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>
            </NavLink>
          ))}
        </nav>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="m-3 p-2 rounded-lg flex items-center justify-center transition-colors hover:bg-zinc-800"
          style={{ color: 'var(--text-muted)' }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </motion.aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <StatusBar />
        <main className="flex-1 overflow-y-auto p-6">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  )
}
