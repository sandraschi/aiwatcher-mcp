# Per-repo fleet start config for aiwatcher-mcp
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'aiwatcher-mcp'
    BackendPort  = 10946
    FrontendPort = 10947
    HealthPath   = '/api/health'
    WebRoot      = 'D:\Dev\repos\aiwatcher-mcp\webapp'
    NssmService  = 'aiwatcher-mcp'
    Backend = @{
        Kind = 'nssm'
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        PortEnvVar     = 'VITE_PORT'
        ApiTargetEnv   = 'VITE_API_TARGET'
    }
}
