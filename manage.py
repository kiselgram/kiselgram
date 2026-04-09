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
from pathlib import Path
from datetime import datetime

# Try to import TOML support
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

# Global variables for managing processes
flask_process = None
video_process = None
is_running = False
process_pid = None
STATUS_FILE = 'status/kiselgram.json'
VIDEO_STATUS_FILE = 'status/kiselgram-video.json'
TOKEN_FILE = '.kiselgram_token'

# Logger instances and file handles
kiselgram_logger = None
video_logger = None
main_logger = None
kiselgram_log_fh = None
video_log_fh = None
main_log_fh = None


class KiselgramFormatter(logging.Formatter):
    """Custom formatter for kiselgram.log"""

    def format(self, record):
        service = getattr(record, 'service', 'kiselgram')
        domain = getattr(record, 'domain', 'general')
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        return f"{service} - {domain} - {record.levelname} - {timestamp}: {record.getMessage()}"


class VideoFormatter(logging.Formatter):
    """Custom formatter for kis_vid.log"""

    def format(self, record):
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        return f"{record.levelname} - {timestamp}: {record.getMessage()}"


class MainFormatter(logging.Formatter):
    """Custom formatter for kis_main.log"""

    def format(self, record):
        domain = getattr(record, 'domain', 'general')
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        return f"{domain} - {record.levelname} - {timestamp}: {record.getMessage()}"


def setup_logging(config=None):
    """Setup logging with configuration from kis.toml - file only, no console"""
    global kiselgram_logger, video_logger, main_logger
    global kiselgram_log_fh, video_log_fh, main_log_fh

    # Default log settings
    log_settings = {
        'kiselgram': {
            'file': 'kiselgram.log',
            'level': 'INFO',
            'max_bytes': 10485760,
            'backup_count': 5
        },
        'video': {
            'file': 'kis_vid.log',
            'level': 'INFO',
            'max_bytes': 10485760,
            'backup_count': 5
        },
        'main': {
            'file': 'kis_main.log',
            'level': 'INFO',
            'max_bytes': 10485760,
            'backup_count': 5
        }
    }

    # Override with config if provided
    if config and 'logging' in config:
        if 'kiselgram' in config['logging']:
            log_settings['kiselgram'].update(config['logging']['kiselgram'])
        if 'video' in config['logging']:
            log_settings['video'].update(config['logging']['video'])
        if 'main' in config['logging']:
            log_settings['main'].update(config['logging']['main'])

    # Create logs directory if it doesn't exist
    Path('logs').mkdir(exist_ok=True)

    # Setup kiselgram logger
    kiselgram_logger = logging.getLogger('kiselgram')
    kiselgram_logger.setLevel(getattr(logging, log_settings['kiselgram']['level'].upper()))
    kiselgram_logger.handlers.clear()

    kiselgram_handler = logging.handlers.RotatingFileHandler(
        f"logs/{log_settings['kiselgram']['file']}",
        maxBytes=log_settings['kiselgram']['max_bytes'],
        backupCount=log_settings['kiselgram']['backup_count'],
        encoding='utf-8'
    )
    kiselgram_handler.setFormatter(KiselgramFormatter())
    kiselgram_logger.addHandler(kiselgram_handler)
    kiselgram_logger.propagate = False

    # Store file handle for subprocess redirection
    kiselgram_log_fh = open(f"logs/{log_settings['kiselgram']['file']}", 'a', encoding='utf-8')

    # Setup video logger
    video_logger = logging.getLogger('video')
    video_logger.setLevel(getattr(logging, log_settings['video']['level'].upper()))
    video_logger.handlers.clear()

    video_handler = logging.handlers.RotatingFileHandler(
        f"logs/{log_settings['video']['file']}",
        maxBytes=log_settings['video']['max_bytes'],
        backupCount=log_settings['video']['backup_count'],
        encoding='utf-8'
    )
    video_handler.setFormatter(VideoFormatter())
    video_logger.addHandler(video_handler)
    video_logger.propagate = False

    # Store file handle for subprocess redirection
    video_log_fh = open(f"logs/{log_settings['video']['file']}", 'a', encoding='utf-8')

    # Setup main logger
    main_logger = logging.getLogger('main')
    main_logger.setLevel(getattr(logging, log_settings['main']['level'].upper()))
    main_logger.handlers.clear()

    main_handler = logging.handlers.RotatingFileHandler(
        f"logs/{log_settings['main']['file']}",
        maxBytes=log_settings['main']['max_bytes'],
        backupCount=log_settings['main']['backup_count'],
        encoding='utf-8'
    )
    main_handler.setFormatter(MainFormatter())
    main_logger.addHandler(main_handler)
    main_logger.propagate = False

    # Store file handle for subprocess redirection
    main_log_fh = open(f"logs/{log_settings['main']['file']}", 'a', encoding='utf-8')

    return True


