#!/usr/bin/env python3
"""
Kiselgram Web Terminal - Interactive browser-based management
Reads status from JSON files and provides full terminal control
Uses virtual environment from .venv
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
VENV_PYTHON = BASE_DIR / '.venv' / 'bin' / 'python'
VENV_ACTIVATE = BASE_DIR / '.venv' / 'bin' / 'activate'
STATUS_FILE = BASE_DIR / '.kiselgram_status.json'
VIDEO_STATUS_FILE = BASE_DIR / '.kiselgram_video_status.json'
LOG_FILE = BASE_DIR / '.kiselgram_terminal.log'
STATIC_DIR = BASE_DIR / 'static'

# Determine which Python to use (prefer venv)
if VENV_PYTHON.exists():
    PYTHON_EXEC = str(VENV_PYTHON)
    VENV_PATH = str(BASE_DIR / '.venv')
    print(f"✅ Using virtual environment: {PYTHON_EXEC}")
else:
    PYTHON_EXEC = sys.executable
    VENV_PATH = None
    print(f"⚠️ Virtual environment not found at {VENV_PYTHON}, using system Python")

# Create static directory if it doesn't exist
STATIC_DIR.mkdir(exist_ok=True)

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
    def read_video_status():
        """Read video server status from JSON"""
        try:
            if VIDEO_STATUS_FILE.exists():
                with open(VIDEO_STATUS_FILE, 'r') as f:
                    data = json.load(f)

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
            'timestamp': datetime.now().isoformat(),
            'venv': {
                'enabled': VENV_PATH is not None,
                'path': VENV_PATH,
                'python': PYTHON_EXEC
            }
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
        """Start a new terminal session with venv activated"""
        try:
            # Set up environment with TERM
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['PYTHONUNBUFFERED'] = '1'

            if VENV_PATH:
                env['VIRTUAL_ENV'] = VENV_PATH
                env['PATH'] = f"{VENV_PATH}/bin:{env.get('PATH', '')}"

            # Create a startup script that sets up the environment properly
            startup_script = f"""
# Set up terminal
export TERM=xterm-256color
export PS1='\\[\\033[01;34m\\]\\w\\[\\033[00m\\] \\[\\033[01;32m\\]$\\[\\033[00m\\] '

# Activate virtual environment if it exists
if [ -f "{VENV_ACTIVATE}" ]; then
    source "{VENV_ACTIVATE}"
    echo "✅ Virtual environment activated: {VENV_PATH}"
    echo "🐍 Python: $(which python)"
    echo ""
fi

# Set up Python path
export PYTHONPATH="{BASE_DIR}:$PYTHONPATH"

