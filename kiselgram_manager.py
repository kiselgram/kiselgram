#!/usr/bin/env python3
"""
Kiselgram Web Terminal - Interactive browser-based management
Reads status from JSON files and provides full terminal control
"""

import os
import sys
import json
import time
import signal
import subprocess
import threading
import webbrowser
import pty
import select
import termios
import struct
import fcntl
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, Response

# Create app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'kiselgram-terminal-secret'

# Paths
BASE_DIR = Path(__file__).parent.absolute()
STATUS_FILE = BASE_DIR / '.kiselgram_status.json'
VIDEO_STATUS_FILE = BASE_DIR / '.kiselgram_video_status.json'
LOG_FILE = BASE_DIR / '.kiselgram_terminal.log'

# Store active terminal sessions
active_sessions = {}


class JSONStatusReader:
    """Read and parse status from JSON files"""

    @staticmethod
    def read_main_status():
        """Read main app status from JSON"""
        try:
            if STATUS_FILE.exists():
                with open(STATUS_FILE, 'r') as f:
                    data = json.load(f)

                # Verify if process is actually running
                if 'pid' in data:
                    try:
                        os.kill(data['pid'], 0)  # Check if process exists
                        data['process_exists'] = True
                    except OSError:
                        data['process_exists'] = False
                        data['running'] = False

                return data
            return None
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def read_video_status():
        """Read video server status from JSON"""
        try:
            if VIDEO_STATUS_FILE.exists():
                with open(VIDEO_STATUS_FILE, 'r') as f:
                    data = json.load(f)

                # Verify if process is actually running
                if 'pid' in data:
                    try:
                        os.kill(data['pid'], 0)
                        data['process_exists'] = True
                    except OSError:
                        data['process_exists'] = False
                        data['running'] = False

                return data
            return None
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def get_all_status():
        """Get combined status from all JSON files"""
        main_status = JSONStatusReader.read_main_status()
        video_status = JSONStatusReader.read_video_status()

        # Also check ports directly
        import socket
        def check_port(port):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0

        return {
            'main': main_status,
            'video': video_status,
            'ports': {
                'main': check_port(5000) if main_status else False,
                'video': check_port(5001) if video_status else False
            },
            'files': {
                'main_status': STATUS_FILE.exists(),
                'video_status': VIDEO_STATUS_FILE.exists()
            },
            'timestamp': datetime.now().isoformat()
        }


class TerminalSession:
    """Interactive terminal session for running commands"""

    def __init__(self, session_id):
        self.session_id = session_id
        self.master_fd = None
        self.slave_fd = None
        self.process = None
        self.output_buffer = []
        self.running = False
        self.cwd = str(BASE_DIR)

    def start(self, cmd=None):
        """Start a new terminal session"""
        try:
            # Create pseudo-terminal
            self.master_fd, self.slave_fd = pty.openpty()

            # Set terminal size
            winsize = struct.pack('HHHH', 24, 80, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)

            # Set terminal attributes
            attrs = termios.tcgetattr(self.slave_fd)
            attrs[3] = attrs[3] & ~termios.ECHO  # Disable echo
            termios.tcsetattr(self.slave_fd, termios.TCSANOW, attrs)

            # Start shell or command
            if cmd:
                shell_cmd = ['/bin/bash', '-c', cmd]
            else:
                shell_cmd = ['/bin/bash', '--login']

            self.process = subprocess.Popen(
                shell_cmd,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=self.cwd,
                preexec_fn=os.setsid,
                close_fds=True
            )

            os.close(self.slave_fd)
            self.running = True

            # Start output reader thread
            def reader():
                while self.running and self.process.poll() is None:
                    try:
                        r, w, e = select.select([self.master_fd], [], [], 0.1)
                        if r:
                            data = os.read(self.master_fd, 1024)
                            if data:
                                self.output_buffer.append(data.decode('utf-8', errors='ignore'))
                                # Keep buffer manageable
                                if len(self.output_buffer) > 1000:
                                    self.output_buffer = self.output_buffer[-1000:]
                    except (IOError, OSError):
                        break
                self.running = False

            thread = threading.Thread(target=reader, daemon=True)
            thread.start()

            return True

        except Exception as e:
            print(f"Error starting terminal: {e}")
            return False

    def write_input(self, data):
        """Write input to the terminal"""
        if self.master_fd and self.running:
            try:
                os.write(self.master_fd, data.encode())
                return True
            except:
                return False
        return False

    def resize(self, rows, cols):
        """Resize terminal"""
        if self.master_fd and self.running:
            try:
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
                return True
            except:
                pass
        return False

    def get_output(self):
        """Get accumulated output and clear buffer"""
        output = ''.join(self.output_buffer)
        self.output_buffer = []
        return output

    def stop(self):
        """Stop the terminal session"""
        self.running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                time.sleep(1)
                self.process.kill()
            except:
                pass
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass


