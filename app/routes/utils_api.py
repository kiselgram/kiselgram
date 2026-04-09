"""
Utility API Blueprint Routes
Provides health checks, environment testing, and shutdown functionality
"""

import os
import sys
import signal
import platform
import time
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from functools import wraps

# Try to import psutil (optional)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

utils_api_bp = Blueprint('utils_api', __name__, url_prefix='/api/utils')

# Token for authentication (set via environment variable)
SHUTDOWN_TOKEN = os.environ.get('KISELGRAM_TOKEN', 'default-token-change-me')

def require_token(f):
    """Decorator to require valid token for protected endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('X-API-Token') or request.args.get('token')

        # Also check JSON body for POST requests
        if request.is_json and not token:
            token = request.json.get('token')

        if not token or token != SHUTDOWN_TOKEN:
            current_app.logger.warning(f"Unauthorized access attempt to {request.path} from {request.remote_addr}")
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Invalid or missing token'
            }), 401
        return f(*args, **kwargs)
    return decorated_function

@utils_api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - Returns basic service status"""
    try:
        health_data = {
            'status': 'healthy',
            'service': current_app.config.get('APP_NAME', 'kiselgram'),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': current_app.config.get('VERSION', '2.0.0'),
            'environment': current_app.config.get('ENV', 'production'),
            'python_version': sys.version.split()[0],
            'platform': platform.platform()
        }

        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                health_data['uptime_seconds'] = int(datetime.now().timestamp() - process.create_time())
            except:
                pass

        # Check database connection
        try:
            from app import db
            db.session.execute('SELECT 1')
            health_data['database'] = 'connected'
        except Exception as e:
            health_data['database'] = 'error'
            health_data['status'] = 'degraded'
            current_app.logger.error(f"Database health check failed: {e}")

        # Check video server if configured
        video_port = os.environ.get('VIDEO_PORT', '5001')
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', int(video_port)))
            sock.close()
            health_data['video_server'] = 'connected' if result == 0 else 'disconnected'
        except:
            health_data['video_server'] = 'unknown'

        return jsonify(health_data)

    except Exception as e:
        current_app.logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500

