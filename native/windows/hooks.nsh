; Kill UI + backend before install/uninstall (backend locks resources/*.exe).
!macro KillAiwatcherMcpFleetProcesses
  DetailPrint "Stopping aiwatcher-mcp processes..."
  ExecWait 'taskkill /F /IM aiwatcher-mcp-backend.exe /T' $0
  ExecWait 'taskkill /F /IM aiwatcher-mcp-native.exe /T' $0
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::KillProcessCurrentUser "aiwatcher-mcp-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcessCurrentUser "aiwatcher-mcp-native.exe"
    Pop $0
  !else
    nsis_tauri_utils::KillProcess "aiwatcher-mcp-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcess "aiwatcher-mcp-native.exe"
    Pop $0
  !endif
  Sleep 2000
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro KillAiwatcherMcpFleetProcesses
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro KillAiwatcherMcpFleetProcesses
!macroend