class CommandRunner:
    """Run manage.py commands and capture output"""

    @staticmethod
    def run_command(command, input_data=None, timeout=30):
        """Run a command and return output"""
        try:
            cmd = [sys.executable, 'manage.py'] + command.split()

            # Use pseudo-terminal for interactive commands
            if input_data or any(x in command for x in ['reset-db', 'delete']):
                master, slave = pty.openpty()

                process = subprocess.Popen(
                    cmd,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    cwd=str(BASE_DIR),
                    close_fds=True
                )

                os.close(slave)

                output = []
                start_time = time.time()

                while True:
                    try:
                        r, w, e = select.select([master], [], [], 0.1)
                        if r:
                            data = os.read(master, 1024).decode(errors='ignore')
                            if data:
                                output.append(data)

                                # Send input if needed
                                if input_data and 'y/n' in data.lower():
                                    time.sleep(0.5)
                                    os.write(master, (input_data + '\n').encode())

                        if process.poll() is not None:
                            break

                        if time.time() - start_time > timeout:
                            process.kill()
                            break
                    except:
                        break

                os.close(master)

                return {
                    'success': process.returncode == 0,
                    'output': ''.join(output),
                    'returncode': process.returncode
                }

            else:
                # Simple command without interaction
                result = subprocess.run(
                    cmd,
                    cwd=str(BASE_DIR),
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                return {
                    'success': result.returncode == 0,
                    'output': result.stdout + result.stderr,
                    'returncode': result.returncode
                }

        except subprocess.TimeoutExpired:
            return {'success': False, 'output': 'Command timed out'}
        except Exception as e:
            return {'success': False, 'output': str(e)}


# Routes

@app.route('/')
def index():
    """Main terminal interface"""
    return render_template('terminal.html')


@app.route('/api/status')
def api_status():
    """Get status from JSON files"""
    return jsonify(JSONStatusReader.get_all_status())


@app.route('/api/status/json/main')
def api_status_main_json():
    """Get raw main status JSON"""
    if STATUS_FILE.exists():
        return send_file(str(STATUS_FILE))
    return jsonify({'error': 'No status file'})


@app.route('/api/status/json/video')
def api_status_video_json():
    """Get raw video status JSON"""
    if VIDEO_STATUS_FILE.exists():
        return send_file(str(VIDEO_STATUS_FILE))
    return jsonify({'error': 'No status file'})


@app.route('/api/terminal/start', methods=['POST'])
def api_terminal_start():
    """Start a new terminal session"""
    data = request.json or {}
    session_id = os.urandom(16).hex()

    terminal = TerminalSession(session_id)
    cmd = data.get('cmd')

    if terminal.start(cmd):
        active_sessions[session_id] = terminal
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Terminal started'
        })

    return jsonify({'success': False, 'message': 'Failed to start terminal'})


@app.route('/api/terminal/<session_id>/write', methods=['POST'])
def api_terminal_write(session_id):
    """Write to terminal"""
    if session_id in active_sessions:
        data = request.json or {}
        text = data.get('input', '')

        if active_sessions[session_id].write_input(text):
            return jsonify({'success': True})

    return jsonify({'success': False})


@app.route('/api/terminal/<session_id>/read')
def api_terminal_read(session_id):
    """Read from terminal (SSE stream)"""

    def generate():
        if session_id not in active_sessions:
            yield "data: {\"error\": \"Session not found\"}\n\n"
            return

        terminal = active_sessions[session_id]

        while terminal.running:
            output = terminal.get_output()
            if output:
                yield f"data: {json.dumps({'output': output})}\n\n"
            time.sleep(0.1)

        # Send final output
        output = terminal.get_output()
        if output:
            yield f"data: {json.dumps({'output': output})}\n\n"

        yield "data: {\"closed\": true}\n\n"

        # Clean up
        if session_id in active_sessions:
            del active_sessions[session_id]

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/terminal/<session_id>/resize', methods=['POST'])
def api_terminal_resize(session_id):
    """Resize terminal"""
    if session_id in active_sessions:
        data = request.json or {}
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)

        if active_sessions[session_id].resize(rows, cols):
            return jsonify({'success': True})

    return jsonify({'success': False})


