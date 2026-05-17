#!/Users/dkisel/PycharmProjects/kiselgram-dev/.venv/bin/python
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

# Global variables
flask_process = None
video_process = None
is_running = False
STATUS_FILE = 'status/kiselgram.json'
VIDEO_STATUS_FILE = 'status/kiselgram-video.json'
TOKEN_FILE = '.kiselgram_token'

# Logger instances
kiselgram_logger = None
video_logger = None
main_logger = None
kiselgram_log_fh = None
video_log_fh = None
main_log_fh = None


def setup_logging(config=None):
    """Setup logging configuration"""
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
    kiselgram_handler.setFormatter(formatter)
    kiselgram_logger.addHandler(kiselgram_handler)
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
    video_handler.setFormatter(formatter)
    video_logger.addHandler(video_handler)
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
    main_handler.setFormatter(formatter)
    main_logger.addHandler(main_handler)
    main_log_fh = open(f"logs/{log_settings['main']['file']}", 'a', encoding='utf-8')

    return True


def log_main(level, message, domain='general'):
    if main_logger:
        getattr(main_logger, level.lower())(f"{domain} - {message}")


def get_shutdown_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    else:
        token = secrets.token_urlsafe(32)
        with open(TOKEN_FILE, 'w') as f:
            f.write(token)
        try:
            os.chmod(TOKEN_FILE, 0o600)
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
    default_config = '''# Kiselgram Configuration File

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
        f.write(default_config)
    print("✅ Created default kis.toml configuration file")
    setup_logging()
    return {'app': {'port': 5000, 'host': '0.0.0.0', 'debug': True},
            'video': {'port': 5001, 'host': '0.0.0.0', 'enabled': True}}


def print_header():
    """Print fancy header"""
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


def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n📦 Checking dependencies...")
    required = ['flask', 'flask_sqlalchemy', 'dotenv', 'PIL']
    all_installed = True

    for dep in required:
        try:
            __import__(dep.replace('-', '_'))
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} - Install with: pip install {dep}")
            all_installed = False

    return all_installed


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
    status_file = VIDEO_STATUS_FILE if service == 'video' else STATUS_FILE
    Path(status_file).parent.mkdir(parents=True, exist_ok=True)
    status = {'running': True, 'port': port, 'pid': pid, 'service': service, 'started_at': datetime.now().isoformat()}
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
    """Kill process running on specific port"""
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                        print(f"✓ Killed process {pid} on port {port}")
        else:
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                if result.stdout.strip():
                    for pid in result.stdout.strip().split():
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            time.sleep(0.5)
                            try:
                                os.kill(int(pid), 0)
                                os.kill(int(pid), signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            print(f"✓ Killed process {pid} on port {port}")
                        except:
                            pass
            except FileNotFoundError:
                subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)
                print(f"✓ Sent kill signal to processes on port {port}")
    except Exception as e:
        print(f"⚠️ Error killing process on port {port}: {e}")


def stop_application(service='all'):
    """Stop running applications"""
    if service == 'all' or service == 'main':
        status = load_status('main')
        if status:
            port = status.get('port', 5000)
            print(f"🛑 Stopping main app on port {port}...")
            kill_process_on_port(port)
        clear_status('main')
        subprocess.run(['pkill', '-f', 'run_kiselgram.py'], capture_output=True)
        print("✅ Main application stopped")

    if service == 'all' or service == 'video':
        video_status = load_status('video')
        if video_status:
            port = video_status.get('port', 5001)
            print(f"🛑 Stopping video server on port {port}...")
            kill_process_on_port(port)
        clear_status('video')
        subprocess.run(['pkill', '-f', 'run_video_server.py'], capture_output=True)
        print("✅ Video server stopped")

    # Cleanup tmp files
    for tmp_file in ['/tmp/run_kiselgram.py', '/tmp/run_video_server.py']:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

    return True


def run_flask_app(host, port, debug, no_browser=False):
    """Run Flask application"""
    global flask_process, is_running

    if host is None or host == 'None':
        host = '0.0.0.0'
    if port is None or port == 'None':
        port = 5000
    port = int(port)

    try:
        env = os.environ.copy()
        env['FLASK_ENV'] = 'development' if debug else 'production'
        env['KISELGRAM_TOKEN'] = SHUTDOWN_TOKEN

        # Create runner script
        runner_content = f'''#!/usr/bin/env python3
import sys
import os

project_root = "{os.getcwd()}"
os.chdir(project_root)
sys.path.insert(0, project_root)

from app import create_app, db
from app.utils.bot_utils import setup_bots
import threading

app = create_app()

def init_database():
    with app.app_context():
        db.create_all()
        setup_bots()
        print("✓ Database initialized")

if __name__ == '__main__':
    init_database()
    print("\\n🚀 Kiselgram is running!")
    print(f"🌐 Access at: http://'localhost' if '{host}' == '0.0.0.0' else '{host}':{port}")
    print("📝 Press Ctrl+C to stop\\n")
    app.run(host='{host}', port={port}, debug={debug})