def log_kiselgram(level, message, service='kiselgram', domain='general'):
    """Log to kiselgram.log"""
    if kiselgram_logger:
        extra = {'service': service, 'domain': domain}
        getattr(kiselgram_logger, level.lower())(message, extra=extra)


def log_video(level, message):
    """Log to kis_vid.log"""
    if video_logger:
        getattr(video_logger, level.lower())(message)


def log_main(level, message, domain='general'):
    """Log to kis_main.log"""
    if main_logger:
        extra = {'domain': domain}
        getattr(main_logger, level.lower())(message, extra=extra)


def get_shutdown_token():
    """Get or create shutdown token"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    else:
        token = secrets.token_urlsafe(32)
        with open(TOKEN_FILE, 'w') as f:
            f.write(token)
        try:
            os.chmod(TOKEN_FILE, 0o600)  # Restrict permissions on Unix-like systems
        except:
            pass
        return token


SHUTDOWN_TOKEN = get_shutdown_token()


def load_config():
    """Load configuration from kis.toml"""
    config = {}

    config_paths = ['config/kis.toml', 'kis-1.toml']
    config_file = None

    for path in config_paths:
        if os.path.exists(path):
            config_file = path
            break

    if not config_file:
        print("⚠️  Config file not found, using default configuration")
        return create_default_config()

    if tomllib is None:
        print("❌ TOML support not available. Install tomli or use Python 3.11+")
        return create_default_config()

    try:
        with open(config_file, 'rb') as f:
            config = tomllib.load(f)
        print(f"✅ Configuration loaded from {config_file}")
        setup_logging(config)
        return config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        print("Using default configuration")
        setup_logging()
        return create_default_config()


def create_default_config():
    """Create default configuration file"""
    default_config = """# Kiselgram Configuration File

[app]
name = "Kiselgram"
version = "2.0.0"
debug = true
host = "0.0.0.0"
port = 5000
secret_key = "your-secret-key-change-in-production"

[database]
url = "sqlite:///kiselgram.db"
echo = false

[server]
workers = 4
threaded = true

[video]
enabled = true
host = "0.0.0.0"
port = 5001
quality = "medium"
max_size = 104857600
auto_start = true

[logging]

[logging.kiselgram]
file = "kiselgram.log"
level = "INFO"
max_bytes = 10485760
backup_count = 5

[logging.video]
file = "kis_vid.log"
level = "INFO"
max_bytes = 10485760
backup_count = 5

[logging.main]
file = "kis_main.log"
level = "INFO"
max_bytes = 10485760
backup_count = 5

[telegram]
bot_token = "YOUR_BOT_TOKEN_HERE"
webhook_url = ""

[uploads]
folder = "uploads"
max_size = 16777216
allowed_images = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
allowed_documents = [".pdf", ".doc", ".docx", ".txt", ".md"]
allowed_videos = [".mp4", ".avi", ".mov", ".mkv"]

[features]
groups = true
channels = true
bots = true
video_streaming = true
file_sharing = true
reactions = true
"""

    os.makedirs('config', exist_ok=True)
    with open('config/kis.toml', 'w') as f:
        f.write(default_config)
    print("✅ Created default kis.toml configuration file")

    setup_logging()

    return {
        'app': {'port': 5000, 'host': '0.0.0.0', 'debug': True},
        'video': {'port': 5001, 'host': '0.0.0.0', 'enabled': True},
        'logging': {
            'kiselgram': {'file': 'kiselgram.log', 'level': 'INFO'},
            'video': {'file': 'kis_vid.log', 'level': 'INFO'},
            'main': {'file': 'kis_main.log', 'level': 'INFO'}
        }
    }


def print_header():
    """Print fancy header for Kiselgram"""
    try:
        with open('config/banner.txt', 'r') as banner:
            printbanner = banner.read()

        with open('config/banner.txt', 'r') as banner:
            legnth = len(banner.readline())

        print("\n" + "=" * legnth)
        print(printbanner)
        print("=" * legnth)
        print("📱 Complete Messaging Platform v2.0")
        print("👥 Groups | 📢 Channels | 📁 File Support | 🤖 Bots | 🎥 Video Server")
        print("=" * legnth)

        log_kiselgram('INFO', 'Application header displayed', 'kiselgram', 'ui')
    except Exception as e:
        log_kiselgram('ERROR', f'Failed to print header: {e}', 'kiselgram', 'error')


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print(f"❌ Python 3.7+ required. Current: {platform.python_version()}")
        return False
    print(f"✅ Python {platform.python_version()}")
    return True


def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n📦 Checking dependencies...")

    required = ['flask', 'flask_sqlalchemy', 'dotenv', 'PIL']
    optional = ['pyTelegramBotAPI', 'pyfiglet', 'opencv-python']

    try:
        import importlib

        for dep in required:
            try:
                importlib.import_module(dep.replace('-', '_'))
                print(f"✅ {dep}")
            except ImportError:
                print(f"❌ {dep} - Install with: pip install {dep}")
                return False

        for dep in optional:
            try:
                importlib.import_module(dep.replace('-', '_'))
                print(f"✅ {dep} (optional)")
            except ImportError:
                print(f"⚠️  {dep} (optional - not installed)")

        return True
    except Exception as e:
        print(f"❌ Error checking dependencies: {e}")
        return False


def check_port_available(port):
    """Check if a port is available"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0
    except:
        return True