@app.route('/api/terminal/<session_id>/stop', methods=['POST'])
def api_terminal_stop(session_id):
    """Stop terminal session"""
    if session_id in active_sessions:
        active_sessions[session_id].stop()
        del active_sessions[session_id]
        return jsonify({'success': True})

    return jsonify({'success': False})


@app.route('/api/command/run', methods=['POST'])
def api_command_run():
    """Run a single command"""
    data = request.json or {}
    command = data.get('command', '')
    auto_confirm = data.get('auto_confirm', True)

    if not command:
        return jsonify({'success': False, 'output': 'No command specified'})

    input_data = 'yes' if auto_confirm and 'reset-db' in command else None
    result = CommandRunner.run_command(command, input_data)

    return jsonify(result)


@app.route('/api/command/suggestions')
def api_command_suggestions():
    """Get command suggestions"""
    commands = [
        {'cmd': 'status', 'desc': 'Show status of all services'},
        {'cmd': 'start', 'desc': 'Start main app + video server'},
        {'cmd': 'start --no-video', 'desc': 'Start main app only'},
        {'cmd': 'stop', 'desc': 'Stop all services'},
        {'cmd': 'restart', 'desc': 'Restart all services'},
        {'cmd': 'video start', 'desc': 'Start video server only'},
        {'cmd': 'video stop', 'desc': 'Stop video server only'},
        {'cmd': 'video status', 'desc': 'Check video server status'},
        {'cmd': 'setup', 'desc': 'Setup environment'},
        {'cmd': 'clean', 'desc': 'Clean temporary files'},
        {'cmd': 'reset-db', 'desc': 'Reset database (⚠️ deletes data)'},
        {'cmd': 'test', 'desc': 'Run basic tests'},
        {'cmd': 'help', 'desc': 'Show help'},
    ]
    return jsonify(commands)


@app.route('/api/process/kill', methods=['POST'])
def api_process_kill():
    """Kill process by port or PID"""
    data = request.json or {}
    port = data.get('port')
    pid = data.get('pid')

    results = []

    if port:
        # Kill process on port
        try:
            import socket
            import psutil

            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    results.append(f"Killed PID {conn.pid} on port {port}")
        except:
            # Fallback method
            if sys.platform == 'win32':
                subprocess.run(f'netstat -ano | findstr :{port}', shell=True)
            else:
                subprocess.run(['pkill', '-f', f':{port}'])
            results.append(f"Attempted to kill processes on port {port}")

    if pid:
        try:
            os.kill(pid, signal.SIGKILL)
            results.append(f"Killed PID {pid}")
        except:
            results.append(f"Failed to kill PID {pid}")

    return jsonify({'success': True, 'results': results})


@app.route('/api/logs')
def api_logs():
    """Get application logs"""
    logs = []

    # Read manage.py output if available
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r') as f:
            logs = f.readlines()[-100:]  # Last 100 lines

    return jsonify({'logs': logs})


@app.route('/open/<service>')
def open_service(service):
    """Open service in browser"""
    if service == 'main':
        webbrowser.open('http://localhost:5000')
        return jsonify({'success': True, 'url': 'http://localhost:5000'})
    elif service == 'video':
        webbrowser.open('http://localhost:5001')
        return jsonify({'success': True, 'url': 'http://localhost:5001'})
    return jsonify({'success': False})


