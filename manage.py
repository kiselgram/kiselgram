#!/usr/bin/env python3
"""
Kiselgram Management Script
Complete Messaging Platform with Groups, Channels & File Support
"""

import os
import sys
import argparse
import platform
import time
import webbrowser
import socket
import subprocess
import threading
import signal
import atexit
import json
import logging
import logging.handlers
import secrets
import re
from pathlib import Path
from datetime import datetime

# ----------------------------------------------------------------------
# Try to import pyfiglet for fancy ASCII art (optional)
# ----------------------------------------------------------------------
try:
    import pyfiglet
    HAS_PYFIGLET = True
except ImportError:
    HAS_PYFIGLET = False

# ----------------------------------------------------------------------
# Try to import TOML support
# ----------------------------------------------------------------------
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# Try to import requests for API calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ----------------------------------------------------------------------
# Global state for subprocesses and file handles
# ----------------------------------------------------------------------
flask_process = None
video_process = None
is_running = False
STATUS_FILE = 'status/kiselgram.json'
VIDEO_STATUS_FILE = 'status/kiselgram-video.json'
TOKEN_FILE = '.kiselgram_token'

# Logger instances and file handles (kept as global for cleanup)
kiselgram_logger = None
video_logger = None
main_logger = None
kiselgram_log_fh = None
video_log_fh = None
main_log_fh = None

# ----------------------------------------------------------------------
# Smart terminal detection
# ----------------------------------------------------------------------
is_tty = sys.stdin.isatty() and sys.stdout.isatty()

# ----------------------------------------------------------------------
# Animate + Out – smooth rainbow banner (embedded)
# ----------------------------------------------------------------------
class Animate:
    """Rainbow‑cycling ASCII banner with optional Enter‑to‑stop."""

    def __init__(self, fps=60, enter_escape=False):
        self.fps = fps
        self._enter_escape = enter_escape
        self._lines = []
        self._stop_event = threading.Event()
        self._animating = False
        self._lock = threading.Lock()
        self._last_color = "\033[38;5;196m"  # fallback red

    def print(self, text):
        with self._lock:
            self._lines.append(text)

    def accii(self, text, font="standard"):
        if not HAS_PYFIGLET:
            self.print(f"[pyfiglet not installed – plain text]")
            return
        try:
            art = pyfiglet.figlet_format(text, font=font)
            for line in art.splitlines():
                if line.strip():
                    self._lines.append(line)
        except Exception as e:
            self.print(f"[ASCII error: {e}]")

    @property
    def enter_escape(self):
        return self._enter_escape

    @enter_escape.setter
    def enter_escape(self, value):
        self._enter_escape = value

    def start(self):
        """Start the animation (blocking). Returns Out if stopped by Enter."""
        if not is_tty:
            print("Terminal not interactive – animation disabled.")
            return None

        # Save terminal settings for raw mode if needed
        old_settings = None
        if self._enter_escape:
            try:
                import termios, tty
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin.fileno())
            except Exception:
                pass

        self._animating = True
        self._stop_event.clear()
        frame = 0

        def rainbow(step):
            hue = (step % 255) / 255.0
            r, g, b = self._hsv_to_rgb(hue, 1, 1)
            return f"\033[38;2;{r};{g};{b}m"

        try:
            print("\033[?25l", end="")  # hide cursor
            last_lines = 0
            while not self._stop_event.is_set():
                with self._lock:
                    lines = self._lines.copy()
                if not lines:
                    time.sleep(0.05)
                    continue

                if last_lines > 0:
                    print(f"\033[{last_lines}A", end="")

                color = rainbow(frame)
                self._last_color = color
                for line in lines:
                    print(f"\033[48;5;0m{color}{line}\033[0m")
                sys.stdout.flush()
                last_lines = len(lines)
                frame += 1
                time.sleep(1 / self.fps)

        except KeyboardInterrupt:
            pass
        finally:
            self._animating = False
            print("\033[?25h", end="")  # show cursor
            print("\033[0m", end="")    # reset colors
            if self._enter_escape and old_settings:
                try:
                    import termios
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                except:
                    pass
            return Out(self._last_color) if self._enter_escape else None

    def stop(self):
        self._stop_event.set()

    def is_animating(self):
        return self._animating

    @staticmethod
    def _hsv_to_rgb(h, s, v):
        i = int(h * 6)
        f = h * 6 - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)
        i %= 6
        if i == 0:   r, g, b = v, t, p
        elif i == 1: r, g, b = q, v, p
        elif i == 2: r, g, b = p, v, t
        elif i == 3: r, g, b = p, q, v
        elif i == 4: r, g, b = t, p, v
        else:        r, g, b = v, p, q
        return (int(r * 5), int(g * 5), int(b * 5))


