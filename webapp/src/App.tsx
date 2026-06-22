import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { AppsPage } from "./pages/AppsPage";
import { BundlesPage } from "./pages/BundlesPage";
import { Dashboard } from "./pages/Dashboard";
import { DigestPage } from "./pages/DigestPage";
import { FeedsPage } from "./pages/FeedsPage";
import { HelpPage } from "./pages/HelpPage";
import { LogsPage } from "./pages/LogsPage";
import { NewsPage } from "./pages/NewsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TestsPage } from "./pages/TestsPage";
import { ToolsPage } from "./pages/ToolsPage";
import FloatingChat from "./components/FloatingChat";

export default function App() {
	return (
		<Shell>
			<Routes>
				<Route path="/" element={<Dashboard />} />
				<Route path="/news" element={<NewsPage />} />
				<Route path="/bundles" element={<BundlesPage />} />
				<Route path="/feeds" element={<FeedsPage />} />
				<Route path="/digest" element={<DigestPage />} />
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