def save_status(port, pid, service='main'):
    """Save application status to file"""
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    Path(status_file).parent.mkdir(parents=True, exist_ok=True)
    status = {
        'running': True,
        'port': port,
        'pid': pid,
        'service': service,
        'started_at': datetime.now().isoformat()
    }
    with open(status_file, 'w') as f:
        json.dump(status, f)


def load_status(service='main'):
    """Load application status from file"""
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            return json.load(f)
    return None


def clear_status(service='main'):
    """Clear status file"""
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    if os.path.exists(status_file):
        os.remove(status_file)


def stop_via_api(port, token):
    """Stop the application via API call"""
    if not REQUESTS_AVAILABLE:
        log_main('WARNING', 'Requests library not available, cannot use API shutdown', 'shutdown')
        return False

    try:
        url = f"http://localhost:{port}/api/utils/test/env/shutdown"
        response = requests.post(
            url,
            headers={'X-API-Token': token},
            timeout=5
        )
        if response.status_code == 200:
            log_main('INFO', f'Successfully sent shutdown request to port {port}', 'shutdown')
            return True
        else:
            log_main('WARNING', f'API shutdown returned status {response.status_code}', 'shutdown')
            return False
    except Exception as e:
        log_main('ERROR', f'API shutdown failed: {e}', 'shutdown')
        return False


def run_flask_app(host, port, debug, no_browser=False):
    """Run Flask application in a subprocess"""
    global flask_process, process_pid, is_running

    # Ensure host and port have valid values
    if host is None or host == 'None':
        host = '0.0.0.0'
    if port is None or port == 'None':
        port = 5000
    port = int(port)

    log_main('INFO', f'Starting Flask app on {host}:{port}', 'flask')

    try:
        env = os.environ.copy()
        env['FLASK_ENV'] = 'development' if debug else 'production'
        env['KISELGRAM_TOKEN'] = SHUTDOWN_TOKEN
        host_fl = 'localhost' if 'host' != '0.0.0.0' else host

        # Create runner in /tmp but working directory is project root
        runner_content = f'''#!/usr/bin/env python3
import sys
import os

# Set working directory to project root
project_root = "{os.getcwd()}"
os.chdir(project_root)
sys.path.insert(0, project_root)

from app import create_app, db
from app.utils import setup_bots
import threading

app = create_app()

def init_database():
    with app.app_context():
        db.create_all()
        setup_bots()
        print("✓ Database initialized")

def start_bot_simulation(app):
    from app.utils import simulate_bot_interaction
    bot_thread = threading.Thread(target=simulate_bot_interaction, args=(app,), daemon=True)
    bot_thread.start()

if __name__ == '__main__':
    init_database()
    start_bot_simulation(app)
    print("\\n🚀 Kiselgram is running!")
    print(f"🌐 Access at: http:/{host_fl}:{port}")
    print("📝 Press Ctrl+C to stop\\n")
    app.run(host='{host}', port={port}, debug={debug})
'''

        # Write runner to /tmp
        runner_path = '/tmp/run_kiselgram.py'
        with open(runner_path, 'w') as f:
            f.write(runner_content)
        os.chmod(runner_path, 0o755)

        cmd = [sys.executable, runner_path]

        print(f"🚀 Starting Flask on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        print(f"🔑 Shutdown token: {SHUTDOWN_TOKEN}")

        # Open log files for redirection
        main_log_fh.seek(0, 2)  # Seek to end
        kiselgram_log_fh.seek(0, 2)  # Seek to end

        flask_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=main_log_fh,  # stdout -> kis_main.log
            stderr=kiselgram_log_fh,  # stderr -> kiselgram.log
            universal_newlines=True,
            bufsize=1,
            cwd=os.getcwd()  # Working directory is project root
        )

        process_pid = flask_process.pid
        is_running = True
        save_status(port, process_pid, 'main')

        log_main('INFO', f'Flask process started with PID {process_pid}', 'flask')

        # Monitor process in background
        def monitor_process():
            flask_process.wait()
            log_main('INFO', f'Flask process {process_pid} exited with code {flask_process.returncode}', 'flask')
            global is_running
            is_running = False
            clear_status('main')

        monitor_thread = threading.Thread(target=monitor_process, daemon=True)
        monitor_thread.start()

        # Open browser if requested
        if not no_browser:
            def open_browser():
                time.sleep(2)
                try:
                    url = f"http://localhost:{port}"
                    webbrowser.open(url)
                    log_main('INFO', f'Opened browser at {url}', 'browser')
                except Exception as e:
                    log_main('WARNING', f'Failed to open browser: {e}', 'browser')

            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()

        return True

    except Exception as e:
        print(f"❌ Error starting Flask: {e}")
        log_main('ERROR', f'Error starting Flask: {e}', 'flask')
        return False