'''

        runner_path = '/tmp/run_kiselgram.py'
        with open(runner_path, 'w') as f:
            f.write(runner_content)
        os.chmod(runner_path, 0o755)

        cmd = [sys.executable, runner_path]

        print(f"🚀 Starting Flask on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        print(f"🔑 Shutdown token: {SHUTDOWN_TOKEN}")

        flask_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=main_log_fh,
            stderr=kiselgram_log_fh,
            universal_newlines=True,
            bufsize=1,
            cwd=os.getcwd()
        )

        is_running = True
        save_status(port, flask_process.pid, 'main')

        # Open browser if requested
        if not no_browser:
            def open_browser():
                time.sleep(2)
                try:
                    webbrowser.open(f"http://localhost:{port}")
                except:
                    pass

            threading.Thread(target=open_browser, daemon=True).start()

        return True

    except Exception as e:
        print(f"❌ Error starting Flask: {e}")
        log_main('ERROR', f'Error starting Flask: {e}', 'flask')
        return False


def run_video_server_process(port=5001, host='0.0.0.0'):
    """Run video server"""
    global video_process

    if host is None or host == 'None':
        host = '0.0.0.0'
    if port is None or port == 'None':
        port = 5001
    port = int(port)

    try:
        env = os.environ.copy()
        env['VIDEO_PORT'] = str(port)
        env['VIDEO_HOST'] = host

        runner_content = f'''#!/usr/bin/env python3
import sys
import os

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
        print("📝 Press Ctrl+C to stop\\n")
        socketio.run(video_app, host='{host}', port={port}, debug=False)
except ImportError:
    print("❌ Video server not found. Make sure video_server/ directory exists.")
'''

        runner_path = '/tmp/run_video_server.py'
        with open(runner_path, 'w') as f:
            f.write(runner_content)
        os.chmod(runner_path, 0o755)

        cmd = [sys.executable, runner_path]

        print(f"🎥 Starting Video Server on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")

        video_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=video_log_fh,
            stderr=kiselgram_log_fh,
            universal_newlines=True,
            bufsize=1,
            cwd=os.getcwd()
        )

        save_status(port, video_process.pid, 'video')
        return True

    except Exception as e:
        print(f"❌ Error starting video server: {e}")
        return False


def start_all_services(args):
    """Start main app and video server"""
    print_header()

    config = load_config()

    # Get settings
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
        print(f"\n❌ Port {main_port} is already in use!")
        return False

    # Stop existing services
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

    # Start Flask
    flask_thread = threading.Thread(target=run_flask_app, args=(main_host, main_port, debug, no_browser), daemon=True)
    flask_thread.start()

    # Start video server if enabled
    if not no_video:
        time.sleep(2)
        video_thread = threading.Thread(target=run_video_server_process, args=(video_port, video_host), daemon=True)
        video_thread.start()

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
        print(f"   Use 'python manage.py stop' to stop services")

    return True


def main():
    """Main entry point"""
    setup_logging()

    parser = argparse.ArgumentParser(description='Kiselgram Management Script')
    subparsers = parser.add_subparsers(dest='command', help='Command')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start services')
    start_parser.add_argument('--port', type=int, help='Main app port')
    start_parser.add_argument('--host', help='Host to bind to')
    start_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    start_parser.add_argument('--no-debug', action='store_false', dest='debug', help='Disable debug mode')
    start_parser.add_argument('--no-browser', action='store_true', help="Don't open browser")
    start_parser.add_argument('--no-video', action='store_true', help='Disable video server')
    start_parser.add_argument('--video-port', type=int, help='Video server port')
    start_parser.add_argument('--video-host', help='Video server host')

    # Stop command
    subparsers.add_parser('stop', help='Stop services')

    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart services')
    restart_parser.add_argument('--port', type=int, help='Main app port')
    restart_parser.add_argument('--host', help='Host to bind to')
    restart_parser.add_argument('--no-video', action='store_true', help='Disable video server')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check status')
    status_parser.add_argument('--all', action='store_true', help='Check all services')

    # Setup command
    subparsers.add_parser('setup', help='Setup environment')

    # Clean command
    subparsers.add_parser('clean', help='Clean temporary files')

    # Reset-db command
    subparsers.add_parser('reset-db', help='Reset database')

    # Test command
    subparsers.add_parser('test', help='Run tests')

    # Help command
    subparsers.add_parser('help', help='Show help')

    args = parser.parse_args()

    if not args.command:
        print_header()
        print("\n❌ No command specified. Use 'python manage.py help' for usage.")
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
        time.sleep(2)
        start_all_services(args)
    elif args.command == 'status':
        print_header()
        print("\n📊 Service Status")
        print("-" * 40)
        main_status = load_status('main')
        video_status = load_status('video')

        if main_status:
            print(f"Main App: ✅ RUNNING on port {main_status.get('port')}")
        else:
            print("Main App: ❌ NOT RUNNING")

        if video_status:
            print(f"Video Server: ✅ RUNNING on port {video_status.get('port')}")
        else:
            print("Video Server: ❌ NOT RUNNING")
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
        print("✅ Cleanup completed")
    elif args.command == 'reset-db':
        print_header()
        confirm = input("\n⚠️ This will DELETE ALL DATA! Type 'yes' to continue: ")
        if confirm.lower() == 'yes':
            for db_file in ['kiselgram.db', 'instance/kiselgram.db']:
                if os.path.exists(db_file):
                    os.remove(db_file)
                    print(f"✓ Removed {db_file}")
            print("✅ Database reset complete")
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
    """Cleanup on exit"""
    global kiselgram_log_fh, video_log_fh, main_log_fh
    for fh in [kiselgram_log_fh, video_log_fh, main_log_fh]:
        if fh:
            try:
                fh.close()
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
        sys.exit(1)