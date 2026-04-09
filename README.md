
# Kiselgram V3.0
## 🚀 Complete Self-Hosted Messaging + Video Chat Platform

#

<div align="center">
  <!-- Main Animated Banner -->
  <img src="banner-1.png" alt="Kiselgram Banner" width="100%" style="
    animation: bannerFloat 6s ease-in-out infinite;
    filter: brightness(1.1) contrast(1.05);
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    max-width: 800px;
  ">
  
  <!-- Scrolling Features Ticker - GREEN + BLUE THEME -->
  <div class="features-ticker" style="
    position: relative;
    background: linear-gradient(135deg, 
      #00d4ff 0%, 
      #0099ff 25%, 
      #00ff88 50%, 
      #32cd32 75%, 
      #00bfff 100%);
    height: 80px;
    border-radius: 12px;
    margin: 15px 0;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,150,255,0.4);
    display: flex;
    align-items: center;
    border: 2px solid #00ccff;
  ">
    <div class="features-track" style="
      display: flex;
      white-space: nowrap;
      animation: scrollFeatures 20s linear infinite;
      font-family: 'Segoe UI', sans-serif;
      font-size: 1.3em;
      font-weight: 600;
    ">
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">💬 Personal Chats</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">👥 Groups</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">📢 Channels</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">🎥 Video Calls</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">📁 File Sharing</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">🔍 Search</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">🎨 Modern UI</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">🔒 Privacy</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">💬 Personal Chats</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">👥 Groups</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">📢 Channels</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">🎥 Video Calls</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">📁 File Sharing</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">🔍 Search</span>
      <span style="color: #ffffff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,212,255,0.5);">🎨 Modern UI</span>
      <span style="color: #e0f8ff; margin: 0 60px; text-shadow: 0 2px 8px rgba(0,255,136,0.5);">🔒 Privacy</span>
    </div>
  </div>
</div>

<style>
@keyframes bannerFloat {
  0%, 100% { transform: translateY(0px) scale(1); }
  50% { transform: translateY(-10px) scale(1.02); }
}