class Out:
    """Colour‑aware print/input using the rainbow colour from the banner."""

    def __init__(self, color):
        self.color = color
        self._orig_print = print
        self._orig_input = input

    def print(self, *args, sep=' ', end='\n', flush=False):
        text = sep.join(str(a) for a in args)
        self._orig_print(f"\033[48;5;0m{self.color}{text}\033[0m", end=end, flush=flush)

    def input(self, prompt=""):
        self._orig_print(f"\033[48;5;0m{self.color}{prompt}\033[0m", end="")
        return self._orig_input()

    def activate(self):
        import builtins
        builtins.print = self.print
        builtins.input = self.input

    def deactivate(self):
        import builtins
        builtins.print = self._orig_print
        builtins.input = self._orig_input

    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, *args):
        self.deactivate()


# ----------------------------------------------------------------------
# Logging setup (original, unchanged)
# ----------------------------------------------------------------------
def setup_logging(config=None):
    global kiselgram_logger, video_logger, main_logger
    global kiselgram_log_fh, video_log_fh, main_log_fh

    log_settings = {
        'kiselgram': {'file': 'kiselgram.log', 'level': 'INFO', 'max_bytes': 10485760, 'backup_count': 5},
        'video': {'file': 'kis_vid.log', 'level': 'INFO', 'max_bytes': 10485760, 'backup_count': 5},
        'main': {'file': 'kis_main.log', 'level': 'INFO', 'max_bytes': 10485760, 'backup_count': 5}
    }

    if config and 'logging' in config:
        if 'kiselgram' in config['logging']:
            log_settings['kiselgram'].update(config['logging']['kiselgram'])
        if 'video' in config['logging']:
            log_settings['video'].update(config['logging']['video'])
        if 'main' in config['logging']:
            log_settings['main'].update(config['logging']['main'])

    Path('logs').mkdir(exist_ok=True)

    log_format = "%(asctime)s - %(name)s - %(levelname)s : %(message)s"
    formatter = logging.Formatter(log_format)

    # kiselgram logger
    kiselgram_logger = logging.getLogger('kiselgram')
    kiselgram_logger.setLevel(getattr(logging, log_settings['kiselgram']['level'].upper()))
    kiselgram_logger.handlers.clear()
    h1 = logging.handlers.RotatingFileHandler(
        f"logs/{log_settings['kiselgram']['file']}",
        maxBytes=log_settings['kiselgram']['max_bytes'],
        backupCount=log_settings['kiselgram']['backup_count'],
        encoding='utf-8'
    )
    h1.setFormatter(formatter)
    kiselgram_logger.addHandler(h1)
    kiselgram_log_fh = open(f"logs/{log_settings['kiselgram']['file']}", 'a', encoding='utf-8')

    # video logger
    video_logger = logging.getLogger('video')
    video_logger.setLevel(getattr(logging, log_settings['video']['level'].upper()))
    video_logger.handlers.clear()
    h2 = logging.handlers.RotatingFileHandler(
        f"logs/{log_settings['video']['file']}",
        maxBytes=log_settings['video']['max_bytes'],
        backupCount=log_settings['video']['backup_count'],
        encoding='utf-8'
    )
    h2.setFormatter(formatter)
    video_logger.addHandler(h2)
    video_log_fh = open(f"logs/{log_settings['video']['file']}", 'a', encoding='utf-8')

    # main logger
    main_logger = logging.getLogger('main')
    main_logger.setLevel(getattr(logging, log_settings['main']['level'].upper()))
    main_logger.handlers.clear()
    h3 = logging.handlers.RotatingFileHandler(
        f"logs/{log_settings['main']['file']}",
        maxBytes=log_settings['main']['max_bytes'],
        backupCount=log_settings['main']['backup_count'],
        encoding='utf-8'
    )
    h3.setFormatter(formatter)
    main_logger.addHandler(h3)
    main_log_fh = open(f"logs/{log_settings['main']['file']}", 'a', encoding='utf-8')

    return True