def run_video_server_process(port=5001, host='0.0.0.0'):
    """Run video server in a subprocess"""
    global video_process

    # Ensure host and port have valid values
    if host is None or host == 'None':
        host = '0.0.0.0'
    if port is None or port == 'None':
        port = 5001
    port = int(port)

    log_main('INFO', f'Starting video server on {host}:{port}', 'video')

    try:
        env = os.environ.copy()
        env['VIDEO_PORT'] = str(port)
        env['VIDEO_HOST'] = host

        # Create runner in /tmp but working directory is project root
        runner_content = f'''#!/usr/bin/env python3
import sys
import os

# Set working directory to project root
project_root = "{os.getcwd()}"
os.chdir(project_root)
sys.path.insert(0, project_root)

from video_server.app import run

if __name__ == '__main__':
    print("\\n🎥 Video Server is running!")
    print(f"🌐 Access at: http://{'localhost' if '{host}' == '0.0.0.0' else '{host}'}:{port}")
    print("📝 Press Ctrl+C to stop\\n")
    run()
'''

        # Write runner to /tmp
        runner_path = '/tmp/run_video_server.py'
        with open(runner_path, 'w') as f:
            f.write(runner_content)
        os.chmod(runner_path, 0o755)

        cmd = [sys.executable, runner_path]

        print(f"🎥 Starting Video Server on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")

        # Open log files for redirection
        video_log_fh.seek(0, 2)  # Seek to end
        kiselgram_log_fh.seek(0, 2)  # Seek to end

        video_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=video_log_fh,  # stdout -> kis_vid.log
            stderr=kiselgram_log_fh,  # stderr -> kiselgram.log
            universal_newlines=True,
            bufsize=1,
            cwd=os.getcwd()  # Working directory is project root
        )

        save_status(port, video_process.pid, 'video')
        log_main('INFO', f'Video server process started with PID {video_process.pid}', 'video')

        # Monitor process in background
        def monitor_video():
            video_process.wait()
            log_main('INFO', f'Video server process {video_process.pid} exited with code {video_process.returncode}',
                     'video')
            clear_status('video')

        monitor_thread = threading.Thread(target=monitor_video, daemon=True)
        monitor_thread.start()

        return True

    except Exception as e:
        print(f"❌ Error starting video server: {e}")
        log_main('ERROR', f'Error starting video server: {e}', 'video')
        return False


