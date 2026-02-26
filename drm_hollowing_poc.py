import sys
import os
import argparse
import time
import json
import shutil
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor

try:
    import frida
except ImportError:
    print("[-] frida module is missing.")
    sys.exit(1)

DOCUMENT_EXTENSIONS = {
    '.xlsx', '.xls', '.xlsm', '.xlsb',
    '.docx', '.doc', '.docm',
    '.pptx', '.ppt', '.pptm', '.pdf',
}

VIEWER_MAP = {
    '.xlsx': 'EXCEL.EXE', '.xls': 'EXCEL.EXE', '.xlsm': 'EXCEL.EXE', '.xlsb': 'EXCEL.EXE',
    '.docx': 'WINWORD.EXE', '.doc': 'WINWORD.EXE', '.docm': 'WINWORD.EXE',
    '.pptx': 'POWERPNT.EXE', '.ppt': 'POWERPNT.EXE', '.pptm': 'POWERPNT.EXE',
    '.pdf': 'Acrobat.exe',
}

_OFFICE_ROOTS = [
    r"C:\Program Files\Microsoft Office\root\Office16",
    r"C:\Program Files\Microsoft Office\Office16",
    r"C:\Program Files\Microsoft Office\Office15",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16",
    # ... Some general paths included for completeness ...
]

_VIEWER_FALLBACK = {
    'EXCEL.EXE': [os.path.join(r, 'EXCEL.EXE') for r in _OFFICE_ROOTS],
    'WINWORD.EXE': [os.path.join(r, 'WINWORD.EXE') for r in _OFFICE_ROOTS],
    'POWERPNT.EXE': [os.path.join(r, 'POWERPNT.EXE') for r in _OFFICE_ROOTS],
}

# =========================================================================
# [SECURITY NOTICE / DISCLAIMER]
# Actual hooking logic, WinAPI specific calls, and buffer manipulation 
# have been intentially REDACTED to prevent malicious use against active DRM systems.
# The payload below only demonstrates the IPC architecture and injection framework.
# =========================================================================
HOOK_SCRIPT = r"""
var filePairs = %FILE_PAIRS%;

function extractFiles() {
    try {
        var okCount = 0;
        
        // [REDACTED] 
        // Logic to dynamically resolve 'kernel32.dll' native exports: 
        // e.g., CreateFileW, ReadFile, WriteFile, CloseHandle safely via Frida.
        
        // [REDACTED]
        // Setting up NativeFunctions and allocating memory buffers (1MB chunks)
        // to handle direct I/O.
        
        for (var fi = 0; fi < filePairs.length; fi++) {
            var pair = filePairs[fi];
            
            // [REDACTED]
            // Calling Native CreateFileW on the target to trigger the Minifilter driver
            // -> The driver checks if our context is a "Trusted Process" and decrypts on-the-fly.
            
            // [REDACTED]
            // Calling ReadFile in a loop to dump decrypted streams.
            // Calling WriteFile to dump the buffer into out 'decrypted.dat' payload file.
            
            okCount++;
        }
        
        // Notify the Python handler
        send({"type": "success", "msg": okCount + " files processed (MOCK)"});
    } catch (e) {
        send({"type": "error", "msg": e.message});
    }
}
setTimeout(extractFiles, %DELAY_MS%);
"""

def make_output_path(input_path, output_dir=None):
    """
    Append an obfuscated extension (.dat) to trick the Minifilter Driver
    from intercepting and re-encrypting the newly written payload.
    """
    _, file_name = os.path.split(input_path)
    name, ext = os.path.splitext(file_name)
    out_name = f"{name}_decrypted{ext}.dat" # .dat suffix bypasses policy
    target_dir = output_dir or os.path.dirname(os.path.abspath(input_path))
    return os.path.join(target_dir, out_name)

def resolve_viewer(app_name):
    if os.path.exists(app_name): return os.path.abspath(app_name)
    found = shutil.which(app_name)
    if found: return found
    for key, paths in _VIEWER_FALLBACK.items():
        if key.upper() == app_name.upper():
            for p in paths:
                if os.path.exists(p): return p
    return None

def process_one_instance(task_info):
    """
    Thread-safe injection logic for a single OS Process ID.
    """
    pid, pname, file_pairs, delay_ms = task_info
    event = threading.Event()
    
    def on_message(message, data):
        if message['type'] == 'send':
            payload = message['payload']
            if payload.get('type') == 'success':
                print(f"    [+] {pname}(PID:{pid}): {payload['msg']}")
            elif payload.get('type') == 'error':
                print(f"    [!] {pname}(PID:{pid}) Error: {payload['msg']}")
        elif message['type'] == 'error':
            print(f"    [!] {pname}(PID:{pid}) Frida Engine Error: {message.get('description')}")
        event.set()

    try:
        session = frida.attach(pid)
        js = HOOK_SCRIPT.replace("%FILE_PAIRS%", json.dumps(file_pairs, ensure_ascii=False))
        js = js.replace("%DELAY_MS%", str(delay_ms))
        script = session.create_script(js)
        script.on('message', on_message)
        script.load()
        
        # Wait until IPC resolves (max 60 sec timeout for safe termination)
        if not event.wait(timeout=60.0):
            print(f"    [!] {pname}(PID:{pid}) IPC Timeout")
        session.detach()
    except Exception as e:
        print(f"    [!] {pname}(PID:{pid}) Interception Failed: {e}")

def run_attach_mode(args):
    """
    Parallel process hollowing mode. 
    Scans entire OS for 'Trusted Processes' and injects simultaneously.
    """
    try: 
        import psutil
    except ImportError: 
        print("[-] pip install psutil is required for -a mode"); sys.exit(1)

    search_names = {os.path.basename(args.app).upper()} if args.app else {v.upper() for v in VIEWER_MAP.values()}
    print(f"[*] Scanning OS tree for targeted processes: {', '.join(search_names)}")

    tasks = []
    output_dir = os.path.join(os.path.expanduser('~'), 'Desktop', 'PoC_Dump')
    os.makedirs(output_dir, exist_ok=True)

    for p in psutil.process_iter(['pid', 'name']):
        try:
            pname = p.info['name']
            if pname and pname.upper() in search_names:
                doc_files = []
                for f in p.open_files():
                    _, ext = os.path.splitext(f.path)
                    if ext.lower() in DOCUMENT_EXTENSIONS and not os.path.basename(f.path).startswith('~$'):
                        doc_files.append({
                            "name": os.path.basename(f.path), 
                            "input": f.path, 
                            "output": make_output_path(f.path, output_dir)
                        })
                if doc_files:
                    # Minimal 200ms delay for already-active processes before triggering payload
                    tasks.append((p.pid, pname, doc_files, 200)) 
        except (psutil.NoSuchProcess, psutil.AccessDenied): 
            continue

    if not tasks:
        print("[-] Target process or valid DRM streams not found."); return

    print(f"[*] Initializing Parallel Hollowing on {len(tasks)} threads...")
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        executor.map(process_one_instance, tasks)
    print("\n[*] All operations concluded gracefully.")

def main():
    print("=" * 60)
    print("Enterprise DRM PoC - Trusted Process Hollowing Framework")
    print("=" * 60)
    parser = argparse.ArgumentParser(description="Demonstrates memory injection architecture.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--attach", action="store_true", help="Attach to running processes and extract in parallel")
    parser.add_argument("--app", default=None, help="Target specific Process execution name")
    args = parser.parse_args()

    if args.attach: 
        run_attach_mode(args)

if __name__ == '__main__':
    main()