def log_main(level, message, domain='general'):
    if main_logger:
        getattr(main_logger, level.lower())(f"{domain} - {message}")


# ----------------------------------------------------------------------
# Shutdown token (original)
# ----------------------------------------------------------------------
def get_shutdown_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    token = secrets.token_urlsafe(32)
    with open(TOKEN_FILE, 'w') as f:
        f.write(token)
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except:
        pass
    return token


SHUTDOWN_TOKEN = get_shutdown_token()


# ----------------------------------------------------------------------
# Config loading (original)
# ----------------------------------------------------------------------
def load_config():
    config = {}
    config_paths = ['config/kis.toml', 'kis-1.toml']
    config_file = None
    for path in config_paths:
        if os.path.exists(path):
            config_file = path
            break
    if not config_file:
        print("⚠️  Config file not found, using defaults")
        return create_default_config()
    if tomllib is None:
        print("❌ TOML support not available. Use Python 3.11+ or install tomli")
        return create_default_config()
    try:
        with open(config_file, 'rb') as f:
            config = tomllib.load(f)
        print(f"✅ Loaded config from {config_file}")
        setup_logging(config)
        return config
    except Exception as e:
        print(f"❌ Config error: {e}")
        setup_logging()
        return create_default_config()


def create_default_config():
    default = '''# Kiselgram Configuration

[app]
name = "Kiselgram"
version = "3.0.0"
debug = true
host = "0.0.0.0"
port = 5000

[database]
url = "sqlite:///kiselgram.db"

[video]
enabled = true
host = "0.0.0.0"
port = 5001

[logging]
level = "INFO"
'''
    os.makedirs('config', exist_ok=True)
    with open('config/kis.toml', 'w') as f:
        f.write(default)
    print("✅ Created default kis.toml")
    setup_logging()
    return {'app': {'port': 5000, 'host': '0.0.0.0', 'debug': True},
            'video': {'port': 5001, 'host': '0.0.0.0', 'enabled': True}}


# ----------------------------------------------------------------------
# Original static header (kept as fallback)
# ----------------------------------------------------------------------
def print_header():
    print("\n" + "=" * 74)
    print("  ____      __ __ _________ ________    __________  ___    __  ___   ____")
    print(" / / /     / //_//  _/ ___// ____/ /   / ____/ __ \\/   |  /  |/  /   \\ \\ \\")
    print("/ / /     / ,<   / / \\__ \\/ __/ / /   / / __/ /_/ / /| | / /|_/ /     \\ \\ \\")
    print("\\ \\ \\    / /| |_/ / ___/ / /___/ /___/ /_/ / _, _/ ___ |/ /  / /      / / /")
    print(" \\_\\_\\  /_/ |_/___//____/_____/_____/\\____/_/ |_/_/  |_/_/  /_/      /_/_/")
    print("=" * 74)
    print("📱 Complete Messaging Platform v3.0")
    print("👥 Groups | 📢 Channels | 📁 File Support | 🤖 Bots | 🎥 Video Server")
    print("=" * 74)


# ----------------------------------------------------------------------
# Animated header (new)
# ----------------------------------------------------------------------
def print_animated_header(enter_escape=True):
    """Display a rainbow‑cycling banner, stop on Enter, return Out colour helper."""
    if not is_tty:
        print_header()
        return None

    anim = Animate(fps=60, enter_escape=enter_escape)
    anim.print("=" * 74)
    if HAS_PYFIGLET:
        anim.accii("Kiselgram", font="slant")
    else:
        anim.print("  ____      __ __ _________ ________    __________  ___    __  ___   ____")
        anim.print(" / / /     / //_//  _/ ___// ____/ /   / ____/ __ \\/   |  /  |/  /   \\ \\ \\")
        anim.print("/ / /     / ,<   / / \\__ \\/ __/ / /   / / __/ /_/ / /| | / /|_/ /     \\ \\ \\")
        anim.print("\\ \\ \\    / /| |_/ / ___/ / /___/ /___/ /_/ / _, _/ ___ |/ /  / /      / / /")
        anim.print(" \\_\\_\\  /_/ |_/___//____/_____/_____/\\____/_/ |_/_/  |_/_/  /_/      /_/_/")
    anim.print("=" * 74)
    anim.print("📱 Complete Messaging Platform v3.0")
    anim.print("👥 Groups | 📢 Channels | 📁 File Support | 🤖 Bots | 🎥 Video Server")
    anim.print("=" * 74)
    anim.print("Press ENTER to continue...")

    # Clear screen before and after animation
    print("\033[2J\033[H", end="")
    try:
        out = anim.start()
    finally:
        print("\033[2J\033[H", end="")
    return out