def stop_application(service='all'):
    """Stop the running application(s)"""
    global flask_process, video_process, is_running

    if service == 'all' or service == 'main':
        status = load_status('main')
        if status and status.get('running'):
            port = status.get('port', 5000)
            print(f"🛑 Stopping Kiselgram main app on port {port}...")

            # Try graceful shutdown via API first
            if stop_via_api(port, SHUTDOWN_TOKEN):
                print("✅ Sent graceful shutdown request via API")
                time.sleep(3)  # Give it time to shutdown
            else:
                print("⚠️ API shutdown failed, using process termination")
                kill_process_on_port(port)
        else:
            port = 5000
            print(f"🛑 Stopping Kiselgram main app (if running)...")
            kill_process_on_port(port)

        clear_status('main')

        # Kill any remaining processes
        if platform.system() != 'Windows':
            subprocess.run(['pkill', '-f', 'run_kiselgram.py'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

        print("✅ Main application stopped")

    if service == 'all' or service == 'video':
        video_status = load_status('video')
        if video_status and video_status.get('running'):
            port = video_status.get('port', 5001)
            print(f"🛑 Stopping Video Server on port {port}...")
        else:
            port = 5001
            print(f"🛑 Stopping Video Server (if running)...")

        kill_process_on_port(port)
        clear_status('video')

        if platform.system() != 'Windows':
            subprocess.run(['pkill', '-f', 'run_video_server.py'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'video_server'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

        print("✅ Video server stopped")

    # Clean up tmp files
    for tmp_file in ['/tmp/run_kiselgram.py', '/tmp/run_video_server.py']:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

    return True


def kill_process_on_port(port):
    """Kill process running on specific port"""
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        log_main('INFO', f'Killed process {pid} on port {port}', 'shutdown')
                        print(f"✓ Killed process {pid} on port {port}")
        else:
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'],
                                        capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split()
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            time.sleep(0.5)
                            # Check if still running
                            try:
                                os.kill(int(pid), 0)
                                os.kill(int(pid), signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            log_main('INFO', f'Killed process {pid} on port {port}', 'shutdown')
                            print(f"✓ Killed process {pid} on port {port}")
                        except ProcessLookupError:
                            pass
            except FileNotFoundError:
                subprocess.run(['fuser', '-k', f'{port}/tcp'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                print(f"✓ Sent kill signal to processes on port {port}")
    except Exception as e:
        print(f"⚠️  Error killing process on port {port}: {e}")
        log_main('ERROR', f'Error killing process on port {port}: {e}', 'shutdown')


def check_application(service='all'):
    """Check application status"""
    if service == 'all' or service == 'main':
        status = load_status('main')
        if status and status.get('running'):
            pid = status.get('pid')
            port = status.get('port', 5000)
            started = status.get('started_at', 'unknown')

            # Check if process is still alive
            try:
                os.kill(int(pid), 0)
                alive = True
            except (ProcessLookupError, OSError):
                alive = False

            print(f"\n📱 MAIN APPLICATION:")
            if alive:
                print(f"   Status: ✅ RUNNING")
            else:
                print(f"   Status: ⚠️ STALE (process dead)")
            print(f"   PID: {pid}")
            print(f"   Port: {port}")
            print(f"   Started: {started}")
            print(f"   URL: http://localhost:{port}")

            if check_port_available(port):
                print(f"   ⚠️  Warning: Port {port} appears to be free (process may have crashed)")
            else:
                print(f"   ✓ Port {port} is active")
        else:
            print(f"\n📱 MAIN APPLICATION: ❌ NOT RUNNING")

    if service == 'all' or service == 'video':
        video_status = load_status('video')
        if video_status and video_status.get('running'):
            pid = video_status.get('pid')
            port = video_status.get('port', 5001)
            started = video_status.get('started_at', 'unknown')

            # Check if process is still alive
            try:
                os.kill(int(pid), 0)
                alive = True
            except (ProcessLookupError, OSError):
                alive = False

            print(f"\n🎥 VIDEO SERVER:")
            if alive:
                print(f"   Status: ✅ RUNNING")
            else:
                print(f"   Status: ⚠️ STALE (process dead)")
            print(f"   PID: {pid}")
            print(f"   Port: {port}")
            print(f"   Started: {started}")
            print(f"   URL: http://localhost:{port}")

            if check_port_available(port):
                print(f"   ⚠️  Warning: Port {port} appears to be free (process may have crashed)")
            else:
                print(f"   ✓ Port {port} is active")
        else:
            print(f"\n🎥 VIDEO SERVER: ❌ NOT RUNNING")

    return True


def setup_environment():
    """Setup the Kiselgram environment"""
    print("\n🔧 Setting up Kiselgram environment...")

    directories = [
        'config',
        'logs',
        'status',
        'uploads/images',
        'uploads/documents',
        'uploads/media',
        'uploads/videos',
        'static/css',
        'static/js',
        'static/images',
        'static/videos',
        'templates',
        'video_server',
        'video_server/templates',
        'video_server/static'
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created: {directory}")

    config_paths = ['config/kis.toml', 'kis-1.toml']
    config_exists = any(os.path.exists(p) for p in config_paths)

    if not config_exists:
        create_default_config()

    if not os.path.exists('requirements.txt'):
        req_content = """Flask>=2.3.0
Flask-SQLAlchemy>=3.0.0
python-dotenv>=1.0.0
Pillow>=10.0.0
pyTelegramBotAPI>=4.12.0
opencv-python>=4.8.0
flask-socketio>=5.3.0
tomli>=2.0.0
requests>=2.28.0
psutil>=5.9.0
"""
        with open('requirements.txt', 'w') as f:
            f.write(req_content)
        print("✓ Created requirements.txt")
    else:
        print("✓ requirements.txt already exists")

    load_config()

    print("\n✅ Setup completed!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Configure config/kis.toml")
    print("3. Run: python manage.py start")

    return True


def show_help():
    """Show help information"""
    print_header()
    print("\n📚 Kiselgram Management Commands:")
    print("=" * 40)

    print("\n📱 Main Application Commands:")
    print("  python manage.py start [options]      Start main app + video server")
    print("  python manage.py stop                  Stop all services")
    print("  python manage.py restart [options]     Restart all services")
    print("  python manage.py status [--all]        Check service status")

    print("\n🎥 Video Server Options:")
    print("  --no-video              Disable video server auto-start")
    print("  --video-port PORT       Set video server port (default: 5001)")
    print("  --video-host HOST       Set video server host (default: 0.0.0.0)")

    print("\n📋 Standalone Video Commands:")
    print("  python manage.py video start           Start only video server")
    print("  python manage.py video stop            Stop only video server")
    print("  python manage.py video restart         Restart only video server")
    print("  python manage.py video status          Check only video server")

    print("\nAdvanced Options:")
    print("  --port PORT            Main app port (default: 5000)")
    print("  --host HOST            Main app host (default: 0.0.0.0)")
    print("  --debug                Enable debug mode")
    print("  --no-browser           Don't open browser automatically")

    print("\nUtility Commands:")
    print("  python manage.py setup                 Setup environment")
    print("  python manage.py clean                 Clean temporary files")
    print("  python manage.py reset-db              Reset database (⚠️ deletes data)")
    print("  python manage.py test                  Run basic tests")
    print("  python manage.py help                  Show this help")

    return True


def clean_temporary_files():
    """Clean temporary files"""
    print("\n🧹 Cleaning temporary files...")

    files_to_remove = [
        '/tmp/run_kiselgram.py',
        '/tmp/run_video_server.py',
        '.kiselgram.pid',
        'status/kiselgram.json',
        'status/kiselgram-video.json'
    ]

    for item in files_to_remove:
        if os.path.exists(item):
            try:
                os.remove(item)
                print(f"✓ Removed: {item}")
            except Exception as e:
                print(f"⚠️ Could not remove {item}: {e}")

    # Clean __pycache__ directories
    import shutil
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                print(f"✓ Removed: {pycache_path}")
            except:
                pass

    print("✅ Cleanup completed")
    return True


def reset_database():
    """Reset the database (WARNING: deletes all data)"""
    print("\n⚠️  WARNING: This will DELETE ALL DATA!")
    confirm = input("Are you sure? Type 'yes' to continue: ")

    if confirm.lower() != 'yes':
        print("❌ Database reset cancelled")
        return False

    print("\n🗑️  Resetting database...")

    stop_application('all')

    db_files = ['kiselgram.db', 'instance/kiselgram.db', 'test.db']

    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"✓ Removed: {db_file}")

    print("\n✅ Database reset complete")
    print("Next: Run 'python manage.py start' to recreate database")

    return True


def run_tests():
    """Run basic tests"""
    print("\n🧪 Running basic tests...")

    tests_passed = 0
    tests_failed = 0

    if sys.version_info >= (3, 7):
        print("✓ Python version OK")
        tests_passed += 1
    else:
        print("✗ Python version too old")
        tests_failed += 1

    if check_dependencies():
        print("✓ Dependencies OK")
        tests_passed += 1
    else:
        print("✗ Missing dependencies")
        tests_failed += 1

    required_dirs = ['app', 'video_server', 'templates', 'static', 'uploads', 'logs']
    all_exist = all(os.path.exists(d) for d in required_dirs)
    if all_exist:
        print("✓ Directory structure OK")
        tests_passed += 1
    else:
        print("✗ Missing directories")
        tests_failed += 1

    config_paths = ['config/kis.toml', 'kis-1.toml']
    if any(os.path.exists(p) for p in config_paths):
        print("✓ Config file exists")
        tests_passed += 1
    else:
        print("⚠️ No config file (run setup to create)")
        tests_passed += 1

    print(f"\n📊 Test Results: {tests_passed} passed, {tests_failed} failed")

    if tests_failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print("⚠️ Some tests failed. Run 'python manage.py setup' to fix issues.")
        return False


def video_command(args):
    """Handle video subcommands"""
    if args.video_command == 'start':
        print_header()
        print("\n🎥 Video Server Management")
        print("-" * 40)

        video_status = load_status('video')
        if video_status and video_status.get('running'):
            current_port = video_status.get('port', 5001)
            print(f"⚠️ Video server is already running on port {current_port}")
            choice = input("Stop and restart? (y/n): ")
            if choice.lower() == 'y':
                stop_application('video')
                time.sleep(2)
            else:
                return

        port = args.port if hasattr(args, 'port') and args.port else 5001
        host = args.host if hasattr(args, 'host') and args.host else '0.0.0.0'

        if not check_port_available(port):
            print(f"❌ Port {port} is already in use!")
            return

        print(f"🚀 Starting video server...")
        print(f"   Port: {port}")
        print(f"   Host: {host}")
        print("-" * 40)

        video_thread = threading.Thread(
            target=run_video_server_process,
            args=(port, host),
            daemon=True
        )
        video_thread.start()

        time.sleep(3)

        if check_port_available(port):
            print("\n⚠️ Video server may not have started properly. Check logs/video.log")
        else:
            print("\n✅ Video server started!")
            print(f"🌐 Access at: http://localhost:{port}")
            print("🛑 To stop: python manage.py video stop")

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Management script stopped. Video server continues running.")

    elif args.video_command == 'stop':
        print_header()
        print("\n🎥 Stopping Video Server...")
        stop_application('video')

    elif args.video_command == 'restart':
        print_header()
        print("\n🎥 Restarting Video Server...")

        stop_application('video')
        time.sleep(2)

        port = args.port if hasattr(args, 'port') and args.port else 5001
        host = args.host if hasattr(args, 'host') and args.host else '0.0.0.0'

        if not check_port_available(port):
            print(f"❌ Port {port} is still in use!")
            return

        print(f"\n🚀 Starting video server...")
        video_thread = threading.Thread(
            target=run_video_server_process,
            args=(port, host),
            daemon=True
        )
        video_thread.start()

        time.sleep(3)
        if check_port_available(port):
            print("\n⚠️ Video server may not have started properly.")
        else:
            print("\n✅ Video server restarted successfully!")

    elif args.video_command == 'status':
        print_header()
        print("\n🎥 Video Server Status")
        print("-" * 40)
        check_application('video')


def start_all_services(args):
    """Start main app and optionally video server"""
    print_header()

    config = load_config()

    # Get main app settings
    if hasattr(args, 'port') and args.port is not None:
        main_port = args.port
    else:
        main_port = config.get('app', {}).get('port', 5000)

    if hasattr(args, 'host') and args.host is not None:
        main_host = args.host
    else:
        main_host = config.get('app', {}).get('host', '0.0.0.0')

    if hasattr(args, 'debug') and args.debug is not None:
        debug = args.debug
    else:
        debug = config.get('app', {}).get('debug', True)

    # Get video settings
    if hasattr(args, 'no_video'):
        video_enabled = not args.no_video
    else:
        video_enabled = config.get('video', {}).get('enabled', True)

    if hasattr(args, 'video_port') and args.video_port is not None:
        video_port = args.video_port
    else:
        video_port = config.get('video', {}).get('port', 5001)

    if hasattr(args, 'video_host') and args.video_host is not None:
        video_host = args.video_host
    else:
        video_host = config.get('video', {}).get('host', '0.0.0.0')

    no_browser = hasattr(args, 'no_browser') and args.no_browser

    if not check_dependencies():
        print("\n❌ Missing dependencies. Install with: pip install -r requirements.txt")
        return False

    if not check_port_available(main_port):
        print(f"\n❌ Port {main_port} is already in use!")
        choice = input(f"Try another port? (y/n): ")
        if choice.lower() == 'y':
            new_port = int(input("Enter port number: "))
            main_port = new_port
            if not check_port_available(main_port):
                print(f"❌ Port {main_port} is also in use.")
                return False
        else:
            return False

    main_status = load_status('main')
    if main_status and main_status.get('running'):
        print(f"\n⚠️  Main application is already running on port {main_status.get('port')}")
        choice = input("Stop and restart? (y/n): ")
        if choice.lower() == 'y':
            stop_application('main')
            time.sleep(2)
        else:
            return False

    if video_enabled:
        if not check_port_available(video_port):
            print(f"\n❌ Video server port {video_port} is already in use!")
            print("Use --video-port to specify a different port or --no-video to disable")
            return False

        video_status = load_status('video')
        if video_status and video_status.get('running'):
            current_port = video_status.get('port', video_port)
            print(f"\n⚠️  Video server is already running on port {current_port}")
            choice = input("Stop and restart? (y/n): ")
            if choice.lower() == 'y':
                stop_application('video')
                time.sleep(2)
            else:
                video_enabled = False

    main_url = f"http://{main_host if main_host != '0.0.0.0' else 'localhost'}:{main_port}"
    video_url = f"http://{video_host if video_host != '0.0.0.0' else 'localhost'}:{video_port}" if video_enabled else "DISABLED"

    print(f"\n🚀 Starting Kiselgram services...")
    print(f"   Main App: {main_url}")
    print(f"   Video Server: {video_url}")
    print(f"   Debug: {debug}")
    print(f"   Open Browser: {not no_browser}")
    print(f"   Logs:")
    print(f"     - Main: logs/kis_main.log")
    print(f"     - Video: logs/kis_vid.log")
    print(f"     - Combined: logs/kiselgram.log")
    print("-" * 40)

    # Open log files for the session
    global main_log_fh, video_log_fh, kiselgram_log_fh

    flask_thread = threading.Thread(
        target=run_flask_app,
        args=(main_host, main_port, debug, no_browser),
        daemon=True
    )
    flask_thread.start()

    if video_enabled:
        time.sleep(1)
        video_thread = threading.Thread(
            target=run_video_server_process,
            args=(video_port, video_host),
            daemon=True
        )
        video_thread.start()

    time.sleep(3)

    main_started = not check_port_available(main_port)
    video_started = not check_port_available(video_port) if video_enabled else False

    print("\n" + "=" * 40)
    if main_started:
        print("✅ Main application started successfully!")
        print(f"🌐 Main App: http://localhost:{main_port}")
        print(f"🔑 Shutdown token: {SHUTDOWN_TOKEN}")
    else:
        print("⚠️  Main application may not have started properly. Check logs above.")

    if video_enabled:
        if video_started:
            print("✅ Video server started successfully!")
            print(f"🎥 Video Server: http://localhost:{video_port}")
        else:
            print("⚠️  Video server may not have started properly. Check logs above.")

    print("\n🛑 To stop all services: python manage.py stop")
    print("   To stop only video: python manage.py video stop")
    print("   Graceful shutdown: POST to /api/utils/test/env/shutdown with token")
    print("Press Ctrl+C to exit this script (services will continue running)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Management script stopped. Services continue running.")
        print(f"   Use 'python manage.py stop' to stop services")

    return True


def main():
    """Main entry point"""
    setup_logging()

    parser = argparse.ArgumentParser(description='Kiselgram Management Script')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    start_parser = subparsers.add_parser('start', help='Start main app + video server')
    start_parser.add_argument('--port', type=int, default=None, help='Main app port')
    start_parser.add_argument('--host', default=None, help='Host to bind to')
    start_parser.add_argument('--debug', action='store_true', default=None, help='Enable debug mode')
    start_parser.add_argument('--no-debug', action='store_false', dest='debug', help='Disable debug mode')
    start_parser.add_argument('--no-browser', action='store_true', help="Don't open browser automatically")
    start_parser.add_argument('--no-video', action='store_true', help='Disable video server auto-start')
    start_parser.add_argument('--video-port', type=int, default=None, help='Video server port')
    start_parser.add_argument('--video-host', default=None, help='Video server host')

    subparsers.add_parser('stop', help='Stop all services')

    restart_parser = subparsers.add_parser('restart', help='Restart all services')
    restart_parser.add_argument('--port', type=int, default=None, help='Main app port')
    restart_parser.add_argument('--host', default=None, help='Host to bind to')
    restart_parser.add_argument('--debug', action='store_true', default=None, help='Enable debug mode')
    restart_parser.add_argument('--no-debug', action='store_false', dest='debug', help='Disable debug mode')
    restart_parser.add_argument('--no-browser', action='store_true', help="Don't open browser automatically")
    restart_parser.add_argument('--no-video', action='store_true', help='Disable video server auto-start')
    restart_parser.add_argument('--video-port', type=int, default=None, help='Video server port')

    status_parser = subparsers.add_parser('status', help='Check service status')
    status_parser.add_argument('--all', action='store_true', help='Check all services')

    video_parser = subparsers.add_parser('video', help='Video server commands')
    video_subparsers = video_parser.add_subparsers(dest='video_command', help='Video command')

    video_start_parser = video_subparsers.add_parser('start', help='Start video server')
    video_start_parser.add_argument('--port', type=int, default=5001, help='Port to run on')
    video_start_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')

    video_subparsers.add_parser('stop', help='Stop video server')

    video_restart_parser = video_subparsers.add_parser('restart', help='Restart video server')
    video_restart_parser.add_argument('--port', type=int, default=5001, help='Port to run on')
    video_restart_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')

    video_subparsers.add_parser('status', help='Check video server status')

    subparsers.add_parser('setup', help='Setup environment')
    subparsers.add_parser('clean', help='Clean temporary files')
    subparsers.add_parser('reset-db', help='Reset database')
    subparsers.add_parser('test', help='Run basic tests')
    subparsers.add_parser('help', help='Show help')

    args = parser.parse_args()

    if not args.command:
        print_header()
        print("\n❌ No command specified. Use 'python manage.py help' for usage.")
        return

    if args.command == 'video':
        if not hasattr(args, 'video_command') or not args.video_command:
            print_header()
            print("\n❌ No video command specified.")
            print("\nAvailable video commands:")
            print("  python manage.py video start   - Start video server")
            print("  python manage.py video stop    - Stop video server")
            print("  python manage.py video restart - Restart video server")
            print("  python manage.py video status  - Check video server status")
            return
        video_command(args)
        return

    if args.command == 'start':
        start_all_services(args)
    elif args.command == 'stop':
        print_header()
        print("\n🛑 Stopping all services...")
        stop_application('all')
    elif args.command == 'restart':
        print_header()
        print("\n🔄 Restarting all services...")
        stop_application('all')
        time.sleep(3)
        start_all_services(args)
    elif args.command == 'status':
        print_header()
        if hasattr(args, 'all') and args.all:
            check_application('all')
        else:
            check_application('main')
            video_status = load_status('video')
            if video_status and video_status.get('running'):
                print("\n🎥 Video server is also running (use --all to see details)")
            else:
                print("\n🎥 Video server is not running")
    elif args.command == 'setup':
        print_header()
        setup_environment()
    elif args.command == 'clean':
        print_header()
        clean_temporary_files()
    elif args.command == 'reset-db':
        print_header()
        reset_database()
    elif args.command == 'test':
        print_header()
        run_tests()
    elif args.command == 'help':
        show_help()
    else:
        print(f"❌ Unknown command: {args.command}")
        show_help()


def cleanup():
    """Cleanup function called on exit"""
    global kiselgram_log_fh, video_log_fh, main_log_fh

    # Close log file handles
    for fh in [kiselgram_log_fh, video_log_fh, main_log_fh]:
        if fh:
            try:
                fh.close()
            except:
                pass

    # Clean up tmp files
    for tmp_file in ['/tmp/run_kiselgram.py', '/tmp/run_video_server.py']:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass


atexit.register(cleanup)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        log_main('ERROR', f'Fatal error: {e}', 'main')
        sys.exit(1)