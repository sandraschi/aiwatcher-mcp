import { Route, Routes } from "react-router-dom";
import FloatingChat from "./components/FloatingChat";
import { Shell } from "./components/Shell";
import { AppsPage } from "./pages/AppsPage";
import { BundlesPage } from "./pages/BundlesPage";
import ChatPage from "./pages/ChatPage";
import { Dashboard } from "./pages/Dashboard";
import { DigestPage } from "./pages/DigestPage";
import { FeedsPage } from "./pages/FeedsPage";
import { HelpPage } from "./pages/HelpPage";
import { HuggingFacePage } from "./pages/HuggingFacePage";
import { LogsPage } from "./pages/LogsPage";
import { MorningNewsPage } from "./pages/MorningNewsPage";
import { NewsPage } from "./pages/NewsPage";
import { SettingsPage } from "./pages/SettingsPage";
import StatusPage from "./pages/StatusPage";
import { TestsPage } from "./pages/TestsPage";
import { ToolsPage } from "./pages/ToolsPage";

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/bundles" element={<BundlesPage />} />
        <Route path="/feeds" element={<FeedsPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/digest" element={<DigestPage />} />
        <Route path="/morning-news" element={<MorningNewsPage />} />
        <Route path="/huggingface" element={<HuggingFacePage />} />
        <Route path="/apps" element={<AppsPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/tests" element={<TestsPage />} />
        <Route path="/logs" element={<LogsPage />} />
      </Routes>
      <FloatingChat />
    </Shell>
  );
}