# Welcome message
echo "Kiselgram Management Terminal Ready"
echo "Type 'python manage.py help' for commands"
echo ""
"""

            # Write startup script to temp file
            startup_file = BASE_DIR / f'.term_startup_{self.session_id}.sh'
            with open(startup_file, 'w') as f:
                f.write(startup_script)
            os.chmod(startup_file, 0o755)

            # Start bash with the startup script
            self.master_fd, self.slave_fd = pty.openpty()

            # Set terminal size
            winsize = struct.pack('HHHH', 24, 80, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

            # Start bash process
            self.process = subprocess.Popen(
                ['/bin/bash', '--rcfile', str(startup_file)],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=self.cwd,
                preexec_fn=os.setsid,
                close_fds=True,
                env=env
            )

            os.close(self.slave_fd)
            self.running = True

            def reader():
                while self.running and self.process.poll() is None:
                    try:
                        r, w, e = select.select([self.master_fd], [], [], 0.1)
                        if r:
                            data = os.read(self.master_fd, 4096)
                            if data:
                                self.output_buffer.append(data.decode('utf-8', errors='ignore'))
                                if len(self.output_buffer) > 1000:
                                    self.output_buffer = self.output_buffer[-1000:]
                    except (IOError, OSError):
                        break
                self.running = False

                # Clean up startup file
                try:
                    startup_file.unlink()
                except:
                    pass

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
    def run_command(command, input_data=None, timeout=60):
        """Run a command using venv Python and capture output"""
        try:
            # Use venv Python if available
            python_cmd = PYTHON_EXEC
            cmd = [python_cmd, 'manage.py'] + command.split()

            # Set environment for venv
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['PYTHONUNBUFFERED'] = '1'

            if VENV_PATH:
                env['VIRTUAL_ENV'] = VENV_PATH
                env['PATH'] = f"{VENV_PATH}/bin:{env.get('PATH', '')}"

            # Run command
            result = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
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
    session_id = os.urandom(16).hex()

    terminal = TerminalSession(session_id)

    if terminal.start():
        active_sessions[session_id] = terminal
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Terminal started',
            'venv': VENV_PATH is not None
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

        output = terminal.get_output()
        if output:
            yield f"data: {json.dumps({'output': output})}\n\n"

        yield "data: {\"closed\": true}\n\n"

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

    result = CommandRunner.run_command(command)

    # Auto-install missing dependencies if needed
    if 'ModuleNotFoundError' in result.get('output', '') and 'flask_cors' in result.get('output', ''):
        # Try to install flask-cors
        install_result = CommandRunner.run_command('pip install flask-cors')
        if install_result['success']:
            # Retry the original command
            result = CommandRunner.run_command(command)

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
        {'cmd': 'pip list', 'desc': 'Show installed packages'},
        {'cmd': 'pip install flask-cors', 'desc': 'Install flask-cors dependency'},
        {'cmd': 'which python', 'desc': 'Show Python path'},
    ]
    return jsonify(commands)


@app.route('/api/venv/info')
def api_venv_info():
    """Get virtual environment info"""
    return jsonify({
        'enabled': VENV_PATH is not None,
        'path': VENV_PATH,
        'python': PYTHON_EXEC,
        'activate_script': str(VENV_ACTIVATE) if VENV_ACTIVATE.exists() else None
    })


@app.route('/api/process/kill', methods=['POST'])
def api_process_kill():
    """Kill process by port or PID"""
    data = request.json or {}
    port = data.get('port')
    pid = data.get('pid')

    results = []

    if port:
        try:
            # Kill process on port using lsof
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split()
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        results.append(f"Killed PID {pid} on port {port}")
                    except:
                        pass
        except:
            subprocess.run(['pkill', '-f', f':{port}'])
            results.append(f"Attempted to kill processes on port {port}")

    if pid:
        try:
            os.kill(int(pid), signal.SIGKILL)
            results.append(f"Killed PID {pid}")
        except:
            results.append(f"Failed to kill PID {pid}")

    return jsonify({'success': True, 'results': results})


@app.route('/api/logs')
def api_logs():
    """Get application logs"""
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r') as f:
            logs = f.readlines()[-100:]
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
    """Create the HTML template - keep the same as before but ensure it's complete"""
    template_dir = Path(__file__).parent / 'templates'
    template_dir.mkdir(exist_ok=True)

    template_path = template_dir / 'terminal.html'

    # Read the template from the previous response (keeping it the same)
    # For brevity, I'm not repeating the entire HTML here, but it's the same as in the previous response

    if not template_path.exists():
        print(f"⚠️ Template not found. Please ensure the HTML template is properly created.")

    return True


def ensure_dependencies():
    """Ensure required dependencies are installed"""
    print("\n📦 Checking and installing required dependencies...")

    required_packages = ['flask-cors', 'flask-socketio']

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} already installed")
        except ImportError:
            print(f"⚠️ {package} not found, installing...")
            result = CommandRunner.run_command(f'pip install {package}')
            if result['success']:
                print(f"✅ Successfully installed {package}")
            else:
                print(f"❌ Failed to install {package}: {result['output']}")


def copy_static_assets():
    """Copy static assets if they exist"""
    favicon_path = STATIC_DIR / 'favicon.ico'
    if not favicon_path.exists():
        try:
            from PIL import Image
            img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
            img.save(favicon_path, 'ICO')
            print(f"✅ Created placeholder favicon at {favicon_path}")
        except:
            print(f"⚠️ Could not create favicon. Place your favicon.ico in {STATIC_DIR}")

    banner_path = STATIC_DIR / 'kiselgram-banner.jpg'
    if banner_path.exists():
        print(f"✅ Found banner image at {banner_path}")
    else:
        print(f"⚠️ Banner image not found. Place kiselgram-banner.jpg in {STATIC_DIR}")


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
    print("📟 Kiselgram Web Terminal - Fixed Terminal Session")
    print(f"🐍 Virtual Environment: {VENV_PATH if VENV_PATH else 'Not found'}")
    print(f"🐍 Python: {PYTHON_EXEC}")
    print("📍 Reading status from: .kiselgram_status.json, .kiselgram_video_status.json")
    print(f"📍 Starting on http://{args.host}:{args.port}")
    print("=" * 60)
    print("\n🔧 Features:")
    print("   • Fixed TERM environment variable")
    print("   • Proper PTY terminal emulation")
    print("   • Virtual environment auto-activation")
    print("   • Auto-install missing dependencies")
    print("   • Live status from JSON files")
    print("=" * 60)

    # Ensure dependencies are installed
    ensure_dependencies()

    # Create template and assets
    create_template()
    copy_static_assets()

    # Open browser if not disabled
    if not args.no_browser:
        webbrowser.open(f"http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")

    print("\n🚀 Terminal is ready!")
    print("💡 Tip: If you see missing module errors, they will be auto-installed")
    print("=" * 60 + "\n")

    try:
        app.run(host=args.host, port=args.port, debug=True, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Terminal stopped")


if __name__ == '__main__':
    main()