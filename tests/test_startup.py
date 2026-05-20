import os
import signal
import socket
import subprocess
import time

import httpx

BACKEND_URL = "http://localhost:10946/api/health"
BACKEND_PORT = 10946
FRONTEND_PORT = 10947

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_port(port):
    """Utility to ensure ports are clear before/after tests"""
    try:
        import psutil
        for proc in psutil.process_iter():
            try:
                conns = proc.connections(kind='inet')
                for conn in conns:
                    if conn.laddr.port == port:
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
                continue
    except ImportError:
        pass

def test_backend_only_startup():
    # 1. Ensure ports are clear
    kill_port(BACKEND_PORT)
    kill_port(FRONTEND_PORT)
    
    # 2. Launch start.ps1 -BackendOnly
    env = os.environ.copy()
    env["SKIP_SYNC"] = "1"
    cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "./start.ps1", "-BackendOnly", "-NoBrowser"]
    
    # Start the process
    proc = subprocess.Popen(cmd, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    
    try:
        # 3. Poll health endpoint (max 60s)
        success = False
        for _ in range(60):
            time.sleep(1)
            try:
                with httpx.Client() as client:
                    resp = client.get(BACKEND_URL, timeout=2.0)
                    if resp.status_code == 200:
                        success = True
                        break
            except Exception:
                continue
        
        assert success, "Backend failed to start and respond to health check on port 10946"
        
        # 4. Verify Frontend is NOT listening
        assert not is_port_open(FRONTEND_PORT), "Frontend (port 10947) is listening but -BackendOnly was specified"
        
    finally:
        # 5. Cleanup
        if os.name == 'nt':
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)])
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        
        kill_port(BACKEND_PORT)
        kill_port(FRONTEND_PORT)

if __name__ == "__main__":
    test_backend_only_startup()
    print("Test Passed!")