@keyframes scrollFeatures {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

@media (max-width: 768px) {
  .features-track { font-size: 1.1em; }
  .features-track span { margin: 0 40px; }
}
</style>


<style>
@keyframes bannerFloat {
  0%, 100% { transform: translateY(0px) scale(1); }
  50% { transform: translateY(-10px) scale(1.02); }
}

@keyframes scrollFeatures {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

@media (max-width: 768px) {
  .features-track { font-size: 1.1em; }
  .features-track span { margin: 0 40px; }
}
</style>

**Kiselgram** - Modern Telegram-inspired platform with **personal chats**, **groups**, **channels**, **file sharing**, and **WebRTC video calls**. Fully self-contained, production-ready.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-green)](https://flask.palletsprojects.com)
[![WebRTC](https://img.shields.io/badge/WebRTC-P2P-orange)](https://webrtc.org)
[![License](https://img.shields.io/badge/License-MIT-brightgreen)](LICENSE)

[🚀 Quick Start](#quick-start) • [✨ Features](#features) • [📁 Structure](#structure) • [🔧 Commands](#commands) • [🌐 API](#api)

## ✨ Features

| Feature | Status | Description |
|---------|--------|-------------|
| 💬 **Personal Chats** | ✅ | Direct messaging with real-time updates |
| 👥 **Group Chats** | ✅ | Member management, permissions |
| 📢 **Channels** | ✅ | Broadcast with invite links |
| 🎥 **Video Calls** | ✅ | WebRTC P2P, multi-participant via `video_server/` |
| 📁 **File Sharing** | ✅ | Images/docs/videos (16MB max) |
| 🔍 **Search** | ✅ | Global message/user search |
| 🎨 **Modern UI** | ✅ | Two-column, dark mode, mobile-responsive |
| 🔒 **Privacy** | ✅ | Block/clear/delete, profile settings |

## 🚀 Quick Start

```bash
# Clone & Setup
git clone https://github.com/kiselgram/kiselgram.git
cd kiselgram

# Virtual Environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt

# Initial Setup
python manage.py setup

# Start Everything (main + video server)
python manage.py start
```

**🌐 Access Points:**
Main App:     http://localhost:5000
Video Server: http://localhost:5001
Video Rooms:  http://localhost:5000/video/
API Docs:     http://localhost:5000/api/status

## 📁 Project Structure

```
kiselgram/
├── app/                    # Main Flask application
│   ├── models.py          # SQLAlchemy database models
│   ├── routes/            # Feature blueprints
│   │   ├── api.py         # REST API endpoints
│   │   ├── chats.py       # Chat routes
│   │   ├── groups.py      # Group management
│   │   └── video_integration.py  # Video call integration
│   ├── uploads/           # User uploaded files
│   └── utils/
├── video_server/          # WebRTC signaling server
│   ├── app.py            # SocketIO + WebRTC signaling
│   ├── templates/video/
│   │   ├── room.html     # Video room UI
│   │   └── room_full.html
│   └── static/js/        # WebRTC client logic
├── static/                # CSS/JS assets
│   ├── banner.png        # Main banner
│   └── kiselgram-banner.jpg
├── templates/             # HTML templates
├── instance/              # SQLite database
│   └── kiselgram.db
├── manage.py             # Management CLI
├── requirements.txt
├── logs/                 # Application logs
└── restart.sh            # Service restart script
```

## 🔧 Management Commands

```bash
# Core Commands
python manage.py start              # Start main + video server
python manage.py start --port 3000  # Custom port
python manage.py start --no-video   # Main app only
python manage.py stop               # Graceful shutdown
python manage.py status             # Service status
python manage.py restart            # Restart services

# Database & Maintenance
python manage.py setup              # Initial setup
python manage.py reset-db           # ⚠️ Delete all data
python manage.py clean              # Clear temp files
python manage.py test               # Run tests

# Video Server Only
python manage.py video start        # Video server only
python manage.py video stop
```

## 🎥 Video Chat Flow

```
1. Chat → Video Icon → POST /video/create-room
2. Redirect → http://localhost:5001/video/join/{room_id}
3. WebRTC → getUserMedia() → SocketIO signaling → P2P streams
4. UI → video_server/templates/video/room.html (grid layout)
```

**Key Files:**
- `app/routes/video_integration.py` - Creates rooms from chats
- `video_server/app.py` - SocketIO signaling (offer/answer/ICE)
- `video_server/templates/video/room.html` - Multi-participant UI

## 🌐 API Endpoints

### Messages
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/messages/<user_id>` | GET | Get chat history |
| `/api/send_message` | POST | Send direct message |
| `/api/group_messages/<group_id>` | GET | Group chat history |

### Video
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/video/rooms` | GET/POST | List/create rooms |
| `/video/join/<room_id>` | GET | Join video room |
| `/video/health` | GET | Video server status |

### Users
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/users` | GET | List users |
| `/api/user_status/<id>` | GET | Online status |
| `/api/mark_read/<id>` | POST | Mark messages read |

## 🛠️ Tech Stack

| Category | Technologies |
|----------|--------------|
| **Backend** | Python 3.10+, Flask, SQLAlchemy, SQLite |
| **Realtime** | Flask-SocketIO, WebRTC, WebSockets |
| **Frontend** | HTML5, CSS3, JavaScript ES6+, FontAwesome |
| **Media** | Pillow (thumbnails), HTML5 video |
| **Database** | SQLite (`instance/kiselgram.db`) |

## 📱 File Upload Support

| Type | Extensions | Max Size |
|------|------------|----------|
| Images | `.png .jpg .gif .webp` | 16MB |
| Documents | `.pdf .docx .txt` | 16MB |
| Video | `.mp4 .webm .mov` | 16MB |
| Audio | `.mp3 .wav .m4a` | 16MB |

**Storage:** `app/uploads/` + `uploads/` directories

## 🔒 Environment Variables
### Just run the setup command! 
```bash
  python manage.py setup
```
## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors & Credits

**DANILKISEL** - Creator & Lead Developer

## 🙏 Acknowledgments

- **Flask-SocketIO** & **WebRTC** communities
- **Telegram** for UI inspiration
- All contributors and early testers

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/kiselgram/kiselgram/issues)
- 💬 **Discord**: [discord.gg/kiselgram](https://discord.gg/NtSKWFns)
- 📧 **Email**: [grown.dk.up@gmail.com](mailto:grown.dk.up@gmail.com)
- 💬 **Telegram**: [Our Channel](https://t.me/kiseigram), [DANILKISEL](https://t.me/dka_dmin)