def create_template():
    """Create the HTML template"""
    template_dir = Path(__file__).parent / 'templates'
    template_dir.mkdir(exist_ok=True)

    template_path = template_dir / 'terminal.html'

    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kiselgram Web Terminal</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Courier New', 'Fira Code', monospace;
            background: #1e1e2f;
            color: #fff;
            height: 100vh;
            overflow: hidden;
        }

        .container {
            display: flex;
            height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 350px;
            background: #2d2d3f;
            border-right: 1px solid #3d3d4f;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid #3d3d4f;
        }

        .sidebar-header h1 {
            font-size: 1.2em;
            color: #0ff;
            margin-bottom: 5px;
        }

        .sidebar-header p {
            font-size: 0.8em;
            color: #aaa;
        }

        .status-panel {
            padding: 15px;
            border-bottom: 1px solid #3d3d4f;
        }

        .status-panel h3 {
            color: #0ff;
            margin-bottom: 10px;
            font-size: 0.9em;
        }

        .status-card {
            background: #1e1e2f;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 3px solid transparent;
        }

        .status-card.main {
            border-left-color: #0ff;
        }

        .status-card.video {
            border-left-color: #f0f;
        }

        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .status-title {
            font-weight: bold;
            color: #fff;
        }

        .status-badge {
            font-size: 0.7em;
            padding: 3px 8px;
            border-radius: 12px;
        }

        .badge-running {
            background: #00ff8844;
            color: #0f8;
            border: 1px solid #0f8;
        }

        .badge-stopped {
            background: #ff444444;
            color: #f44;
            border: 1px solid #f44;
        }

        .status-detail {
            font-size: 0.75em;
            color: #aaa;
            margin: 3px 0;
        }

        .status-detail span {
            color: #0ff;
            margin-right: 5px;
        }

        .status-json {
            margin-top: 8px;
            padding: 8px;
            background: #1a1a2a;
            border-radius: 4px;
            font-size: 0.65em;
            color: #0f0;
            white-space: pre-wrap;
            max-height: 150px;
            overflow-y: auto;
            font-family: monospace;
        }

        .quick-actions {
            padding: 15px;
            border-bottom: 1px solid #3d3d4f;
        }

        .quick-actions h3 {
            color: #0ff;
            margin-bottom: 10px;
            font-size: 0.9em;
        }

        .action-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        .action-btn {
            background: #1e1e2f;
            border: 1px solid #3d3d4f;
            color: #fff;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
            transition: all 0.2s;
        }

        .action-btn:hover {
            background: #3d3d4f;
            border-color: #0ff;
        }

        .action-btn.danger:hover {
            border-color: #f44;
            color: #f44;
        }

        .action-btn.success:hover {
            border-color: #0f8;
            color: #0f8;
        }

        .command-suggestions {
            padding: 15px;
            flex: 1;
        }

        .command-suggestions h3 {
            color: #0ff;
            margin-bottom: 10px;
            font-size: 0.9em;
        }

        .suggestion-item {
            padding: 8px;
            margin: 4px 0;
            background: #1e1e2f;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75em;
            display: flex;
            justify-content: space-between;
            border: 1px solid transparent;
        }

        .suggestion-item:hover {
            border-color: #0ff;
        }

        .suggestion-cmd {
            color: #0f0;
        }

        .suggestion-desc {
            color: #aaa;
            font-size: 0.9em;
        }

        /* Main content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #1e1e2f;
        }

        .terminal-header {
            background: #2d2d3f;
            padding: 10px 20px;
            border-bottom: 1px solid #3d3d4f;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .terminal-header h3 {
            color: #0ff;
            font-size: 0.9em;
        }

        .terminal-container {
            flex: 1;
            padding: 20px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .terminal {
            flex: 1;
            background: #0a0a0f;
            border-radius: 8px;
            padding: 15px;
            overflow-y: auto;
            font-family: 'Courier New', 'Fira Code', monospace;
            font-size: 13px;
            line-height: 1.5;
        }

        .terminal-output {
            color: #0f0;
            margin-bottom: 10px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .terminal-output div {
            margin: 2px 0;
        }

        .terminal-input-line {
            display: flex;
            align-items: center;
            margin-top: 5px;
        }

        .terminal-prompt {
            margin-right: 10px;
            color: #0ff;
            font-weight: bold;
        }

        .terminal-input {
            flex: 1;
            background: transparent;
            border: none;
            color: #fff;
            font-family: 'Courier New', 'Fira Code', monospace;
            font-size: 13px;
            outline: none;
        }

        .command-bar {
            background: #2d2d3f;
            padding: 15px 20px;
            border-top: 1px solid #3d3d4f;
            display: flex;
            gap: 10px;
        }

        .command-input {
            flex: 1;
            background: #1e1e2f;
            border: 1px solid #3d3d4f;
            color: #fff;
            padding: 10px 15px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            outline: none;
        }

        .command-input:focus {
            border-color: #0ff;
        }

        .send-btn {
            background: #0ff;
            color: #1e1e2f;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }

        .send-btn:hover {
            background: #0cf;
        }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: #2d2d3f;
            padding: 30px;
            border-radius: 8px;
            max-width: 500px;
            width: 90%;
        }

        .modal-content h3 {
            color: #0ff;
            margin-bottom: 20px;
        }

        .modal-content p {
            margin: 15px 0;
            color: #aaa;
        }

        .modal-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #2d2d3f;
            border-left: 3px solid #0ff;
            padding: 15px 25px;
            border-radius: 4px;
            color: #fff;
            display: none;
            z-index: 1001;
        }

        .toast.error {
            border-left-color: #f44;
        }

        .toast.success {
            border-left-color: #0f8;
        }

        /* Loading */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #3d3d4f;
            border-top-color: #0ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #1e1e2f;
        }

        ::-webkit-scrollbar-thumb {
            background: #3d3d4f;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #4d4d5f;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h1>🎮 Kiselgram Web Terminal</h1>
                <p>Interactive browser-based management</p>
                <div style="margin-top: 10px; font-size: 0.75em; color: #0f0;" id="jsonStatus">
                    ✓ Reading from JSON files
                </div>
            </div>

            <!-- Status Panel -->
            <div class="status-panel">
                <h3>📊 Service Status (from JSON)</h3>
                <div id="statusContainer">
                    <div class="loading"></div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="quick-actions">
                <h3>⚡ Quick Actions</h3>
                <div class="action-grid">
                    <button class="action-btn success" onclick="window.runQuickCommand('start')">🚀 Start All</button>
                    <button class="action-btn danger" onclick="window.runQuickCommand('stop')">⏹️ Stop All</button>
                    <button class="action-btn" onclick="window.runQuickCommand('status')">📊 Status</button>
                    <button class="action-btn" onclick="window.runQuickCommand('video start')">🎥 Start Video</button>
                    <button class="action-btn danger" onclick="window.runQuickCommand('video stop')">⏹️ Stop Video</button>
                    <button class="action-btn" onclick="window.runQuickCommand('clean')">🧹 Clean</button>
                    <button class="action-btn danger" onclick="window.confirmResetDB()">⚠️ Reset DB</button>
                    <button class="action-btn" onclick="window.refreshStatus()">🔄 Refresh</button>
                </div>
            </div>

            <!-- Command Suggestions -->
            <div class="command-suggestions">
                <h3>📋 Command Suggestions</h3>
                <div id="suggestionsContainer">
                    <div class="loading"></div>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <!-- Terminal Header -->
            <div class="terminal-header">
                <h3>📟 Interactive Terminal</h3>
                <button class="action-btn" onclick="window.clearTerminal()" style="font-size: 0.8em;">🗑️ Clear</button>
            </div>

            <!-- Terminal -->
            <div class="terminal-container">
                <div class="terminal" id="terminal" onclick="window.focusTerminalInput()">
                    <div id="terminal-output" class="terminal-output">
                        <div>╔══════════════════════════════════════════════════════════╗</div>
                        <div>║         Kiselgram Web Terminal v1.0                       ║</div>
                        <div>╠══════════════════════════════════════════════════════════╣</div>
                        <div>║  Status loaded from JSON files                           ║</div>
                        <div>║  Type 'python manage.py help' for commands               ║</div>
                        <div>╚══════════════════════════════════════════════════════════╝</div>
                        <div></div>
                    </div>
                    <div class="terminal-input-line">
                        <span class="terminal-prompt">$</span>
                        <input type="text" id="terminal-input" class="terminal-input" 
                               autofocus placeholder="Enter command..." autocomplete="off">
                    </div>
                </div>
            </div>

            <!-- Command Bar -->
            <div class="command-bar">
                <input type="text" id="quick-command" class="command-input" 
                       placeholder="Quick command (e.g., status, start, stop)" 
                       list="command-datalist">
                <datalist id="command-datalist"></datalist>
                <button class="send-btn" onclick="window.sendQuickCommand()">Run Command</button>
            </div>
        </div>
    </div>

    <!-- Reset DB Confirmation Modal -->
    <div class="modal" id="resetModal">
        <div class="modal-content">
            <h3>⚠️ Reset Database</h3>
            <p>This will DELETE ALL DATA! Are you absolutely sure?</p>
            <p>Type <strong>yes</strong> to confirm:</p>
            <input type="text" id="resetConfirm" class="command-input" style="width: 100%;" placeholder="yes">
            <div class="modal-actions">
                <button class="action-btn" onclick="window.closeModal()">Cancel</button>
                <button class="action-btn danger" onclick="window.executeResetDB()">Reset Database</button>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast" id="toast"></div>

    <script>
        // State
        let currentSessionId = null;
        let eventSource = null;
        let commandHistory = [];
        let historyIndex = -1;

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            refreshStatus();
            loadSuggestions();
            startNewTerminal();

            // Input handling
            const input = document.getElementById('terminal-input');
            input.addEventListener('keydown', handleInputKey);

            // Quick command input
            const quickCmd = document.getElementById('quick-command');
            quickCmd.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') sendQuickCommand();
            });
        });

        // Show toast
        window.showToast = function(message, type = 'info') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = `toast ${type}`;
            toast.style.display = 'block';
            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        };

        // Refresh status from JSON
        window.refreshStatus = async function() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateStatusUI(data);
            } catch (error) {
                console.error('Error refreshing status:', error);
            }
        };

        // Update status UI
        function updateStatusUI(data) {
            const container = document.getElementById('statusContainer');

            let html = '';

            // Main app status
            if (data.main) {
                const main = data.main;
                const statusClass = main.running ? 'badge-running' : 'badge-stopped';
                const statusText = main.running ? 'RUNNING' : 'STOPPED';

                html += `
                    <div class="status-card main">
                        <div class="status-header">
                            <span class="status-title">📱 Main App</span>
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                        <div class="status-detail"><span>Port:</span> ${main.port || 'N/A'}</div>
                        <div class="status-detail"><span>PID:</span> ${main.pid || 'N/A'}</div>
                        <div class="status-detail"><span>Started:</span> ${main.started_at ? new Date(main.started_at).toLocaleString() : 'N/A'}</div>
                `;

                if (main.error) {
                    html += `<div class="status-detail" style="color: #f44;">Error: ${main.error}</div>`;
                }

                // Show raw JSON
                html += `<div class="status-json">${escapeHtml(JSON.stringify(main, null, 2))}</div>`;
                html += `</div>`;
            } else {
                html += `
                    <div class="status-card main">
                        <div class="status-header">
                            <span class="status-title">📱 Main App</span>
                            <span class="status-badge badge-stopped">NO STATUS</span>
                        </div>
                        <div class="status-detail">No status file found</div>
                    </div>
                `;
            }

            // Video server status
            if (data.video) {
                const video = data.video;
                const statusClass = video.running ? 'badge-running' : 'badge-stopped';
                const statusText = video.running ? 'RUNNING' : 'STOPPED';

                html += `
                    <div class="status-card video">
                        <div class="status-header">
                            <span class="status-title">🎥 Video Server</span>
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                        <div class="status-detail"><span>Port:</span> ${video.port || 'N/A'}</div>
                        <div class="status-detail"><span>PID:</span> ${video.pid || 'N/A'}</div>
                        <div class="status-detail"><span>Started:</span> ${video.started_at ? new Date(video.started_at).toLocaleString() : 'N/A'}</div>
                `;

                if (video.error) {
                    html += `<div class="status-detail" style="color: #f44;">Error: ${video.error}</div>`;
                }

                html += `<div class="status-json">${escapeHtml(JSON.stringify(video, null, 2))}</div>`;
                html += `</div>`;
            } else {
                html += `
                    <div class="status-card video">
                        <div class="status-header">
                            <span class="status-title">🎥 Video Server</span>
                            <span class="status-badge badge-stopped">NO STATUS</span>
                        </div>
                        <div class="status-detail">No status file found</div>
                    </div>
                `;
            }

            // Port status
            html += `
                <div style="margin-top: 10px; padding: 10px; background: #1e1e2f; border-radius: 4px;">
                    <div class="status-detail"><span>Port 5000:</span> ${data.ports?.main ? '🟢 In use' : '⚫ Free'}</div>
                    <div class="status-detail"><span>Port 5001:</span> ${data.ports?.video ? '🟢 In use' : '⚫ Free'}</div>
                    <div class="status-detail"><span>JSON files:</span> Main: ${data.files?.main_status ? '✅' : '❌'} Video: ${data.files?.video_status ? '✅' : '❌'}</div>
                    <div class="status-detail"><span>Updated:</span> ${new Date(data.timestamp).toLocaleTimeString()}</div>
                </div>
            `;

            container.innerHTML = html;
            document.getElementById('jsonStatus').innerHTML = `✓ Reading from: ${data.files?.main_status ? 'kiselgram_status.json' : 'no status file'}`;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Load command suggestions
        async function loadSuggestions() {
            try {
                const response = await fetch('/api/command/suggestions');
                const commands = await response.json();

                const container = document.getElementById('suggestionsContainer');
                let html = '';
                const datalist = document.getElementById('command-datalist');

                commands.forEach(cmd => {
                    html += `
                        <div class="suggestion-item" onclick="window.runQuickCommand('${cmd.cmd}')">
                            <span class="suggestion-cmd">${cmd.cmd}</span>
                            <span class="suggestion-desc">${cmd.desc}</span>
                        </div>
                    `;

                    const option = document.createElement('option');
                    option.value = cmd.cmd;
                    datalist.appendChild(option);
                });

                container.innerHTML = html;
            } catch (error) {
                console.error('Error loading suggestions:', error);
            }
        }

        // Start new terminal session
        async function startNewTerminal() {
            try {
                const response = await fetch('/api/terminal/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                });
                const data = await response.json();

                if (data.success) {
                    currentSessionId = data.session_id;
                    startEventSource();
                    showToast('Terminal session started', 'success');

                    // Send initial command to set context
                    setTimeout(() => {
                        sendToTerminal('clear');
                        sendToTerminal('echo "Kiselgram Management Terminal Ready"');
                        sendToTerminal('echo ""');
                        sendToTerminal('echo "Available commands:"');
                        sendToTerminal('echo "  python manage.py status   - Check service status"');
                        sendToTerminal('echo "  python manage.py start    - Start all services"');
                        sendToTerminal('echo "  python manage.py stop     - Stop all services"');
                        sendToTerminal('echo "  python manage.py help     - Show full help"');
                        sendToTerminal('echo ""');
                    }, 500);
                }
            } catch (error) {
                console.error('Error starting terminal:', error);
            }
        }

        // Start event source for terminal output
        function startEventSource() {
            if (eventSource) {
                eventSource.close();
            }

            eventSource = new EventSource(`/api/terminal/${currentSessionId}/read`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.output) {
                    appendToTerminal(data.output);
                }
                if (data.closed) {
                    eventSource.close();
                }
            };

            eventSource.onerror = function() {
                console.error('Event source error');
                setTimeout(startNewTerminal, 1000);
            };
        }

        // Send input to terminal
        window.sendToTerminal = async function(text) {
            if (!currentSessionId) return;

            try {
                await fetch(`/api/terminal/${currentSessionId}/write`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({input: text + '\\n'})
                });
            } catch (error) {
                console.error('Error sending to terminal:', error);
            }
        };

        // Append to terminal output
        function appendToTerminal(text) {
            const output = document.getElementById('terminal-output');
            // Escape HTML and handle newlines
            const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const lines = escaped.split('\\n');
            lines.forEach(line => {
                if (line.trim() || line === '') {
                    const div = document.createElement('div');
                    div.textContent = line;
                    output.appendChild(div);
                }
            });
            output.scrollTop = output.scrollHeight;
        }

        // Clear terminal
        window.clearTerminal = function() {
            const output = document.getElementById('terminal-output');
            output.innerHTML = '<div>Terminal cleared.</div>';
        };

        // Handle input key
        function handleInputKey(e) {
            const input = document.getElementById('terminal-input');

            if (e.key === 'Enter') {
                const cmd = input.value.trim();
                if (cmd) {
                    commandHistory.push(cmd);
                    historyIndex = commandHistory.length;

                    // Add to terminal output
                    const output = document.getElementById('terminal-output');
                    const promptDiv = document.createElement('div');
                    promptDiv.style.color = '#0ff';
                    promptDiv.textContent = '$ ' + cmd;
                    output.appendChild(promptDiv);
                    output.scrollTop = output.scrollHeight;

                    // Send to terminal
                    sendToTerminal(cmd);

                    input.value = '';
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (historyIndex > 0) {
                    historyIndex--;
                    input.value = commandHistory[historyIndex];
                }
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (historyIndex < commandHistory.length - 1) {
                    historyIndex++;
                    input.value = commandHistory[historyIndex];
                } else {
                    historyIndex = commandHistory.length;
                    input.value = '';
                }
            }
        }

        // Focus terminal input
        window.focusTerminalInput = function() {
            document.getElementById('terminal-input').focus();
        };

        // Run quick command
        window.runQuickCommand = function(cmd) {
            // Add to terminal output
            const output = document.getElementById('terminal-output');
            const promptDiv = document.createElement('div');
            promptDiv.style.color = '#0ff';
            promptDiv.textContent = '$ python manage.py ' + cmd;
            output.appendChild(promptDiv);
            output.scrollTop = output.scrollHeight;

            // Send to terminal
            sendToTerminal('python manage.py ' + cmd);
        };

        // Send quick command from input
        window.sendQuickCommand = function() {
            const input = document.getElementById('quick-command');
            const cmd = input.value.trim();
            if (cmd) {
                runQuickCommand(cmd);
                input.value = '';
            }
        };

        // Confirm reset DB
        window.confirmResetDB = function() {
            document.getElementById('resetModal').classList.add('active');
            document.getElementById('resetConfirm').focus();
        };

        // Close modal
        window.closeModal = function() {
            document.getElementById('resetModal').classList.remove('active');
            document.getElementById('resetConfirm').value = '';
        };

        // Execute reset DB
        window.executeResetDB = function() {
            const confirm = document.getElementById('resetConfirm').value;
            if (confirm === 'yes') {
                runQuickCommand('reset-db');
                closeModal();
            } else {
                showToast('Type "yes" to confirm', 'error');
            }
        };

        // Auto-refresh status every 5 seconds
        setInterval(refreshStatus, 5000);

        // Make functions globally available
        window.refreshStatus = refreshStatus;
        window.runQuickCommand = runQuickCommand;
        window.sendQuickCommand = sendQuickCommand;
        window.confirmResetDB = confirmResetDB;
        window.closeModal = closeModal;
        window.executeResetDB = executeResetDB;
        window.clearTerminal = clearTerminal;
        window.focusTerminalInput = focusTerminalInput;
    </script>
</body>
</html>"""

    with open(template_path, 'w') as f:
        f.write(html)

    print(f"✅ Created terminal template at {template_path}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Kiselgram Web Terminal')
    parser.add_argument('--port', type=int, default=6060,
                        help='Port to run on (default: 6060)')
    parser.add_argument('--host', default='127.0.0.1',
                        help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--no-browser', action='store_true',
                        help="Don't open browser automatically")

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("""
  _  __ ___ _____ _____ ____ ____ ___  _   _   _ _____ _____ _   _ ____  
 | |/ // _ \\_   _| ____/ ___/ ___/ _ \\| \\ | | | | |_   _|_   _| \\ | |  _ \\ 
 | ' /| | | || | |  _| \\___ \\___ \\ | | |  \\| | | |   | |   | | |  \\| | |_) |
 | . \\| |_| || | | |___ ___) |__) | |_| | |\\  | |_|   | |   | | | |\\  |  _ < 
 |_|\\_\\\\___/ |_| |_____|____/____/ \\___/|_| \\_|\\___/  |_|   |_| |_| \\_|_| \\_\\
    """)
    print("=" * 60)
    print("📟 Kiselgram Web Terminal")
    print("📍 Reading status from: .kiselgram_status.json, .kiselgram_video_status.json")
    print(f"📍 Starting on http://{args.host}:{args.port}")
    print("=" * 60)
    print("\n🚀 Features:")
    print("   • Live status from JSON files")
    print("   • Interactive browser-based terminal")
    print("   • Command history and suggestions")
    print("   • Quick actions for common commands")
    print("   • Raw JSON viewer")
    print("=" * 60)

    # Create template
    create_template()

    # Open browser if not disabled
    if not args.no_browser:
        webbrowser.open(f"http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")

    # Run app
    try:
        app.run(host=args.host, port=args.port, debug=True, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Terminal stopped")


if __name__ == '__main__':
    main()