@utils_api_bp.route('/health/detailed', methods=['GET'])
@require_token
def detailed_health():
    """Detailed health check with system information - Requires token"""
    try:
        if not PSUTIL_AVAILABLE:
            return jsonify({
                'error': 'psutil not installed',
                'message': 'Install psutil for detailed health checks: pip install psutil'
            }), 500

        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=1)

        # System info
        system_info = {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'memory_available_gb': round(psutil.virtual_memory().available / (1024**3), 2),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': {}
        }

        # Add disk usage for relevant paths
        for path in ['/', '.', '/uploads']:
            try:
                if os.path.exists(path):
                    usage = psutil.disk_usage(path)
                    system_info['disk_usage'][path] = {
                        'total_gb': round(usage.total / (1024**3), 2),
                        'used_gb': round(usage.used / (1024**3), 2),
                        'free_gb': round(usage.free / (1024**3), 2),
                        'percent': usage.percent
                    }
            except:
                pass

        # Process info
        process_info = {
            'pid': process.pid,
            'name': process.name(),
            'status': process.status(),
            'created': datetime.fromtimestamp(process.create_time()).isoformat(),
            'cpu_percent': cpu_percent,
            'memory_rss_mb': round(memory_info.rss / (1024**2), 2),
            'memory_vms_mb': round(memory_info.vms / (1024**2), 2),
            'memory_percent': round(process.memory_percent(), 2),
            'threads': process.num_threads(),
            'connections': len(process.connections()),
            'open_files': len(process.open_files())
        }

        # Application info
        app_info = {
            'name': current_app.config.get('APP_NAME', 'Kiselgram'),
            'version': current_app.config.get('VERSION', '2.0.0'),
            'debug': current_app.debug,
            'testing': current_app.testing,
            'secret_key_set': bool(current_app.secret_key),
            'upload_folder': current_app.config.get('UPLOAD_FOLDER', 'uploads'),
            'max_content_length_mb': current_app.config.get('MAX_CONTENT_LENGTH', 0) / (1024**2)
        }

        # Count database records if models exist
        try:
            from app.models import User, Message, Group, Channel
            db_stats = {
                'users': User.query.count(),
                'messages': Message.query.count(),
                'groups': Group.query.count(),
                'channels': Channel.query.count()
            }
            app_info['database_stats'] = db_stats
        except:
            pass

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'system': system_info,
            'process': process_info,
            'application': app_info
        })

    except Exception as e:
        current_app.logger.error(f"Detailed health check error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500

@utils_api_bp.route('/test/env', methods=['GET', 'POST'])
def test_environment():
    """Test environment endpoint - Returns sanitized environment info"""
    if request.method == 'POST':
        # POST returns more detailed info with optional token
        token = request.headers.get('X-API-Token')
        if request.is_json:
            token = token or request.json.get('token')
        detailed = token == SHUTDOWN_TOKEN
    else:
        detailed = False

    # Basic environment info (safe to expose)
    env_info = {
        'python_version': sys.version,
        'platform': platform.platform(),
        'working_directory': os.getcwd(),
        'environment_variables': {
            'FLASK_ENV': os.environ.get('FLASK_ENV', 'not set'),
            'DATABASE_URL': '[REDACTED]' if not detailed else os.environ.get('DATABASE_URL', 'not set'),
            'VIDEO_PORT': os.environ.get('VIDEO_PORT', 'not set'),
            'VIDEO_HOST': os.environ.get('VIDEO_HOST', 'not set')
        }
    }

    # Add more details if authorized
    if detailed:
        # Add safe environment variables
        safe_vars = {}
        for k, v in os.environ.items():
            if not any(sensitive in k.upper() for sensitive in ['KEY', 'TOKEN', 'PASSWORD', 'SECRET']):
                safe_vars[k] = v
        env_info['environment_variables'].update(safe_vars)

        # Add sys.path
        env_info['sys_path'] = sys.path

        # Add safe config values
        safe_config = {}
        for k, v in current_app.config.items():
            if not any(sensitive in k.upper() for sensitive in ['KEY', 'TOKEN', 'PASSWORD', 'SECRET']):
                if isinstance(v, (str, int, float, bool)):
                    safe_config[k] = v
        env_info['config'] = safe_config

    return jsonify({
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'environment': env_info,
        'detailed': detailed,
        'request': {
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.user_agent.string
        }
    })

@utils_api_bp.route('/test/env/shutdown', methods=['GET', 'POST'])
@require_token
def shutdown():
    """Gracefully shutdown the application - Requires token"""
    try:
        shutdown_info = {
            'message': 'Shutdown initiated',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'pid': os.getpid()
        }

        # Log the shutdown request
        current_app.logger.warning(f"⚠️ Shutdown requested from {request.remote_addr}")

        # Get reference to app for context
        app = current_app._get_current_object()

        # Return response before shutting down
        response = jsonify(shutdown_info)

        # Schedule shutdown (give time for response to be sent)
        def shutdown_server(app):
            """Shutdown server with proper app context"""
            time.sleep(1)

            # Use app context for cleanup operations
            with app.app_context():
                try:
                    # Try to clean up database
                    from app import db
                    db.session.remove()
                    app.logger.info("Database session cleaned up")
                except Exception as e:
                    app.logger.error(f"Database cleanup error: {e}")

                app.logger.info("Shutting down server...")

            # Shutdown without app context
            if platform.system() == 'Windows':
                # Windows shutdown
                os.kill(os.getpid(), signal.CTRL_C_EVENT)
            else:
                # Unix-like shutdown
                os.kill(os.getpid(), signal.SIGTERM)

            # Force exit after 5 seconds if still running
            time.sleep(5)
            print("Force exiting...", file=sys.stderr)
            os._exit(0)

        import threading
        shutdown_thread = threading.Thread(target=shutdown_server, args=(app,))
        shutdown_thread.daemon = True
        shutdown_thread.start()

        return response

    except Exception as e:
        current_app.logger.error(f"Shutdown error: {e}")
        return jsonify({
            'error': 'Shutdown failed',
            'message': str(e)
        }), 500

@utils_api_bp.route('/stats', methods=['GET'])
@require_token
def get_stats():
    """Get application statistics - Requires token"""
    try:
        stats = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'database': {},
            'system': {},
            'uploads': {}
        }

        # Database stats
        try:
            from app.models import User, Message, Group, Channel
            from app import db
            from sqlalchemy import func

            stats['database'] = {
                'users': User.query.count(),
                'messages': Message.query.count(),
                'groups': Group.query.count(),
                'channels': Channel.query.count()
            }

            # Get latest activity
            try:
                latest_message = Message.query.order_by(Message.created_at.desc()).first()
                if latest_message:
                    stats['database']['latest_activity'] = latest_message.created_at.isoformat()
            except:
                pass

        except Exception as e:
            stats['database'] = {'error': str(e)}

        # Upload stats
        try:
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            if os.path.exists(upload_folder):
                total_size = 0
                file_count = 0
                for root, dirs, files in os.walk(upload_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                        file_count += 1

                stats['uploads'] = {
                    'total_files': file_count,
                    'total_size_mb': round(total_size / (1024**2), 2)
                }
        except Exception as e:
            stats['uploads'] = {'error': str(e)}

        # System stats
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            memory = process.memory_info()

            stats['system'] = {
                'cpu_percent': process.cpu_percent(),
                'memory_rss_mb': round(memory.rss / (1024**2), 2),
                'memory_vms_mb': round(memory.vms / (1024**2), 2),
                'threads': process.num_threads(),
                'connections': len(process.connections()),
                'uptime_seconds': int(datetime.now().timestamp() - process.create_time())
            }

        return jsonify(stats)

    except Exception as e:
        current_app.logger.error(f"Stats error: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500

@utils_api_bp.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint for connectivity testing"""
    return jsonify({
        'ping': 'pong',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'service': current_app.config.get('APP_NAME', 'kiselgram'),
        'version': current_app.config.get('VERSION', '2.0.0')
    })

@utils_api_bp.route('/endpoints', methods=['GET'])
def list_endpoints():
    """List all available utility endpoints"""
    endpoints = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint.startswith('utils_api.'):
            endpoints.append({
                'path': rule.rule,
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'endpoint': rule.endpoint,
                'requires_token': 'require_token' in str(current_app.view_functions[rule.endpoint])
            })

    return jsonify({
        'prefix': '/api/utils',
        'endpoints': endpoints,
        'documentation': {
            'health': 'GET /api/utils/health - Public health check',
            'detailed_health': 'GET /api/utils/health/detailed - Detailed health (requires token)',
            'test_env': 'GET|POST /api/utils/test/env - Environment info',
            'shutdown': 'GET|POST /api/utils/test/env/shutdown - Shutdown server (requires token)',
            'stats': 'GET /api/utils/stats - Application statistics (requires token)',
            'ping': 'GET /api/utils/ping - Simple ping test',
            'endpoints': 'GET /api/utils/endpoints - This list'
        }
    })