# ----------------------------------------------------------------------
# Port & process helpers (unchanged)
# ----------------------------------------------------------------------
def check_dependencies():
    print("\n📦 Checking dependencies...")
    required = ['flask', 'flask_sqlalchemy', 'dotenv', 'PIL']
    ok = True
    for dep in required:
        try:
            __import__(dep.replace('-', '_'))
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} - pip install {dep}")
            ok = False
    return ok


def check_port_available(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0
    except:
        return True


def save_status(port, pid, service='main'):
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    Path(status_file).parent.mkdir(parents=True, exist_ok=True)
    status = {'running': True, 'port': port, 'pid': pid, 'service': service,
              'started_at': datetime.now().isoformat()}
    with open(status_file, 'w') as f:
        json.dump(status, f)


def load_status(service='main'):
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                return json.load(f)
        except:
            return None
    return None


def clear_status(service='main'):
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    if os.path.exists(status_file):
        os.remove(status_file)


def kill_process_on_port(port):
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                    print(f"✓ Killed PID {pid} on port {port}")
        else:
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                if result.stdout.strip():
                    for pid in result.stdout.strip().split():
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            time.sleep(0.5)
                            os.kill(int(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        print(f"✓ Killed PID {pid} on port {port}")
            except FileNotFoundError:
                subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)
                print(f"✓ Sent kill to port {port}")
    except Exception as e:
        print(f"⚠️  Kill error: {e}")


def stop_application(service='all'):
    if service in ('all', 'main'):
        status = load_status('main')
        if status:
            kill_process_on_port(status.get('port', 5000))
        clear_status('main')
        subprocess.run(['pkill', '-f', 'run_kiselgram.py'], capture_output=True)
        print("✅ Main app stopped")

    if service in ('all', 'video'):
        vstatus = load_status('video')
        if vstatus:
            kill_process_on_port(vstatus.get('port', 5001))
        clear_status('video')
        subprocess.run(['pkill', '-f', 'run_video_server.py'], capture_output=True)
        print("✅ Video server stopped")

    for tmp in ['/tmp/run_kiselgram.py', '/tmp/run_video_server.py']:
        if os.path.exists(tmp):
            os.remove(tmp)
    return True


# ----------------------------------------------------------------------
# Smart Flask output processor (unchanged from previous)
# ----------------------------------------------------------------------
def process_flask_output(line, source='stderr', state=None):
    if state is None:
        state = {}
    line = line.rstrip('\n\r')
    if not line:
        return

    # Debug PIN
    pin_match = re.match(r'.*Debugger PIN:\s*(\S+)', line)
    if pin_match:
        state['debug_pin'] = pin_match.group(1)
        print(f"\n--------------------- NEW DEBUG PIN: {state['debug_pin']} ----------------------------------\n")
        return

    # Change detection
    change_match = re.match(r'.*Detected change in (.+), reloading', line)
    if change_match:
        path = change_match.group(1)
        print(f"\n--------------------- DETECTED CHANGE!! in {path} ---------------------------------\n")
        kiselgram_logger.info(f"Detected change in {path}, reloading")
        return

    # Startup
    run_match = re.match(r'.*Running on http://127\.0\.0\.1:(\d+)', line)
    if run_match:
        port = run_match.group(1)
        state['port'] = port
        print(f"\n------------- STARTED FLASK ON PORT {port} ---------------------------")
        if 'debug_pin' in state:
            print(f"---------------------- Debug pin: {state['debug_pin']} -------------------------------------\n")
        kiselgram_logger.info(f"Flask started on port {port}")
        return

    # Traceback
    if line.startswith('Traceback (most recent call last):'):
        state['in_traceback'] = True
        state['traceback_lines'] = [line]
        return
    if state.get('in_traceback'):
        state['traceback_lines'].append(line)
        if line and not line.startswith(' ') and re.match(r'\S', line):
            full = '\n'.join(state['traceback_lines'])
            kiselgram_logger.error(f"Unhandled exception:\n{full}")
            print(f"\n❌ ERROR: {line}\n")
            state['in_traceback'] = False
            state['traceback_lines'] = []
        return

    # HTTP access log
    access_match = re.match(r'^(?P<ip>\S+) \S+ \S+ \[.*?\] "(?P<method>\S+) .*?" (?P<status>\d{3})', line)
    if access_match:
        method = access_match.group('method')
        status = int(access_match.group('status'))
        if status in (200, 304):
            level = 'debug'
        elif status == 404:
            level = 'warning'
        elif status >= 500:
            level = 'error'
        else:
            level = 'info'
        if method == 'POST':
            upgrade = {'debug': 'info', 'warning': 'error'}
            level = upgrade.get(level, level)
        getattr(kiselgram_logger, level)(f"{method} {status} {line}")
        short = line.split(']"')[-1].strip() if ']"' in line else line
        print(f"[{level.upper():7s}] {method} {status}   {short}")
        return

    kiselgram_logger.info(line)


def run_flask_app(host, port, debug, no_browser=False):
    global flask_process, is_running
    host = host or '0.0.0.0'
    port = int(port) if port else 5000

    try:
        env = os.environ.copy()
        env['FLASK_ENV'] = 'development' if debug else 'production'
        env['KISELGRAM_TOKEN'] = SHUTDOWN_TOKEN

        runner = f'''#!/usr/bin/env python3
import sys, os
project_root = "{os.getcwd()}"
os.chdir(project_root)
sys.path.insert(0, project_root)

from app import create_app, db
from app.utils.bot_utils import setup_bots

app = create_app()
with app.app_context():
    db.create_all()
    setup_bots()

if __name__ == '__main__':
    print("\\n🚀 Kiselgram starting...", flush=True)
    app.run(host='{host}', port={port}, debug={debug})
'''
        runner_path = '/tmp/run_kiselgram.py'
        with open(runner_path, 'w') as f:
            f.write(runner)
        os.chmod(runner_path, 0o755)

        cmd = [sys.executable, runner_path]
        print(f"🚀 Starting Flask on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        print(f"🔑 Shutdown token: {SHUTDOWN_TOKEN}")

        flask_process = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, bufsize=1, cwd=os.getcwd()
        )
        is_running = True
        save_status(port, flask_process.pid, 'main')

        state = {'debug_pin': None, 'port': str(port), 'in_traceback': False, 'traceback_lines': []}

        def read_stdout():
            for line in flask_process.stdout:
                process_flask_output(line, 'stdout', state)
                main_log_fh.write(line)
                main_log_fh.flush()

        def read_stderr():
            for line in flask_process.stderr:
                process_flask_output(line, 'stderr', state)
                kiselgram_log_fh.write(line)
                kiselgram_log_fh.flush()

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()

        if not no_browser:
            def open_browser():
                time.sleep(3)
                webbrowser.open(f"http://localhost:{port}")
            threading.Thread(target=open_browser, daemon=True).start()

        return True
    except Exception as e:
        print(f"❌ Error starting Flask: {e}")
        log_main('ERROR', f'Flask start error: {e}', 'flask')
        return False


# ----------------------------------------------------------------------
# Video server (original)
# ----------------------------------------------------------------------
def run_video_server_process(port=5001, host='0.0.0.0'):
    global video_process
    host = host or '0.0.0.0'
    port = int(port) if port else 5001

    try:
        env = os.environ.copy()
        env['VIDEO_PORT'] = str(port)
        env['VIDEO_HOST'] = host

        runner = f'''#!/usr/bin/env python3
import sys, os
project_root = "{os.getcwd()}"
os.chdir(project_root)
sys.path.insert(0, project_root)

try:
    from video_server.app import app as video_app
    from flask_socketio import SocketIO
    socketio = SocketIO(video_app, cors_allowed_origins="*")
    if __name__ == '__main__':
        print("\\n🎥 Video Server is running!")
        print(f"🌐 Access at: http://localhost:{port}")
        socketio.run(video_app, host='{host}', port={port}, debug=False)
except ImportError:
    print("❌ video_server/ not found")
'''
        runner_path = '/tmp/run_video_server.py'
        with open(runner_path, 'w') as f:
            f.write(runner)
        os.chmod(runner_path, 0o755)

        cmd = [sys.executable, runner_path]
        print(f"🎥 Starting Video Server on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")

        video_process = subprocess.Popen(
            cmd, env=env,
            stdout=video_log_fh, stderr=kiselgram_log_fh,
            universal_newlines=True, bufsize=1, cwd=os.getcwd()
        )
        save_status(port, video_process.pid, 'video')
        return True
    except Exception as e:
        print(f"❌ Video server error: {e}")
        return False


# ----------------------------------------------------------------------
# start_all_services – now uses animated header
# ----------------------------------------------------------------------
def start_all_services(args):
    # Animated header, blocking until Enter
    out = print_animated_header(enter_escape=True)
    if out:
        # Use the colour for subsequent messages inside this function
        out.activate()
        try:
            _start_all_services_internal(args)
        finally:
            out.deactivate()
    else:
        _start_all_services_internal(args)


def _start_all_services_internal(args):
    """Original start logic, but can be wrapped with coloured print."""
    config = load_config()

    main_port = getattr(args, 'port', None) or config.get('app', {}).get('port', 5000)
    main_host = getattr(args, 'host', None) or config.get('app', {}).get('host', '0.0.0.0')
    debug = getattr(args, 'debug', None) or config.get('app', {}).get('debug', True)
    no_video = getattr(args, 'no_video', False)
    video_port = getattr(args, 'video_port', None) or config.get('video', {}).get('port', 5001)
    video_host = getattr(args, 'video_host', None) or config.get('video', {}).get('host', '0.0.0.0')
    no_browser = getattr(args, 'no_browser', False)

    if not check_dependencies():
        print("\n❌ Missing dependencies. Install with: pip install -r requirements.txt")
        return False

    if not check_port_available(main_port):
        print(f"\n❌ Port {main_port} already in use!")
        return False

    stop_application('all')
    time.sleep(1)

    main_url = f"http://{main_host if main_host != '0.0.0.0' else 'localhost'}:{main_port}"
    video_url = f"http://{video_host if video_host != '0.0.0.0' else 'localhost'}:{video_port}" if not no_video else "DISABLED"

    print(f"\n🚀 Starting Kiselgram services...")
    print(f"   Main App: {main_url}")
    print(f"   Video Server: {video_url}")
    print(f"   Debug: {debug}")
    print(f"   Open Browser: {not no_browser}")
    print("-" * 40)

    threading.Thread(target=run_flask_app, args=(main_host, main_port, debug, no_browser), daemon=True).start()

    if not no_video:
        time.sleep(2)
        threading.Thread(target=run_video_server_process, args=(video_port, video_host), daemon=True).start()

    time.sleep(3)
    print("\n" + "=" * 40)
    print("✅ Services started!")
    print(f"🌐 Main App: {main_url}")
    print(f"🔑 Shutdown token: {SHUTDOWN_TOKEN}")
    print("\n🛑 To stop: python manage.py stop")
    print("Press Ctrl+C to exit (services continue running)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Management script stopped. Services continue running.")
        print("   Use 'python manage.py stop' to stop services")
    return True


# ----------------------------------------------------------------------
# CLI entry point (unchanged)
# ----------------------------------------------------------------------
def main():
    setup_logging()
    parser = argparse.ArgumentParser(description='Kiselgram Management Script')
    subparsers = parser.add_subparsers(dest='command', help='Command')

    # start
    sp = subparsers.add_parser('start', help='Start services')
    sp.add_argument('--port', type=int)
    sp.add_argument('--host')
    sp.add_argument('--debug', action='store_true')
    sp.add_argument('--no-debug', dest='debug', action='store_false')
    sp.add_argument('--no-browser', action='store_true')
    sp.add_argument('--no-video', action='store_true')
    sp.add_argument('--video-port', type=int)
    sp.add_argument('--video-host')

    # stop
    subparsers.add_parser('stop', help='Stop services')

    # restart
    rp = subparsers.add_parser('restart', help='Restart services')
    rp.add_argument('--port', type=int)
    rp.add_argument('--host')
    rp.add_argument('--no-video', action='store_true')

    # status
    subparsers.add_parser('status', help='Check status')
    subparsers.add_parser('setup', help='Setup environment')
    subparsers.add_parser('clean', help='Clean temporary files')
    subparsers.add_parser('reset-db', help='Reset database')
    subparsers.add_parser('test', help='Run tests')
    subparsers.add_parser('help', help='Show help')

    args = parser.parse_args()
    if not args.command:
        print_header()  # fallback for unknown command
        print("\n❌ No command. Use 'python manage.py help'")
        return

    if args.command == 'start':
        start_all_services(args)
    elif args.command == 'stop':
        print_header()
        print("\n🛑 Stopping all services...")
        stop_application('all')
    elif args.command == 'restart':
        out = print_animated_header(enter_escape=True)  # show banner again
        if out:
            with out:
                print("\n🔄 Restarting all services...")
                stop_application('all')
                time.sleep(2)
                _start_all_services_internal(args)
        else:
            print("🔄 Restarting...")
            stop_application('all')
            time.sleep(2)
            start_all_services(args)
    elif args.command == 'status':
        print_header()
        main_s = load_status('main')
        video_s = load_status('video')
        print("\n📊 Service Status")
        print("-" * 40)
        print(f"Main App: {'✅ RUNNING' if main_s else '❌ NOT RUNNING'} {f'on port {main_s["port"]}' if main_s else ''}")
        print(f"Video Server: {'✅ RUNNING' if video_s else '❌ NOT RUNNING'} {f'on port {video_s["port"]}' if video_s else ''}")
    elif args.command == 'setup':
        print_header()
        print("\n🔧 Setting up environment...")
        os.makedirs('uploads/images', exist_ok=True)
        os.makedirs('uploads/documents', exist_ok=True)
        os.makedirs('uploads/media', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        os.makedirs('status', exist_ok=True)
        create_default_config()
        print("\n✅ Setup completed!")
        print("Next: pip install -r requirements.txt && python manage.py start")
    elif args.command == 'clean':
        print_header()
        print("\n🧹 Cleaning temporary files...")
        for tmp in ['/tmp/run_kiselgram.py', '/tmp/run_video_server.py']:
            if os.path.exists(tmp):
                os.remove(tmp)
        print("✅ Cleanup done")
    elif args.command == 'reset-db':
        print_header()
        confirm = input("\n⚠️  This will DELETE ALL DATA! Type 'yes' to continue: ")
        if confirm.lower() == 'yes':
            for db in ['kiselgram.db', 'instance/kiselgram.db']:
                if os.path.exists(db):
                    os.remove(db)
                    print(f"✓ Removed {db}")
            print("✅ Database reset")
    elif args.command == 'test':
        print_header()
        print("\n🧪 Running tests...")
        if check_dependencies():
            print("✅ All basic tests passed!")
        else:
            print("❌ Some tests failed")
    elif args.command == 'help':
        print_header()
        print("\n📚 Commands:")
        print("  start              - Start all services")
        print("  stop               - Stop all services")
        print("  restart            - Restart all services")
        print("  status             - Check service status")
        print("  setup              - Setup environment")
        print("  clean              - Clean temporary files")
        print("  reset-db           - Reset database")
        print("  test               - Run tests")
        print("\nOptions:")
        print("  --port PORT        - Main app port (default: 5000)")
        print("  --no-video         - Disable video server")
        print("  --no-browser       - Don't open browser")
        print("  --video-port PORT  - Video server port (default: 5001)")


def cleanup():
    for fh in [kiselgram_log_fh, video_log_fh, main_log_fh]:
        if fh:
            try: fh.close()
            except: pass

atexit.register(cleanup)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)