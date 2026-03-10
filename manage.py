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
from pathlib import Path
from datetime import datetime
from video_server.app import run as run_video_server

# Global variables for managing processes
flask_process = None
video_process = None
is_running = False
process_pid = None
STATUS_FILE = '.kiselgram_status.json'
VIDEO_STATUS_FILE = '.kiselgram_video_status.json'


def print_header():
    """Print fancy header for Kiselgram"""
    print("\n" + "=" * 60)
    print("""
  _  __ ___ _____ _____ ____ ____ ___  ____  __  __ 
 | |/ // _ \\_   _| ____/ ___/ ___/ _ \\|  _ \\|  \\/  |
 | ' /| | | || | |  _| \\___ \\___ \\ | | | |_) | |\\/| |
 | . \\| |_| || | | |___ ___) |__) | |_| |  _ <| |  | |
 |_|\\_\\\\___/ |_| |_____|____/____/ \\___/|_| \\_\\_|  |_|
    """)
    print("=" * 60)
    print("📱 Complete Messaging Platform v2.0")
    print("👥 Groups | 📢 Channels | 📁 File Support | 🤖 Bots | 🎥 Video Server (Auto-start)")
    print("=" * 60)


def check_python_version():
    """Check if Python version is compatible"""
    print("🔍 Checking Python version...")
    if sys.version_info < (3, 7):
        print(f"❌ Python 3.7+ required. Current: {platform.python_version()}")
        return False
    print(f"✅ Python {platform.python_version()}")
    return True


def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n📦 Checking dependencies...")

    required = [
        'flask',
        'flask_sqlalchemy',
        'dotenv',
        'PIL'
    ]

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


def run_flask_app(host, port, debug, no_browser=False):
    """Run Flask application in a subprocess"""
    global flask_process, process_pid, is_running

    try:
        # Set environment variables
        env = os.environ.copy()
        env['FLASK_ENV'] = 'development' if debug else 'production'

        # Build command based on what files exist
        if os.path.exists('run_modular.py'):
            cmd = [sys.executable, 'run_modular.py']
        elif os.path.exists('app'):
            # Create a temporary runner for modular app
            runner_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    app.run(host='{host}', port={port}, debug={debug})
