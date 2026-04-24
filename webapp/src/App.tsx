import { Routes, Route } from 'react-router-dom'
import { Shell } from './components/Shell'
import { Dashboard } from './pages/Dashboard'
import { NewsPage } from './pages/NewsPage'
import { FeedsPage } from './pages/FeedsPage'
import { DigestPage } from './pages/DigestPage'
import { AppsPage } from './pages/AppsPage'
import { ToolsPage } from './pages/ToolsPage'
import { HelpPage } from './pages/HelpPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/feeds" element={<FeedsPage />} />
        <Route path="/digest" element={<DigestPage />} />
        <Route path="/apps" element={<AppsPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Shell>
  )
}
