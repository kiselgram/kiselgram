// static/js/free.js
// Kiselgram Free Edition - Complete

(function() {
    'use strict';

    console.log('🍊 Kiselgram Free v4.0.0');

    // State
    window.isPremium = false;
    window.currentUserId = null;
    window.currentUserUsername = '';
    window.currentUserDisplayName = '';
    window.currentUserAvatar = '?';
    window.activeChat = null;
    window.selectedMembers = [];
    window.replyToMessage = null;

    const FREE_FONTS = ['Inter', 'Courier New'];

    // DOM helper
    function getEl(id) { return document.getElementById(id); }

    // Initialize
    document.addEventListener('DOMContentLoaded', async () => {
        await loadCurrentUser();
        await loadChatList();
        setupEventListeners();
        loadThemePreference();
        loadFontPreference();
        renderStoriesRowLocked();

        const urlParams = new URLSearchParams(window.location.search);
        const chatId = urlParams.get('chat');
        if (chatId) setTimeout(() => openChat('personal', parseInt(chatId)), 500);

        setInterval(loadChatList, 30000);
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
        if (name) name.textContent = window.currentUserDisplayName;
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

    function renderStoriesRowLocked() {
        const row = getEl('storiesRow');
        if (!row) return;
        row.innerHTML = `
            <div class="story-item locked" onclick="showPremiumModal('stories')">
                <div class="story-avatar add-story locked"><div class="add-story-btn">🔒</div></div>
                <span class="story-username">Premium</span>
            </div>
        `;
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

    // Premium Modal
    window.showPremiumModal = (feature = 'feature') => {
        const msgs = {
            fonts: 'Unlock 9+ premium fonts!',
            stories: 'Stories - Premium only!',
            wallpapers: 'Custom wallpapers - Premium only!',
        };

        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.style.display = 'flex';
        m.onclick = e => { if (e.target === m) m.remove(); };
        m.innerHTML = `
            <div class="modal-container" style="max-width:400px">
                <div class="modal-header" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white">
                    <h3>✨ Kiselgram Premium</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color:white">✕</button>
                </div>
                <div class="modal-body" style="text-align:center;padding:24px">
                    <div style="font-size:48px;margin-bottom:16px">👑</div>
                    <p style="font-size:16px;margin-bottom:20px">${msgs[feature] || 'Unlock all premium features!'}</p>
                    <div style="background:linear-gradient(135deg,rgba(251,99,64,0.1),rgba(45,206,137,0.1));border-radius:16px;padding:16px;margin-bottom:20px">
                        <h4>Premium Benefits:</h4>
                        <ul style="text-align:left;color:var(--text-secondary)">
                            <li>✨ 11 Premium Fonts</li>
                            <li>📸 Stories Feature</li>
                            <li>🎨 Custom Chat Wallpapers</li>
                            <li>💬 Priority Support</li>
                        </ul>
                    </div>
                    <div style="display:flex;justify-content:center;gap:20px;margin-bottom:20px">
                        <div style="text-align:center">
                            <div style="font-size:28px;font-weight:700;background:linear-gradient(135deg,#fb6340,#2dce89);-webkit-background-clip:text;-webkit-text-fill-color:transparent">$3.99</div>
                            <div style="font-size:12px;color:var(--text-muted)">per month</div>
                        </div>
                        <div style="text-align:center">
                            <div style="font-size:28px;font-weight:700;background:linear-gradient(135deg,#fb6340,#2dce89);-webkit-background-clip:text;-webkit-text-fill-color:transparent">$39.99</div>
                            <div style="font-size:12px;color:var(--text-muted)">per year</div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-secondary" onclick="this.closest('.modal-overlay').remove()">Maybe Later</button>
                    <button class="modal-btn modal-btn-primary" onclick="location.href='/premium'" style="background:linear-gradient(135deg,#fb6340,#2dce89)">Upgrade Now</button>
                </div>
            </div>
        `;
        document.body.appendChild(m);
    };

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
        const name = el.querySelector('.font-name')?.textContent.split(' ')[0];
        if (!FREE_FONTS.includes(name)) {
            showToast('🔒 Premium font', 'error');
            showPremiumModal('fonts');
            return;
        }
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
                    <div class="chat-avatar ${c.type}">${avatar}</div>
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

        if (type === 'personal') await fetch(`/api/mark_read/${id}`, { method: 'POST' });
        getEl('messageInput')?.focus();
    };

    async function loadChatInfo(type, id) {
        const headerName = getEl('chatHeaderName');
        const headerAvatar = getEl('chatHeaderAvatar');
        if (type === 'personal') {
            try {
                const res = await fetch('/api/users');
                const data = await res.json();
                const user = data.users?.find(u => u.id === id);
                if (user) {
                    if (headerName) headerName.textContent = user.display_name || user.username;
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
        const content = m.content || '';
        return `
            <div class="message-wrapper ${isOwn ? 'outgoing' : 'incoming'}" id="msg-${m.id}">
                ${!isOwn ? `<div class="message-sender">${escapeHtml(m.sender_name||'User')}</div>` : ''}
                <div class="message-bubble">
                    ${att}
                    ${content ? `<div class="message-text">${escapeHtml(content).replace(/\n/g,'<br>')}</div>` : ''}
                    <div class="message-meta">
                        <span class="message-time">${m.timestamp_formatted||''}</span>
                        ${isOwn ? `<span class="message-status">${m.is_read?'✓✓':'✓'}</span>` : ''}
                    </div>
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
            }
        } catch (e) {}
    }

    window.triggerAvatarUpload = () => getEl('avatarInput')?.click();

    window.uploadAvatar = async (input) => {
        const file = input.files?.[0];
        if (!file) return;
        const fd = new FormData();
        fd.append('avatar', file);
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

    window.handleFileSelect = (input) => {
        const files = input.files;
        if (!files?.length) return;
        getEl('uploadFileName').textContent = files.length === 1 ? files[0].name : `${files.length} files`;
        getEl('uploadArea').classList.add('active');
    };

    window.uploadFile = async () => {
        const input = getEl('fileInput');
        const files = input?.files;
        if (!files?.length || !window.activeChat) { window.cancelUpload(); return; }

        for (const file of files) {
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
    window.showChatInfo = () => showToast('Chat info', 'info');

    window.showChatMenu = () => {
        if (!window.activeChat) return;
        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.onclick = e => { if (e.target === m) m.remove(); };
        m.innerHTML = `
            <div class="chat-menu-dropdown" style="position:fixed;top:60px;right:20px;background:var(--bg-secondary);border-radius:12px;box-shadow:var(--shadow-lg);padding:8px 0;min-width:200px;z-index:2000">
                <div class="chat-menu-item" onclick="showChatInfo();this.closest('.modal-overlay').remove()"><span>ℹ️</span> View Info</div>
                <div class="chat-menu-item locked" onclick="showPremiumModal('wallpapers');this.closest('.modal-overlay').remove()"><span>🎨</span> Customize 🔒</div>
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

    window.showAddContactModal = () => showToast('Add contact', 'info');

    // Settings
    window.openSettingsPanel = () => {
        getEl('settingsPanel')?.classList.add('open');
        getEl('panelOverlay')?.classList.add('visible');
    };

    window.closeSettingsPanel = () => {
        getEl('settingsPanel')?.classList.remove('open');
        getEl('panelOverlay')?.classList.remove('visible');
    };

    window.openPrivacyPanel = () => {
        getEl('privacyPanel')?.classList.add('open');
        getEl('panelOverlay')?.classList.add('visible');
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

    window.openChatCustomization = () => showPremiumModal('wallpapers');

})();