# FakeFind Audit: aiwatcher-mcp
**Date**: 2026-07-25

## Summary
- Total issues: 7
- CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 4
- Files affected: 6

## Fixed

### HIGH: StatusPage.tsx — Always-green Live badge
- Static "Live" badge never reflected backend state
- Fixed: wired to Zustand useConnection store, shows Live/Connecting/Offline

### MEDIUM: ToolsPage.tsx — poll_feeds preview mapped to /api/stats
- Preview button showed stats instead of feeds data
- Fixed: removed poll_feeds from SAFE_TOOL_ENDPOINTS (it's a write operation)

### MEDIUM: BundlesPage.tsx — onAdded callback was empty no-op
- onAdded={() => {}} after adding suggested source feed
- Fixed: wired to invalidateQueries(["bundles"])

### LOW: Shell.tsx — Hardcoded v0.1.0 in sidebar
- Fixed: fetches version from /api/capabilities at mount

### LOW: HelpPage.tsx — Duplicate hardcoded v0.1.0
- Fixed: removed version string, kept description

### LOW: ChatPage.tsx — Hardcoded gemma3:1b model fallback
- Fixed: removed hardcoded fallback, passes session.model as-is

### LOW: TestsPage.tsx — Default speech test text
- Left as-is (acceptable for debug page)

## Remaining
- TestsPage.tsx: default speech text (LOW, acceptable debug page)
