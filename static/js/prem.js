// static/js/prem.js
// Kiselgram Premium Edition - Complete

(function() {
    'use strict';

    console.log('✨ Kiselgram Premium v4.0.0');

    // State
    window.isPremium = true;
    window.PREMIUM_FEATURES = {
        fonts: true, stories: true, wallpapers: true, animatedStickers: true,
        videoAvatars: true, chatStats: true, customNotifications: true,
        largeUploads: true, botApi: true, prioritySupport: true
    };

    window.currentUserId = null;
    window.currentUserUsername = '';
    window.currentUserDisplayName = '';
    window.currentUserAvatar = '?';
    window.activeChat = null;
    window.selectedMembers = [];
    window.replyToMessage = null;
    window.currentStories = [];
    window.currentStoryIndex = 0;
    window.currentStoryUser = null;
    window.storyProgressInterval = null;

    // DOM helper
    function getEl(id) { return document.getElementById(id); }

    window.hasFeature = (feature) => window.isPremium && window.PREMIUM_FEATURES[feature] === true;

    // Initialize
    document.addEventListener('DOMContentLoaded', async () => {
        await loadCurrentUser();
        await loadChatList();
        await loadStories();
        setupEventListeners();
        loadThemePreference();
        loadFontPreference();

        if (hasFeature('videoAvatars')) {
            const avatarInput = getEl('avatarInput');
            if (avatarInput) avatarInput.accept = 'image/*,video/*';
        }

        const urlParams = new URLSearchParams(window.location.search);
        const chatId = urlParams.get('chat');
        if (chatId) setTimeout(() => openChat('personal', parseInt(chatId)), 500);

        setInterval(loadChatList, 30000);
        setInterval(loadStories, 120000);
        setInterval(() => { if (window.activeChat) loadMessages(window.activeChat.type, window.activeChat.id); }, 5000);
    });

    async function loadCurrentUser() {
        try {
            const res = await fetch('/api/profile');
            const data = await res.json();
            if (data.success && data.user) {
                window.currentUserId = data.user.id;
                window.currentUserUsername = data.user.username;
                window.currentUserDisplayName = data.user.display_name || data.user.username;
                window.currentUserAvatar = data.user.username[0].toUpperCase();
                updateUI();
            }
        } catch (e) {}
    }

    function updateUI() {
        const avatar = getEl('menuUserAvatar');
        const name = getEl('menuUserName');
        const username = getEl('menuUserUsername');
        if (avatar) avatar.textContent = window.currentUserAvatar;
        if (name) name.innerHTML = `${window.currentUserDisplayName} <span class="premium-badge">PREMIUM</span>`;
        if (username) username.textContent = '@' + window.currentUserUsername;
    }

    function setupEventListeners() {
        getEl('menuBtn')?.addEventListener('click', togglePopoutMenu);
        getEl('globalSearchInput')?.addEventListener('input', debounce(handleGlobalSearch, 300));

        const msgInput = getEl('messageInput');
        if (msgInput) {
            msgInput.addEventListener('input', handleMessageInput);
            msgInput.addEventListener('keydown', handleMessageKeydown);
        }
    }

    // Utilities
    function debounce(fn, wait) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
    }

    function escapeHtml(s) {
        if (!s) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function formatTime(ts) {
        if (!ts) return '';
        const d = new Date(ts), n = new Date(), diff = n - d;
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return Math.floor(diff/60000) + 'm ago';
        if (diff < 86400000) return Math.floor(diff/3600000) + 'h ago';
        return d.toLocaleDateString();
    }

    function showToast(msg, type = 'info') {
        const toast = document.createElement('div');
        toast.textContent = msg;
        toast.style.cssText = `
            position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
            background:${type==='success'?'#2dce89':type==='error'?'#fb6340':'#5e72e4'};
            color:white;padding:12px 24px;border-radius:30px;font-weight:500;
            z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    window.showToast = showToast;

    // Menu
    function togglePopoutMenu() {
        document.body.classList.toggle('popout-open');
        getEl('menuBtn')?.classList.toggle('active');
    }

    window.closePopout = () => {
        document.body.classList.remove('popout-open');
        getEl('menuBtn')?.classList.remove('active');
    };

    // Theme & Font
    window.setTheme = (theme) => {
        document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('active'));
        event?.currentTarget?.classList.add('active');
        if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
        else if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
        else document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('kiselgram_theme', theme);
    };

    function loadThemePreference() {
        const t = localStorage.getItem('kiselgram_theme');
        if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
        else if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
    }

    window.setFont = (el) => {
        document.querySelectorAll('.font-option').forEach(o => o.classList.remove('active'));
        el.classList.add('active');
        document.body.style.setProperty('--font-family', el.dataset.font);
        localStorage.setItem('kiselgram_font', el.dataset.font);
        showToast('Font updated', 'success');
    };

    function loadFontPreference() {
        const f = localStorage.getItem('kiselgram_font');
        if (f) document.body.style.setProperty('--font-family', f);
    }

    // Stories
    async function loadStories() {
        if (!window.currentUserId) return;
        try {
            const res = await fetch('/api/stories');
            const data = await res.json();
            if (data.success) {
                window.currentStories = data.stories || [];
                renderStoriesRow();
            }
        } catch (e) {}
    }

    function renderStoriesRow() {
        const row = getEl('storiesRow');
        if (!row) return;
        const stories = window.currentStories || [];
        const hasStory = stories.some(s => s.user_id === window.currentUserId);

        let html = `
            <div class="story-item" onclick="showCreateStoryModal()">
                <div class="story-avatar ${hasStory ? '' : 'add-story'}">
                    ${hasStory ? `<div class="story-avatar-placeholder">${window.currentUserAvatar}</div>` : `<div class="add-story-btn">+</div>`}
                </div>
                <span class="story-username">Your story</span>
            </div>
        `;

        for (const s of stories) {
            if (s.user_id === window.currentUserId) continue;
            const f = s.stories[0];
            html += `
                <div class="story-item" onclick="openStoryViewer(${s.user_id})">
                    <div class="story-avatar ${s.has_unviewed ? 'unviewed' : 'viewed'}">
                        ${f?.media_url && f.media_type === 'image' ? `<img src="${f.media_url}">` : `<div class="story-avatar-placeholder">${s.avatar_letter}</div>`}
                    </div>
                    <span class="story-username">${escapeHtml(s.display_name)}</span>
                </div>
            `;
        }
        row.innerHTML = html;
    }

    window.showCreateStoryModal = () => {
        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.innerHTML = `
            <div class="modal-container" style="max-width:400px">
                <div class="modal-header" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white">
                    <h3>Create Story</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color:white">✕</button>
                </div>
                <div class="modal-body">
                    <div class="story-media-upload" onclick="document.getElementById('storyMediaInput').click()">
                        <div class="upload-placeholder" id="storyMediaPreview">
                            <span style="font-size:48px">📸</span>
                            <p>Click to upload</p>
                        </div>
                        <input type="file" id="storyMediaInput" accept="image/*,video/*" style="display:none" onchange="previewStoryMedia(this)">
                    </div>
                    <textarea id="storyCaption" class="modal-input" placeholder="Caption..." rows="2"></textarea>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="modal-btn modal-btn-primary" onclick="uploadStory()" style="background:linear-gradient(135deg,#fb6340,#2dce89)">Post</button>
                </div>
            </div>
        `;
        (getEl('modalRoot') || document.body).appendChild(m);
    };

    window.previewStoryMedia = (i) => {
        const f = i.files[0];
        if (!f) return;
        const p = getEl('storyMediaPreview');
        if (!p) return;
        p.innerHTML = f.type.startsWith('video/')
            ? `<video src="${URL.createObjectURL(f)}" autoplay loop muted style="width:100%;height:100%;object-fit:cover"></video>`
            : `<img src="${URL.createObjectURL(f)}" style="width:100%;height:100%;object-fit:cover">`;
    };

    window.uploadStory = async () => {
        const f = getEl('storyMediaInput')?.files[0];
        if (!f) { showToast('Select media', 'error'); return; }
        const fd = new FormData();
        fd.append('media', f);
        fd.append('caption', getEl('storyCaption')?.value || '');
        try {
            const res = await fetch('/api/stories/create', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) {
                document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
                showToast('Story posted!', 'success');
                loadStories();
            }
        } catch (e) {}
    };

    window.openStoryViewer = (uid) => {
        const u = window.currentStories.find(s => s.user_id === uid);
        if (!u) return;
        window.currentStoryUser = u;
        window.currentStoryIndex = 0;
        renderStoryViewer();
    };

    function renderStoryViewer() {
        const story = window.currentStoryUser?.stories?.[window.currentStoryIndex];
        if (!story) return;
        const v = document.createElement('div');
        v.className = 'story-viewer';
        v.id = 'storyViewer';
        v.innerHTML = `
            <div class="story-viewer-header">
                <div class="story-progress-container">
                    ${window.currentStoryUser.stories.map((_, i) => `
                        <div class="story-progress-bar-container">
                            <div class="story-progress-bar ${i < window.currentStoryIndex ? 'completed' : ''}" id="storyProgress${i}"></div>
                        </div>
                    `).join('')}
                </div>
                <div class="story-viewer-user">
                    <div class="story-viewer-avatar">${window.currentStoryUser.avatar_letter}</div>
                    <div class="story-viewer-info">
                        <span class="story-viewer-name">${escapeHtml(window.currentStoryUser.display_name)}</span>
                        <span class="story-viewer-time">${formatTime(story.created_at)}</span>
                    </div>
                </div>
                <button class="story-viewer-close" onclick="closeStoryViewer()">✕</button>
            </div>
            <div class="story-viewer-content">
                ${story.media_type === 'video' ? `<video src="${story.media_url}" autoplay loop muted></video>` : `<img src="${story.media_url}">`}
                ${story.caption ? `<div class="story-caption">${escapeHtml(story.caption)}</div>` : ''}
            </div>
            <div class="story-viewer-footer">
                <div class="story-reply-input">
                    <input type="text" placeholder="Send message..." id="storyReplyInput">
                    <button onclick="sendStoryReply()">➤</button>
                </div>
                <div class="story-actions">
                    <button onclick="likeCurrentStory()" id="storyLikeBtn">${story.liked ? '❤️' : '🤍'} ${story.like_count || 0}</button>
                    <button onclick="deleteCurrentStory()" ${window.currentStoryUser.user_id !== window.currentUserId ? 'style="display:none"' : ''}>🗑️</button>
                </div>
            </div>
            <div class="story-nav">
                <div class="story-nav-left" onclick="previousStory()"></div>
                <div class="story-nav-right" onclick="nextStory()"></div>
            </div>
        `;
        document.body.appendChild(v);
        document.body.style.overflow = 'hidden';
        startProgress();
        fetch(`/api/stories/${story.id}/view`, { method: 'POST' });
    }

    function startProgress() {
        if (window.storyProgressInterval) clearInterval(window.storyProgressInterval);
        const b = getEl(`storyProgress${window.currentStoryIndex}`);
        if (!b) return;
        let w = 0;
        window.storyProgressInterval = setInterval(() => {
            w += 1;
            b.style.width = w + '%';
            if (w >= 100) { clearInterval(window.storyProgressInterval); nextStory(); }
        }, 50);
    }

    window.nextStory = () => {
        if (window.currentStoryIndex < window.currentStoryUser.stories.length - 1) {
            window.currentStoryIndex++;
            getEl('storyViewer')?.remove();
            renderStoryViewer();
        } else {
            const idx = window.currentStories.findIndex(s => s.user_id === window.currentStoryUser.user_id);
            if (idx < window.currentStories.length - 1) {
                window.currentStoryUser = window.currentStories[idx + 1];
                window.currentStoryIndex = 0;
                getEl('storyViewer')?.remove();
                renderStoryViewer();
            } else {
                closeStoryViewer();
            }
        }
    };

    window.previousStory = () => {
        if (window.currentStoryIndex > 0) {
            window.currentStoryIndex--;
            getEl('storyViewer')?.remove();
            renderStoryViewer();
        } else {
            const idx = window.currentStories.findIndex(s => s.user_id === window.currentStoryUser.user_id);
            if (idx > 0) {
                window.currentStoryUser = window.currentStories[idx - 1];
                window.currentStoryIndex = window.currentStoryUser.stories.length - 1;
                getEl('storyViewer')?.remove();
                renderStoryViewer();
            }
        }
    };

    window.closeStoryViewer = () => {
        if (window.storyProgressInterval) clearInterval(window.storyProgressInterval);
        getEl('storyViewer')?.remove();
        document.body.style.overflow = '';
        loadStories();
    };

    window.likeCurrentStory = async () => {
        const s = window.currentStoryUser?.stories?.[window.currentStoryIndex];
        if (!s) return;
        try {
            const res = await fetch(`/api/stories/${s.id}/like`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                s.liked = data.liked;
                s.like_count = data.like_count;
                const b = getEl('storyLikeBtn');
                if (b) b.innerHTML = `${data.liked ? '❤️' : '🤍'} ${data.like_count}`;
            }
        } catch (e) {}
    };

    window.deleteCurrentStory = async () => {
        if (!confirm('Delete this story?')) return;
        const s = window.currentStoryUser?.stories?.[window.currentStoryIndex];
        if (!s) return;
        try {
            const res = await fetch(`/api/stories/${s.id}`, { method: 'DELETE' });
            if (res.ok) {
                window.currentStoryUser.stories.splice(window.currentStoryIndex, 1);
                if (window.currentStoryUser.stories.length === 0) {
                    const idx = window.currentStories.findIndex(x => x.user_id === window.currentStoryUser.user_id);
                    if (idx > -1) window.currentStories.splice(idx, 1);
                    closeStoryViewer();
                } else {
                    if (window.currentStoryIndex >= window.currentStoryUser.stories.length) {
                        window.currentStoryIndex = window.currentStoryUser.stories.length - 1;
                    }
                    getEl('storyViewer')?.remove();
                    renderStoryViewer();
                }
            }
        } catch (e) {}
    };

    window.sendStoryReply = () => {
        const m = getEl('storyReplyInput')?.value.trim();
        if (!m) return;
        openChat('personal', window.currentStoryUser.user_id);
        setTimeout(() => {
            const input = getEl('messageInput');
            if (input) { input.value = m; getEl('sendBtn').disabled = false; }
        }, 500);
        closeStoryViewer();
    };

    // Chat List
    async function loadChatList() {
        try {
            const res = await fetch('/api/chat_list');
            const data = await res.json();
            if (data.success) renderChatList(data.chats);
        } catch (e) {}
    }

    function renderChatList(chats) {
        const container = getEl('chatList');
        if (!container) return;
        if (!chats?.length) {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No chats yet</p></div>';
            return;
        }
        container.innerHTML = chats.map(c => {
            const active = window.activeChat?.type === c.type && window.activeChat?.id === c.id;
            const avatar = c.avatar_url ? `<img src="${c.avatar_url}">` : (c.avatar || '?');
            return `
                <div class="chat-item ${active ? 'active' : ''}" data-chat-type="${c.type}" data-chat-id="${c.id}" onclick="openChat('${c.type}',${c.id})">
                    <div class="chat-avatar ${c.type} ${c.has_story ? 'has-story' : ''}">${avatar}${c.type==='personal'&&c.is_online?'<span class="online-indicator"></span>':''}</div>
                    <div class="chat-info">
                        <div class="chat-name-row"><span class="chat-name">${escapeHtml(c.name)}</span><span class="chat-time">${c.timestamp||''}</span></div>
                        <div class="chat-preview"><span>${escapeHtml(c.last_message||'No messages')}</span>${c.unread_count>0?`<span class="unread-badge">${c.unread_count}</span>`:''}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Chat View
    function hideAllPanels() {
        ['emptyChat','chatView','contactsView','createGroupView','createChannelView'].forEach(id => {
            const el = getEl(id);
            if (el) el.style.display = 'none';
        });
    }

    window.openChat = async (type, id) => {
        window.activeChat = { type, id };
        document.querySelectorAll('.chat-item').forEach(i => i.classList.remove('active'));
        document.querySelector(`.chat-item[data-chat-type="${type}"][data-chat-id="${id}"]`)?.classList.add('active');

        hideAllPanels();
        const chatView = getEl('chatView');
        if (chatView) chatView.style.display = 'flex';

        await loadChatInfo(type, id);
        await loadMessages(type, id);
        applyWallpaper();

        if (type === 'personal') await fetch(`/api/mark_read/${id}`, { method: 'POST' });
        getEl('messageInput')?.focus();
    };

    async function loadChatInfo(type, id) {
        const headerName = getEl('chatHeaderName');
        const headerAvatar = getEl('chatHeaderAvatar');
        const headerStatus = getEl('chatHeaderStatus');

        if (type === 'personal') {
            try {
                const res = await fetch('/api/users');
                const data = await res.json();
                const user = data.users?.find(u => u.id === id);
                if (user) {
                    if (headerName) headerName.textContent = user.display_name || user.username;
                    if (headerStatus) {
                        headerStatus.textContent = user.is_online ? 'Online' : 'Offline';
                        headerStatus.classList.toggle('online', user.is_online);
                    }
                    if (headerAvatar) {
                        headerAvatar.textContent = user.username[0].toUpperCase();
                        headerAvatar.className = 'chat-header-avatar personal';
                    }
                }
            } catch (e) {}
        } else {
            if (headerName) headerName.textContent = type === 'group' ? 'Group' : 'Channel';
            if (headerAvatar) {
                headerAvatar.textContent = type === 'group' ? '👥' : '📢';
                headerAvatar.className = `chat-header-avatar ${type}`;
            }
        }
    }

    async function loadMessages(type, id) {
        const container = getEl('messagesContainer');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"></div>';

        try {
            const url = type === 'personal' ? `/api/messages/${id}` : `/api/group_messages/${id}`;
            const res = await fetch(`${url}?after=0&limit=50`);
            const data = await res.json();
            const msgs = data.messages || (data.success && data.messages) || [];

            if (msgs.length) {
                let html = '', lastDate = null;
                for (const m of msgs) {
                    const md = new Date(m.timestamp || Date.now());
                    const ds = md.toLocaleDateString();
                    if (ds !== lastDate) {
                        const t = new Date(), y = new Date(t); y.setDate(y.getDate()-1);
                        let dt = md.toDateString() === t.toDateString() ? 'Today' : md.toDateString() === y.toDateString() ? 'Yesterday' : md.toLocaleDateString(undefined, {month:'long',day:'numeric'});
                        html += `<div class="message-date-divider">${dt}</div>`;
                        lastDate = ds;
                    }
                    html += renderMessage(m);
                }
                container.innerHTML = html;
            } else {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No messages yet</p></div>';
            }
            container.scrollTop = container.scrollHeight;
            applyWallpaper();
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><p>Error loading messages</p></div>';
        }
    }

    function renderMessage(m) {
        const isOwn = m.is_own || m.sender_id === window.currentUserId;
        let att = '';
        if (m.has_attachment) {
            att = m.file_type === 'image'
                ? `<img src="${m.file_url}" class="message-image" onclick="openImageViewer('${m.file_url}')">`
                : `<div class="file-attachment"><span>📎</span><a href="${m.file_url}" target="_blank">${m.file_name||'File'}</a></div>`;
        }
        let reply = '';
        if (m.reply_to_id) {
            reply = `<div class="reply-indicator"><span>↩️ Reply</span><div>${escapeHtml(m.reply_to_content||'')}</div></div>`;
        }
        const content = m.content || '';
        return `
            <div class="message-wrapper ${isOwn ? 'outgoing' : 'incoming'}" id="msg-${m.id}">
                ${!isOwn ? `<div class="message-sender">${escapeHtml(m.sender_name||'User')}</div>` : ''}
                <div class="message-bubble">
                    ${reply}
                    ${att}
                    ${content ? `<div class="message-text">${escapeHtml(content).replace(/\n/g,'<br>')}</div>` : ''}
                    <div class="message-meta">
                        <span class="message-time">${m.timestamp_formatted||''}</span>
                        ${isOwn ? `<span class="message-status">${m.is_read?'✓✓':'✓'}</span>` : ''}
                    </div>
                </div>
                <div class="message-actions">
                    <span class="action-icon" onclick="setReply(${m.id})">↩️</span>
                    ${isOwn ? `<span class="action-icon" onclick="deleteMessage(${m.id})">🗑️</span>` : ''}
                </div>
            </div>
        `;
    }

    function handleMessageInput() {
        const input = getEl('messageInput');
        const btn = getEl('sendBtn');
        if (input && btn) btn.disabled = !input.value.trim();
        if (input) { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 100) + 'px'; }
    }

    async function handleMessageKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            await sendMessage();
        }
    }

    async function sendMessage() {
        const input = getEl('messageInput');
        const content = input?.value.trim();
        if (!content || !window.activeChat) return;

        const url = window.activeChat.type === 'personal' ? '/api/send_message' : '/api/send_group_message';
        const payload = { content };
        if (window.activeChat.type === 'personal') payload.receiver_id = window.activeChat.id;
        else payload.group_id = window.activeChat.id;

        if (window.replyToMessage) {
            payload.reply_to_id = window.replyToMessage;
            window.replyToMessage = null;
            const preview = getEl('replyPreview');
            if (preview) preview.style.display = 'none';
        }

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success && data.message) {
                if (input) input.value = '';
                handleMessageInput();
                const container = getEl('messagesContainer');
                if (container) {
                    if (container.querySelector('.empty-state')) container.innerHTML = '';
                    container.insertAdjacentHTML('beforeend', renderMessage(data.message));
                    container.scrollTop = container.scrollHeight;
                }
                loadChatList();
            }
        } catch (e) {}
    }

    window.setReply = (id) => {
        window.replyToMessage = id;
        const msg = getEl(`msg-${id}`);
        const preview = getEl('replyPreview');
        if (msg && preview) {
            const t = msg.querySelector('.message-text')?.textContent || '';
            preview.querySelector('.reply-preview-name').textContent = 'Replying';
            preview.querySelector('.reply-preview-text').textContent = t.substring(0, 50);
            preview.style.display = 'flex';
        }
    };

    window.cancelReply = () => {
        window.replyToMessage = null;
        const preview = getEl('replyPreview');
        if (preview) preview.style.display = 'none';
    };

    window.deleteMessage = async (id) => {
        if (!confirm('Delete this message?')) return;
        try {
            await fetch(`/api/messages/${id}`, { method: 'DELETE' });
            getEl(`msg-${id}`)?.remove();
        } catch (e) {}
    };

    window.openImageViewer = (url) => window.open(url, '_blank');

    // Chat Customization
    window.openChatCustomization = () => {
        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.innerHTML = `
            <div class="modal-container" style="max-width:450px">
                <div class="modal-header" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white">
                    <h3>Chat Customization</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color:white">✕</button>
                </div>
                <div class="modal-body">
                    <h4>Wallpaper</h4>
                    <div class="wallpaper-options">
                        ${['gradient1','gradient2','gradient3','gradient4','gradient5','default'].map(w => `
                            <div class="wallpaper-option" style="background:${w==='default'?'var(--bg-surface)':''}" onclick="setWallpaper('${w}')">${w==='default'?'Default':''}</div>
                        `).join('')}
                    </div>
                    <h4 style="margin-top:20px">Text Size</h4>
                    <div style="display:flex;gap:8px">
                        <button class="modal-btn modal-btn-secondary" onclick="setTextSize('small')">Small</button>
                        <button class="modal-btn modal-btn-secondary" onclick="setTextSize('medium')">Medium</button>
                        <button class="modal-btn modal-btn-secondary" onclick="setTextSize('large')">Large</button>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-secondary" onclick="resetChatCustomization()">Reset</button>
                    <button class="modal-btn modal-btn-primary" onclick="this.closest('.modal-overlay').remove()">Done</button>
                </div>
            </div>
        `;
        (getEl('modalRoot') || document.body).appendChild(m);
    };

    window.setWallpaper = (w) => {
        if (!window.activeChat) return;
        localStorage.setItem(`wallpaper_${window.activeChat.type}_${window.activeChat.id}`, w);
        applyWallpaper();
        showToast('Wallpaper updated', 'success');
    };

    function applyWallpaper() {
        if (!window.activeChat) return;
        const w = localStorage.getItem(`wallpaper_${window.activeChat.type}_${window.activeChat.id}`) || 'default';
        const c = getEl('messagesContainer');
        if (c) {
            c.classList.remove('wallpaper-gradient1','wallpaper-gradient2','wallpaper-gradient3','wallpaper-gradient4','wallpaper-gradient5');
            if (w !== 'default') c.classList.add(`wallpaper-${w}`);
        }
    }

    window.setTextSize = (size) => {
        const c = getEl('messagesContainer');
        if (c) {
            c.classList.remove('text-small','text-medium','text-large');
            c.classList.add(`text-${size}`);
            localStorage.setItem('chat_text_size', size);
        }
        showToast('Text size updated', 'success');
    };

    window.resetChatCustomization = () => {
        if (!window.activeChat) return;
        localStorage.removeItem(`wallpaper_${window.activeChat.type}_${window.activeChat.id}`);
        localStorage.removeItem('chat_text_size');
        const c = getEl('messagesContainer');
        if (c) {
            c.classList.remove('wallpaper-gradient1','wallpaper-gradient2','wallpaper-gradient3','wallpaper-gradient4','wallpaper-gradient5','text-small','text-medium','text-large');
            c.classList.add('text-medium');
        }
        showToast('Customization reset', 'success');
    };

    // Contacts
    window.showContactsView = () => {
        window.closePopout();
        hideAllPanels();
        const view = getEl('contactsView');
        if (view) view.style.display = 'flex';
        loadContacts();
    };

    window.hideContactsView = () => {
        const view = getEl('contactsView');
        if (view) view.style.display = 'none';
        if (window.activeChat) getEl('chatView').style.display = 'flex';
        else getEl('emptyChat').style.display = 'flex';
    };

    async function loadContacts() {
        const container = getEl('contactsList');
        if (!container) return;
        try {
            const res = await fetch('/api/contacts');
            const data = await res.json();
            if (data.success) {
                container.innerHTML = data.contacts.map(c => `
                    <div class="contact-item" onclick="openChat('personal',${c.id})">
                        <div class="contact-avatar">${c.username[0].toUpperCase()}</div>
                        <div class="contact-info">
                            <div class="contact-name">${escapeHtml(c.display_name)}</div>
                            <div class="contact-username">@${escapeHtml(c.username)}</div>
                        </div>
                        ${c.is_online ? '<span class="online-badge">●</span>' : ''}
                    </div>
                `).join('') || '<div class="empty-state"><p>No contacts</p></div>';
            }
        } catch (e) {}
    }

    // Search
    async function handleGlobalSearch() {
        const input = getEl('globalSearchInput');
        const q = input?.value.trim();
        if (!q || q.length < 2) return;

        try {
            const res = await fetch(`/api/search/global?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            if (data.success) {
                // Handle search results
            }
        } catch (e) {}
    }

    // Groups
    window.showCreateGroupView = () => {
        window.closePopout();
        hideAllPanels();
        const view = getEl('createGroupView');
        if (view) view.style.display = 'flex';
        window.selectedMembers = [];
    };

    window.hideCreateGroupView = () => {
        const view = getEl('createGroupView');
        if (view) view.style.display = 'none';
        if (window.activeChat) getEl('chatView').style.display = 'flex';
        else getEl('emptyChat').style.display = 'flex';
    };

    window.createGroup = async () => {
        const name = getEl('groupName')?.value.trim();
        if (!name) { showToast('Enter group name', 'error'); return; }

        const fd = new FormData();
        fd.append('name', name);
        fd.append('description', getEl('groupDescription')?.value || '');
        fd.append('member_ids', JSON.stringify(window.selectedMembers || []));

        const avatar = getEl('groupAvatarInput');
        if (avatar?.files[0]) fd.append('avatar', avatar.files[0]);

        try {
            const res = await fetch('/api/groups/create', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) {
                showToast('Group created!', 'success');
                window.hideCreateGroupView();
                loadChatList();
                openChat('group', data.group.id);
            }
        } catch (e) {}
    };

    // Channels
    window.showCreateChannelView = () => {
        window.closePopout();
        hideAllPanels();
        const view = getEl('createChannelView');
        if (view) view.style.display = 'flex';
    };

    window.hideCreateChannelView = () => {
        const view = getEl('createChannelView');
        if (view) view.style.display = 'none';
        if (window.activeChat) getEl('chatView').style.display = 'flex';
        else getEl('emptyChat').style.display = 'flex';
    };

    window.createChannel = async () => {
        const name = getEl('channelName')?.value.trim();
        if (!name) { showToast('Enter channel name', 'error'); return; }

        const fd = new FormData();
        fd.append('name', name);
        fd.append('description', getEl('channelDescription')?.value || '');

        const avatar = getEl('channelAvatarInput');
        if (avatar?.files[0]) fd.append('avatar', avatar.files[0]);

        try {
            const res = await fetch('/api/channels/create', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) {
                showToast('Channel created!', 'success');
                window.hideCreateChannelView();
                loadChatList();
                openChat('channel', data.channel.id);
            }
        } catch (e) {}
    };

    // Profile
    window.openProfileModal = () => {
        const modal = getEl('profileModal');
        if (modal) modal.style.display = 'flex';
        loadProfileData();
    };

    window.closeProfileModal = () => {
        const modal = getEl('profileModal');
        if (modal) modal.style.display = 'none';
    };

    async function loadProfileData() {
        try {
            const res = await fetch('/api/profile');
            const data = await res.json();
            if (data.success && data.user) {
                const u = data.user;
                getEl('profileDisplayName').textContent = u.display_name;
                getEl('profileUsername').textContent = '@' + u.username;
                getEl('profileBio').textContent = u.bio || 'No bio yet';
                const avatar = getEl('profileAvatar');
                if (avatar) {
                    avatar.innerHTML = u.avatar_url
                        ? `<img src="${u.avatar_url}" class="profile-avatar">`
                        : `<div class="profile-avatar-placeholder">${u.username[0].toUpperCase()}</div>`;
                }
                getEl('profileDisplayNameValue').textContent = u.display_name;
                getEl('profileUsernameValue').textContent = '@' + u.username;
                getEl('profileBioValue').textContent = u.bio || 'No bio yet';
            }
        } catch (e) {}
    }

    window.openEditProfileModal = () => {
        const m = getEl('editProfileModal');
        if (!m) return;
        const dn = getEl('profileDisplayNameValue')?.textContent || window.currentUserDisplayName;
        const un = getEl('profileUsernameValue')?.textContent.replace('@', '') || window.currentUserUsername;
        const bio = getEl('profileBioValue')?.textContent || '';

        getEl('editDisplayName').value = dn;
        getEl('editUsername').value = un;
        const eb = getEl('editBio');
        eb.value = bio === 'No bio yet' ? '' : bio;
        const cc = getEl('bioCharCount');
        if (cc) { cc.textContent = eb.value.length; eb.addEventListener('input', () => cc.textContent = eb.value.length); }
        m.style.display = 'flex';
    };

    window.closeEditProfileModal = () => {
        const m = getEl('editProfileModal');
        if (m) m.style.display = 'none';
    };

    window.saveProfile = async () => {
        const dn = getEl('editDisplayName')?.value.trim() || '';
        const un = getEl('editUsername')?.value.trim() || '';
        const bio = getEl('editBio')?.value.trim() || '';

        if (!dn) { showToast('Display name required', 'error'); return; }
        if (!un || un.length < 3) { showToast('Username min 3 chars', 'error'); return; }
        if (!/^[a-zA-Z0-9_]+$/.test(un)) { showToast('Invalid username', 'error'); return; }

        try {
            const res = await fetch('/api/profile/update', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_name: dn, username: un, bio })
            });
            const data = await res.json();
            if (data.success) {
                window.currentUserDisplayName = dn;
                window.currentUserUsername = un;
                window.currentUserAvatar = un[0].toUpperCase();
                updateUI();
                closeEditProfileModal();
                loadProfileData();
                showToast('Profile updated!', 'success');
            } else {
                showToast(data.error || 'Failed', 'error');
            }
        } catch (e) {
            showToast('Error', 'error');
        }
    };

    window.triggerAvatarUpload = () => getEl('avatarInput')?.click();

    window.uploadAvatar = async (i) => {
        const f = i.files?.[0];
        if (!f) return;
        if (!hasFeature('videoAvatars') && f.type.startsWith('video/')) {
            showToast('Video avatars require Premium', 'error');
            return;
        }
        const fd = new FormData();
        fd.append('avatar', f);
        try {
            const res = await fetch('/files/upload_avatar', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) {
                showToast('Avatar updated!', 'success');
                window.currentUserAvatar = window.currentUserUsername[0].toUpperCase();
                updateUI();
                loadProfileData();
            }
        } catch (e) {}
    };

    // File Upload
    window.triggerFileUpload = () => getEl('fileInput')?.click();

    window.handleFileSelect = (i) => {
        const f = i.files;
        if (!f?.length) return;
        getEl('uploadFileName').textContent = f.length === 1 ? f[0].name : `${f.length} files`;
        getEl('uploadArea').classList.add('active');
    };

    window.uploadFile = async () => {
        const input = getEl('fileInput');
        const files = input?.files;
        if (!files?.length || !window.activeChat) { window.cancelUpload(); return; }

        for (const file of files) {
            const limit = hasFeature('largeUploads') ? 500*1024*1024 : 100*1024*1024;
            if (file.size > limit) { showToast(`File too large`, 'error'); continue; }

            const fd = new FormData();
            fd.append('file', file);
            if (window.activeChat.type === 'personal') fd.append('receiver_id', window.activeChat.id);
            else fd.append('group_id', window.activeChat.id);

            try {
                const res = await fetch('/files/upload_file', { method: 'POST', body: fd });
                const data = await res.json();
                if (data.success) {
                    const container = getEl('messagesContainer');
                    if (container) {
                        if (container.querySelector('.empty-state')) container.innerHTML = '';
                        container.insertAdjacentHTML('beforeend', renderMessage(data.message));
                        container.scrollTop = container.scrollHeight;
                    }
                }
            } catch (e) {}
        }
        window.cancelUpload();
    };

    window.cancelUpload = () => {
        getEl('uploadArea').classList.remove('active');
        getEl('fileInput').value = '';
    };

    // Chat Menu
    window.showChatInfo = () => {
        if (!window.activeChat) return;
        showToast('Chat info', 'info');
    };

    window.showChatMenu = () => {
        if (!window.activeChat) return;
        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.onclick = e => { if (e.target === m) m.remove(); };
        m.innerHTML = `
            <div class="chat-menu-dropdown" style="position:fixed;top:60px;right:20px;background:var(--bg-secondary);border-radius:12px;box-shadow:var(--shadow-lg);padding:8px 0;min-width:200px;z-index:2000">
                <div class="chat-menu-item" onclick="showChatInfo();this.closest('.modal-overlay').remove()"><span>ℹ️</span> View Info</div>
                <div class="chat-menu-item" onclick="openChatCustomization();this.closest('.modal-overlay').remove()"><span>🎨</span> Customize</div>
                ${hasFeature('chatStats') ? `<div class="chat-menu-item" onclick="showChatStats();this.closest('.modal-overlay').remove()"><span>📊</span> Statistics</div>` : ''}
                ${window.activeChat.type === 'personal' ? `
                    <div class="chat-menu-divider"></div>
                    <div class="chat-menu-item danger" onclick="blockUser(${window.activeChat.id});this.closest('.modal-overlay').remove()"><span>🚫</span> Block</div>
                    <div class="chat-menu-item danger" onclick="clearChat(${window.activeChat.id});this.closest('.modal-overlay').remove()"><span>🗑️</span> Clear</div>
                ` : ''}
            </div>
        `;
        document.body.appendChild(m);
    };

    window.blockUser = async (id) => {
        if (!confirm('Block this user?')) return;
        try {
            await fetch(`/api/block_user/${id}`, { method: 'POST' });
            showToast('User blocked', 'success');
            window.activeChat = null;
            getEl('emptyChat').style.display = 'flex';
            getEl('chatView').style.display = 'none';
            loadChatList();
        } catch (e) {}
    };

    window.clearChat = async (id) => {
        if (!confirm('Clear chat history?')) return;
        try {
            await fetch(`/api/clear_chat/${id}`, { method: 'POST' });
            showToast('Chat cleared', 'success');
            if (window.activeChat?.id === id) {
                getEl('messagesContainer').innerHTML = '<div class="empty-state"><p>No messages</p></div>';
            }
            loadChatList();
        } catch (e) {}
    };

    window.showChatStats = () => showToast('Chat statistics', 'info');

    window.showAddContactModal = () => {
        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.style.display = 'flex';
        m.onclick = e => { if (e.target === m) m.remove(); };
        m.innerHTML = `
            <div class="modal-container" style="max-width:400px">
                <div class="modal-header"><h3>Add Contact</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
                <div class="modal-body">
                    <input type="text" id="addContactSearch" class="modal-input" placeholder="Search username...">
                    <div id="addContactResults" style="max-height:300px;overflow-y:auto"></div>
                </div>
            </div>
        `;
        document.body.appendChild(m);
        const si = getEl('addContactSearch');
        if (si) {
            si.addEventListener('input', debounce(async () => {
                const q = si.value.trim();
                if (q.length < 2) return;
                try {
                    const res = await fetch(`/api/users?search=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    if (data.success) {
                        const results = getEl('addContactResults');
                        if (results) {
                            results.innerHTML = data.users.map(u => `
                                <div class="contact-item" onclick="openChat('personal',${u.id});closeAllModals()">
                                    <div class="contact-avatar">${u.username[0].toUpperCase()}</div>
                                    <div class="contact-info">
                                        <div class="contact-name">${escapeHtml(u.display_name)}</div>
                                        <div class="contact-username">@${escapeHtml(u.username)}</div>
                                    </div>
                                </div>
                            `).join('');
                        }
                    }
                } catch (e) {}
            }, 300));
            si.focus();
        }
    };

    window.closeAllModals = () => {
        document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
        const pm = getEl('profileModal');
        if (pm) pm.style.display = 'none';
        const em = getEl('editProfileModal');
        if (em) em.style.display = 'none';
    };

    // Settings
    window.openSettingsPanel = () => {
        getEl('settingsPanel')?.classList.add('open');
        getEl('panelOverlay')?.classList.add('visible');
        window.closePopout();
    };

    window.closeSettingsPanel = () => {
        getEl('settingsPanel')?.classList.remove('open');
        getEl('panelOverlay')?.classList.remove('visible');
    };

    window.openPrivacyPanel = () => {
        getEl('privacyPanel')?.classList.add('open');
        getEl('panelOverlay')?.classList.add('visible');
        window.closePopout();
    };

    window.closePrivacyPanel = () => {
        getEl('privacyPanel')?.classList.remove('open');
        getEl('panelOverlay')?.classList.remove('visible');
    };

    window.closeAllPanels = () => {
        getEl('settingsPanel')?.classList.remove('open');
        getEl('privacyPanel')?.classList.remove('open');
        getEl('panelOverlay')?.classList.remove('visible');
    };

    window.toggleSetting = (el, setting) => {
        el.classList.toggle('active');
        localStorage.setItem(`kiselgram_${setting}`, el.classList.contains('active'));
    };

    window.savePrivacySettings = () => {
        showToast('Saved', 'success');
        window.closePrivacyPanel();
    };

    // Misc
    window.showFollowers = () => showToast('Followers', 'info');
    window.showFollowing = () => showToast('Following', 'info');
    window.showGroups = () => showToast('Groups', 'info');
    window.toggleMobileSidebar = () => getEl('chatSidebar')?.classList.toggle('mobile-visible');
    window.logout = () => fetch('/api/auth/logout', { method: 'POST' }).then(() => location.href = '/login');

    window.triggerGroupAvatarUpload = () => getEl('groupAvatarInput')?.click();
    window.previewGroupAvatar = (i) => {
        if (i.files?.[0]) {
            const r = new FileReader();
            r.onload = e => { getEl('groupAvatarPreview').innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`; };
            r.readAsDataURL(i.files[0]);
        }
    };

    window.triggerChannelAvatarUpload = () => getEl('channelAvatarInput')?.click();
    window.previewChannelAvatar = (i) => {
        if (i.files?.[0]) {
            const r = new FileReader();
            r.onload = e => { getEl('channelAvatarPreview').innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`; };
            r.readAsDataURL(i.files[0]);
        }
    };

})();