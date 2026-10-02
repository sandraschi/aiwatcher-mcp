# Per-repo fleet start config for aiwatcher-mcp
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'aiwatcher-mcp'
    BackendPort  = 10946
    FrontendPort = 10947
    HealthPath   = '/api/health'
    WebRoot      = 'webapp'
    Backend = @{
        Kind          = 'uvicorn'
        UvicornTarget = 'aiwatcher_mcp.api:app'
        SyncExtras    = @('dev')
        Env           = @{ WEB_PORT = '10946' }
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        PortEnvVar     = 'VITE_PORT'
        ApiTargetEnv   = 'VITE_API_TARGET'
    }
}