'''

            with open('tmp_runner.py', 'w') as f:
                f.write(runner_content)
            cmd = [sys.executable, 'tmp_runner.py']
        else:
            print("❌ No Flask application found!")
            return False

        # Start Flask process
        print(f"🚀 Starting Flask on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        flask_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        process_pid = flask_process.pid
        is_running = True
        save_status(port, process_pid, 'main')

        # Monitor output in a separate thread
        def monitor_output():
            for line in flask_process.stdout:
                line = line.rstrip()
                if line:  # Skip empty lines
                    print(f"[App] {line}")
                    # Only open browser if --no-browser is False
                    if not no_browser and "Running on" in line and "http://" in line:
                        # Try to open browser
                        try:
                            time.sleep(2)
                            url = f"http://localhost:{port}"
                            webbrowser.open(url)
                            print(f"\n🌐 Opened browser at: {url}")
                        except:
                            pass

        monitor_thread = threading.Thread(target=monitor_output, daemon=True)
        monitor_thread.start()

        # Wait for process to complete
        flask_process.wait()
        is_running = False
        clear_status('main')

        return True

    except Exception as e:
        print(f"❌ Error starting Flask: {e}")
        return False


def run_video_server_process(port=5001, host='0.0.0.0'):
    """Run video server in a subprocess"""
    global video_process

    try:
        # Create a temporary runner for video server
        runner_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_server.app import run

if __name__ == '__main__':
    # Override default port if needed
    os.environ['VIDEO_PORT'] = '{port}'
    os.environ['VIDEO_HOST'] = '{host}'
    run()
'''

        with open('tmp_video_runner.py', 'w') as f:
            f.write(runner_content)

        cmd = [sys.executable, 'tmp_video_runner.py']

        # Start video server process
        print(f"🎥 Starting Video Server on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        video_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        save_status(port, video_process.pid, 'video')

        # Monitor output in a separate thread
        def monitor_video_output():
            for line in video_process.stdout:
                line = line.rstrip()
                if line:  # Skip empty lines
                    print(f"[Video] {line}")

        monitor_thread = threading.Thread(target=monitor_video_output, daemon=True)
        monitor_thread.start()

        return True

    except Exception as e:
        print(f"❌ Error starting video server: {e}")
        return False


def stop_application(service='all'):
    """Stop the running application(s)"""
    global flask_process, video_process, is_running

    if service == 'all' or service == 'main':
        status = load_status('main')
        if status and status.get('running'):
            port = status.get('port', 5000)
            print(f"🛑 Stopping Kiselgram main app on port {port}...")
        else:
            port = 5000
            print(f"🛑 Stopping Kiselgram main app (if running)...")

        kill_process_on_port(port)
        clear_status('main')

        # Kill any Python processes running our app
        if platform.system() != 'Windows':
            subprocess.run(['pkill', '-f', 'run_modular.py'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'tmp_runner.py'],
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

        # Kill video server processes
        if platform.system() != 'Windows':
            subprocess.run(['pkill', '-f', 'tmp_video_runner.py'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'video_server'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

        print("✅ Video server stopped")

    # Clean up temporary files
    for tmp_file in ['tmp_runner.py', 'tmp_video_runner.py', 'init_db.py', '.kiselgram.pid']:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
            print(f"✓ Removed {tmp_file}")

    return True


def kill_process_on_port(port):
    """Kill process running on specific port"""
    try:
        if platform.system() == 'Windows':
            # Find PID using port on Windows
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        print(f"✓ Killed process {pid} on port {port}")
        else:
            # Unix/Linux/Mac - find and kill process on port
            import signal
            # Try lsof first
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'],
                                        capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split()
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            time.sleep(0.5)
                            os.kill(int(pid), signal.SIGKILL)
                            print(f"✓ Killed process {pid} on port {port}")
                        except ProcessLookupError:
                            pass  # Process already dead
            except FileNotFoundError:
                # lsof not available, use pkill
                subprocess.run(['pkill', '-f', f'port.*{port}'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                print(f"✓ Sent kill signal to processes on port {port}")
    except Exception as e:
        print(f"⚠️  Error killing process on port {port}: {e}")


def check_application(service='all'):
    """Check application status"""
    if service == 'all' or service == 'main':
        status = load_status('main')
        if status and status.get('running'):
            pid = status.get('pid')
            port = status.get('port', 5000)
            started = status.get('started_at', 'unknown')

            print(f"\n📱 MAIN APPLICATION:")
            print(f"   Status: ✅ RUNNING")
            print(f"   PID: {pid}")
            print(f"   Port: {port}")
            print(f"   Started: {started}")
            print(f"   URL: http://localhost:{port}")

            # Check if port is actually responding
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

            print(f"\n🎥 VIDEO SERVER:")
            print(f"   Status: ✅ RUNNING")
            print(f"   PID: {pid}")
            print(f"   Port: {port}")
            print(f"   Started: {started}")
            print(f"   URL: http://localhost:{port}")

            # Check if port is actually responding
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

    # Create necessary directories
    directories = [
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

    # Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        env_content = """# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Flask Configuration
SECRET_KEY=your-secret-key-change-in-production
DATABASE_URL=sqlite:///kiselgram.db

# Server Configuration
HOST=0.0.0.0
PORT=5000
DEBUG=True

# Video Server Configuration
VIDEO_PORT=5001
VIDEO_HOST=0.0.0.0
VIDEO_QUALITY=medium
MAX_VIDEO_SIZE=104857600  # 100MB
VIDEO_AUTO_START=True     # Auto-start video server with main app

# File Uploads
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB
"""
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✓ Created .env file")
    else:
        print("✓ .env file already exists")

    # Create requirements.txt if it doesn't exist
    if not os.path.exists('requirements.txt'):
        req_content = """Flask>=2.3.0
Flask-SQLAlchemy>=3.0.0
python-dotenv>=1.0.0
Pillow>=10.0.0
pyTelegramBotAPI>=4.12.0
opencv-python>=4.8.0  # For video processing
flask-socketio>=5.3.0  # For real-time video
"""
        with open('requirements.txt', 'w') as f:
            f.write(req_content)
        print("✓ Created requirements.txt")
    else:
        print("✓ requirements.txt already exists")

    print("\n✅ Setup completed!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Configure Telegram bot in .env (optional)")
    print("3. Run: python manage.py start  (video server starts automatically)")
    print("   Use --no-video to disable video server auto-start")

    return True


def show_help():
    """Show help information"""
    print_header()
    print("\n📚 Kiselgram Management Commands:")
    print("=" * 40)

    print("\n📱 Main Application Commands (Video Server Auto-starts):")
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
    print("  python manage.py clean                  Clean temporary files")
    print("  python manage.py reset-db               Reset database (⚠️ deletes data)")
    print("  python manage.py test                   Run basic tests")

    print("\nExamples:")
    print("  # Start everything (video auto-starts)")
    print("  python manage.py start")
    print("")
    print("  # Start without video server")
    print("  python manage.py start --no-video")
    print("")
    print("  # Start with custom video port")
    print("  python manage.py start --video-port 8080")
    print("")
    print("  # Start both services on different ports")
    print("  python manage.py start --port 3000 --video-port 3001")
    print("")
    print("  # Start without opening browser")
    print("  python manage.py start --no-browser")

    return True


def clean_temporary_files():
    """Clean temporary files"""
    print("\n🧹 Cleaning temporary files...")

    files_to_remove = [
        'tmp_runner.py',
        'tmp_video_runner.py',
        'init_db.py',
        '.kiselgram.pid',
        '.kiselgram_status.json',
        '.kiselgram_video_status.json'
    ]

    for item in files_to_remove:
        if os.path.exists(item):
            if os.path.isdir(item):
                import shutil
                shutil.rmtree(item)
                print(f"✓ Removed directory: {item}")
            else:
                os.remove(item)
                print(f"✓ Removed file: {item}")

    # Clean __pycache__ directories
    import shutil
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            shutil.rmtree(pycache_path)
            print(f"✓ Removed: {pycache_path}")

    # Clean .pyc files
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                filepath = os.path.join(root, file)
                os.remove(filepath)
                print(f"✓ Removed: {filepath}")

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

    # Stop application if running
    stop_application('all')

    # Remove database files
    db_files = [
        'kiselgram.db',
        'instance/kiselgram.db',
        'test.db'
    ]

    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"✓ Removed: {db_file}")

    # Remove uploads
    if os.path.exists('uploads'):
        import shutil
        shutil.rmtree('uploads')
        os.makedirs('uploads/images', exist_ok=True)
        os.makedirs('uploads/documents', exist_ok=True)
        os.makedirs('uploads/media', exist_ok=True)
        os.makedirs('uploads/videos', exist_ok=True)
        print("✓ Cleared uploads directory")

    print("\n✅ Database reset complete")
    print("Next: Run 'python manage.py start' to recreate database")

    return True


def run_tests():
    """Run basic tests"""
    print("\n🧪 Running basic tests...")

    tests_passed = 0
    tests_failed = 0

    # Test 1: Check Python version
    try:
        if sys.version_info >= (3, 7):
            print("✓ Python version OK")
            tests_passed += 1
        else:
            print("✗ Python version too old")
            tests_failed += 1
    except:
        tests_failed += 1

    # Test 2: Check dependencies
    try:
        if check_dependencies():
            print("✓ Dependencies OK")
            tests_passed += 1
        else:
            print("✗ Missing dependencies")
            tests_failed += 1
    except:
        tests_failed += 1

    # Test 3: Check directory structure
    try:
        required_dirs = ['app', 'video_server', 'templates', 'static', 'uploads']
        all_exist = all(os.path.exists(d) for d in required_dirs)
        if all_exist:
            print("✓ Directory structure OK")
            tests_passed += 1
        else:
            print("✗ Missing directories")
            tests_failed += 1
    except:
        tests_failed += 1

    # Test 4: Check database
    try:
        if os.path.exists('kiselgram.db') or os.path.exists('instance/kiselgram.db'):
            print("✓ Database file exists")
            tests_passed += 1
        else:
            print("⚠️ No database file (this is OK for first run)")
            tests_passed += 1
    except:
        tests_failed += 1

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

        # Check if already running
        video_status = load_status('video')
        if video_status and video_status.get('running'):
            print(f"⚠️ Video server is already running on port {video_status.get('port')}")
            choice = input("Stop and restart? (y/n): ")
            if choice.lower() == 'y':
                stop_application('video')
                time.sleep(2)
            else:
                return

        # Check port
        port = args.port if hasattr(args, 'port') and args.port else 5001
        if not check_port_available(port):
            print(f"❌ Port {port} is already in use!")
            return

        print(f"🚀 Starting video server...")
        print(f"   Port: {port}")
        print(f"   Host: {args.host if hasattr(args, 'host') else '0.0.0.0'}")
        print("-" * 40)

        # Start video server in a separate thread
        video_thread = threading.Thread(
            target=run_video_server_process,
            args=(port, args.host if hasattr(args, 'host') else '0.0.0.0'),
            daemon=True
        )
        video_thread.start()

        # Wait a bit and check if started
        time.sleep(3)

        if check_port_available(port):
            print("\n⚠️ Video server may not have started properly. Check logs above.")
        else:
            print("\n✅ Video server started!")
            print(f"🌐 Access at: http://localhost:{port}")
            print("🛑 To stop: python manage.py video stop")

            try:
                # Keep script alive
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

        # Stop if running
        stop_application('video')
        time.sleep(2)

        # Start again
        port = args.port if hasattr(args, 'port') and args.port else 5001
        if not check_port_available(port):
            print(f"❌ Port {port} is still in use!")
            return

        print(f"\n🚀 Starting video server...")
        video_thread = threading.Thread(
            target=run_video_server_process,
            args=(port, args.host if hasattr(args, 'host') else '0.0.0.0'),
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

    # Check dependencies
    if not check_dependencies():
        print("\n❌ Missing dependencies. Install with: pip install -r requirements.txt")
        return False

    # Check main app port
    if not check_port_available(args.port):
        print(f"\n❌ Port {args.port} is already in use!")
        choice = input(f"Try another port? (y/n): ")
        if choice.lower() == 'y':
            new_port = int(input("Enter port number: "))
            args.port = new_port
            if not check_port_available(args.port):
                print(f"❌ Port {args.port} is also in use.")
                return False
        else:
            return False

    # Check if main app already running
    main_status = load_status('main')
    if main_status and main_status.get('running'):
        print(f"\n⚠️  Main application is already running on port {main_status.get('port')}")
        choice = input("Stop and restart? (y/n): ")
        if choice.lower() == 'y':
            stop_application('main')
            time.sleep(2)
        else:
            return False

    # Check video port if video is enabled
    video_enabled = not args.no_video
    video_port = args.video_port if hasattr(args, 'video_port') else 5001

    if video_enabled:
        if not check_port_available(video_port):
            print(f"\n❌ Video server port {video_port} is already in use!")
            print("Use --video-port to specify a different port or --no-video to disable")
            return False

        # Check if video server already running
        video_status = load_status('video')
        if video_status and video_status.get('running'):
            print(f"\n⚠️  Video server is already running on port {video_status.get('port')}")
            choice = input("Stop and restart? (y/n): ")
            if choice.lower() == 'y':
                stop_application('video')
                time.sleep(2)
            else:
                video_enabled = False

    print(f"\n🚀 Starting Kiselgram services...")
    print(f"   Main App: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")
    if video_enabled:
        print(f"   Video Server: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{video_port}")
    else:
        print(f"   Video Server: DISABLED (use --no-video to disable, or remove flag to enable)")
    print(f"   Debug: {args.debug}")
    print(f"   Open Browser: {not args.no_browser}")
    print("-" * 40)

    # Start Flask in a separate thread - PASS THE NO_BROWSER FLAG
    flask_thread = threading.Thread(
        target=run_flask_app,
        args=(args.host, args.port, args.debug, args.no_browser),  # Added no_browser parameter
        daemon=True
    )
    flask_thread.start()

    # Start video server if enabled
    if video_enabled:
        # Small delay to avoid output mixing
        time.sleep(1)
        video_thread = threading.Thread(
            target=run_video_server_process,
            args=(video_port, args.host),
            daemon=True
        )
        video_thread.start()

    # Wait a bit and check if started
    time.sleep(3)

    # Check main app
    main_started = not check_port_available(args.port)

    # Check video if enabled
    video_started = not check_port_available(video_port) if video_enabled else False

    print("\n" + "=" * 40)
    if main_started:
        print("✅ Main application started successfully!")
        print(f"🌐 Main App: http://localhost:{args.port}")
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
    print("Press Ctrl+C to exit this script (services will continue running)")

    try:
        # Keep script alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Management script stopped. Services continue running.")

    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Kiselgram Management Script')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Main app commands (with auto video)
    start_parser = subparsers.add_parser('start',
                                         help='Start main app + video server (use --no-video to disable video)')
    start_parser.add_argument('--port', type=int, default=5000, help='Main app port (default: 5000)')
    start_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    start_parser.add_argument('--debug', action='store_true', default=True, help='Enable debug mode')
    start_parser.add_argument('--no-debug', action='store_false', dest='debug', help='Disable debug mode')
    start_parser.add_argument('--no-browser', action='store_true', help="Don't open browser automatically")

    # Video server options for main start
    start_parser.add_argument('--no-video', action='store_true', help='Disable video server auto-start')
    start_parser.add_argument('--video-port', type=int, default=5001, help='Video server port (default: 5001)')
    start_parser.add_argument('--video-host', default='0.0.0.0', help='Video server host (default: 0.0.0.0)')

    subparsers.add_parser('stop', help='Stop all services')

    restart_parser = subparsers.add_parser('restart', help='Restart all services')
    restart_parser.add_argument('--port', type=int, default=5000, help='Main app port (default: 5000)')
    restart_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    restart_parser.add_argument('--debug', action='store_true', default=True, help='Enable debug mode')
    restart_parser.add_argument('--no-debug', action='store_false', dest='debug', help='Disable debug mode')
    restart_parser.add_argument('--no-browser', action='store_true', help="Don't open browser automatically")
    restart_parser.add_argument('--no-video', action='store_true', help='Disable video server auto-start')
    restart_parser.add_argument('--video-port', type=int, default=5001, help='Video server port (default: 5001)')

    status_parser = subparsers.add_parser('status', help='Check service status')
    status_parser.add_argument('--all', action='store_true', help='Check all services')

    # Video subcommands
    video_parser = subparsers.add_parser('video', help='Video server commands')
    video_subparsers = video_parser.add_subparsers(dest='video_command', help='Video command to execute')

    # Video start
    video_start_parser = video_subparsers.add_parser('start', help='Start video server')
    video_start_parser.add_argument('--port', type=int, default=5001, help='Port to run on (default: 5001)')
    video_start_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')

    # Video stop
    video_subparsers.add_parser('stop', help='Stop video server')

    # Video restart
    video_restart_parser = video_subparsers.add_parser('restart', help='Restart video server')
    video_restart_parser.add_argument('--port', type=int, default=5001, help='Port to run on (default: 5001)')
    video_restart_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')

    # Video status
    video_subparsers.add_parser('status', help='Check video server status')

    # Utility commands
    subparsers.add_parser('setup', help='Setup environment')
    subparsers.add_parser('clean', help='Clean temporary files')
    subparsers.add_parser('reset-db', help='Reset database (⚠️ deletes data)')
    subparsers.add_parser('test', help='Run basic tests')
    subparsers.add_parser('help', help='Show help')

    args = parser.parse_args()

    if not args.command:
        print_header()
        print("\n❌ No command specified. Use 'python manage.py help' for usage.")
        return

    # Handle video commands
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

    # Handle other commands
    if args.command == 'start':
        start_all_services(args)

    elif args.command == 'stop':
        print_header()
        print("\n🛑 Stopping all services...")
        stop_application('all')

    elif args.command == 'restart':
        print_header()
        print("\n🔄 Restarting all services...")

        # Stop all services
        stop_application('all')
        time.sleep(3)

        # Clear temp files
        clean_temporary_files()

        # Start again
        start_all_services(args)

    elif args.command == 'status':
        print_header()
        if hasattr(args, 'all') and args.all:
            check_application('all')
        else:
            check_application('main')
            # Also show video status hint
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


# Cleanup on exit
def cleanup():
    """Cleanup function called on exit"""
    # Clean up temporary files
    for tmp_file in ['tmp_runner.py', 'tmp_video_runner.py', 'init_db.py']:
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
        sys.exit(1)