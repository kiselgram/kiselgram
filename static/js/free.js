// static/js/free.js
// Kiselgram Free Edition – Offline, Push, Caching, Onboarding, Skeletons
// Version 4.1.0

(function() {
    'use strict';

    console.log('🍊 Kiselgram Free v4.1.0');

    // ========== GLOBALS ==========
    window.isPremium = false;
    window.currentUserId = null;
    window.currentUserUsername = '';
    window.currentUserDisplayName = '';
    window.currentUserAvatar = '?';

    window.activeChat = null;
    window.selectedMembers = [];
    window.replyToMessage = null;

    const FREE_FONTS = ['Inter', 'Courier New'];

    const cachedMessages = new Map();
    function getMessagesHash(msgs) {
        return msgs.map(m => `${m.id}:${m.content}:${m.is_read}`).join('|');
    }

    let offlineQueue = [];
    let isOnline = navigator.onLine;

    // DOM references
    function getEl(id) { return document.getElementById(id); }
    const DOM = {
        get emptyChat() { return getEl('emptyChat'); },
        get chatView() { return getEl('chatView'); },
        get contactsView() { return getEl('contactsView'); },
        get createGroupView() { return getEl('createGroupView'); },
        get createChannelView() { return getEl('createChannelView'); },
        get chatList() { return getEl('chatList'); },
        get messagesContainer() { return getEl('messagesContainer'); },
        get messageInput() { return getEl('messageInput'); },
        get sendBtn() { return getEl('sendBtn'); },
        get modalRoot() { return getEl('modalRoot'); },
        get searchResults() { return getEl('searchResults'); },
        get globalSearchInput() { return getEl('globalSearchInput'); },
        get replyPreview() { return getEl('replyPreview'); },
        get chatHeaderName() { return getEl('chatHeaderName'); },
        get chatHeaderAvatar() { return getEl('chatHeaderAvatar'); },
        get chatHeaderStatus() { return getEl('chatHeaderStatus'); }
    };

    // ========== UTILITIES ==========
    function debounce(fn, wait) { let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); }; }
    function escapeHtml(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

    function showToast(msg, type='info') {
        const toast = document.createElement('div');
        toast.textContent = msg;
        toast.style.cssText = `position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:${type==='success'?'#2dce89':type==='error'?'#fb6340':'#5e72e4'};color:white;padding:12px 24px;border-radius:30px;font-weight:500;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
    window.showToast = showToast;

    // ========== PUSH NOTIFICATIONS ==========
    async function subscribeToPush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
        try {
            const registration = await navigator.serviceWorker.ready;
            let subscription = await registration.pushManager.getSubscription();
            if (!subscription) {
                const vapidPublicKey = 'YOUR_VAPID_PUBLIC_KEY';
                subscription = await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
                });
            }
            await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription })
            });
        } catch (e) {}
    }

    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
        return outputArray;
    }

    // ========== OFFLINE SYNC ==========
    async function syncOfflineMessages() {
        if (offlineQueue.length === 0) return;
        const toSync = [...offlineQueue];
        offlineQueue = [];
        try {
            const res = await fetch('/api/sync_messages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: toSync })
            });
            const data = await res.json();
            if (data.success) {
                data.synced.forEach(item => {
                    const tempEl = document.getElementById(`temp-msg-${item.temp_id}`);
                    if (tempEl) tempEl.outerHTML = renderMessage(item.message);
                });
                loadChatList();
            }
        } catch (e) {
            offlineQueue.push(...toSync);
        }
    }

    window.addEventListener('online', () => { isOnline = true; syncOfflineMessages(); });
    window.addEventListener('offline', () => { isOnline = false; });

    // ========== INIT ==========
    document.addEventListener('DOMContentLoaded', async () => {
        if ('serviceWorker' in navigator) {
            try { await navigator.serviceWorker.register('/sw.js'); } catch (e) {}
        }

        await loadCurrentUser();
        await loadChatList();
        setupEventListeners();
        loadThemePreference();
        loadFontPreference();
        renderStoriesRowLocked();

        if (window.currentUserId && !localStorage.getItem('profile_completed')) {
            setTimeout(() => showProfileCompletionPrompt(), 1000);
        }

        if (Notification.permission === 'default') {
            Notification.requestPermission().then(p => { if (p === 'granted') subscribeToPush(); });
        } else if (Notification.permission === 'granted') {
            subscribeToPush();
        }

        const urlParams = new URLSearchParams(window.location.search);
        const chatId = urlParams.get('chat');
        if (chatId) setTimeout(() => openChat('personal', parseInt(chatId)), 500);

        setInterval(loadChatList, 30000);
        setInterval(() => { if (window.activeChat) loadMessages(window.activeChat.type, window.activeChat.id); }, 5000);
    });

    function showProfileCompletionPrompt() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="modal-container">
                <div class="modal-header"><h3>Complete Your Profile</h3></div>
                <div class="modal-body">
                    <p>Add a display name and bio to help friends recognise you.</p>
                    <input type="text" id="onboardDisplayName" class="modal-input" placeholder="Display name" value="${window.currentUserDisplayName}">
                    <textarea id="onboardBio" class="modal-input" placeholder="Bio" rows="3"></textarea>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-secondary" onclick="this.closest('.modal-overlay').remove()">Skip</button>
                    <button class="modal-btn modal-btn-primary" id="saveOnboarding">Save</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        document.getElementById('saveOnboarding').onclick = async () => {
            const dn = document.getElementById('onboardDisplayName').value.trim();
            const bio = document.getElementById('onboardBio').value.trim();
            if (dn) {
                await fetch('/api/profile/update', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ display_name: dn, bio })
                });
                localStorage.setItem('profile_completed', 'true');
                modal.remove();
                showToast('Profile updated!', 'success');
                loadCurrentUser();
            }
        };
    }

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
                if (data.user.display_name && data.user.bio) {
                    localStorage.setItem('profile_completed', 'true');
                }
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

    function setupEventListeners() {
        getEl('menuBtn')?.addEventListener('click', togglePopoutMenu);
        DOM.globalSearchInput?.addEventListener('input', debounce(handleGlobalSearch, 300));
        DOM.globalSearchInput?.addEventListener('focus', () => DOM.searchResults?.classList.add('active'));
        if (DOM.messageInput) {
            DOM.messageInput.addEventListener('input', handleMessageInput);
            DOM.messageInput.addEventListener('keydown', handleMessageKeydown);
        }
        document.addEventListener('click', (e) => {
            const sc = document.querySelector('.global-search');
            if (sc && !sc.contains(e.target)) DOM.searchResults?.classList.remove('active');
        });
    }

    function handleMessageInput() {
        if (DOM.messageInput && DOM.sendBtn) DOM.sendBtn.disabled = !DOM.messageInput.value.trim();
        if (DOM.messageInput) {
            DOM.messageInput.style.height = 'auto';
            DOM.messageInput.style.height = Math.min(DOM.messageInput.scrollHeight, 100) + 'px';
        }
    }

    async function handleMessageKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            await sendMessage();
        }
    }

    // ========== CHAT LIST WITH CACHE & SKELETON ==========
    async function loadChatList() {
        try {
            const cached = localStorage.getItem('kiselgram_chatlist');
            if (cached) {
                renderChatList(JSON.parse(cached));
            } else {
                if (DOM.chatList) DOM.chatList.innerHTML = Array(6).fill(0).map(() => `
                    <div class="chat-item skeleton-item">
                        <div class="skeleton skeleton-avatar"></div>
                        <div class="skeleton skeleton-text"></div>
                    </div>
                `).join('');
            }
            const r = await fetch('/api/chat_list');
            const d = await r.json();
            if (d.success) {
                localStorage.setItem('kiselgram_chatlist', JSON.stringify(d.chats));
                renderChatList(d.chats);
            }
        } catch (e) {}
    }

    function renderChatList(chats) {
        const c = DOM.chatList;
        if (!c) return;
        if (!chats?.length) {
            c.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No chats</p></div>';
            return;
        }
        c.innerHTML = chats.map(chat => {
            const active = window.activeChat?.type===chat.type && window.activeChat?.id===chat.id;
            return `<div class="chat-item ${active?'active':''}" data-chat-type="${chat.type}" data-chat-id="${chat.id}" onclick="openChat('${chat.type}',${chat.id})">
                <div class="chat-avatar ${chat.type}">${chat.avatar_url?`<img src="${chat.avatar_url}">`:(chat.avatar||'?')}</div>
                <div class="chat-info">
                    <div class="chat-name-row"><span class="chat-name">${escapeHtml(chat.name)}</span><span class="chat-time">${chat.timestamp||''}</span></div>
                    <div class="chat-preview"><span>${escapeHtml(chat.last_message||'')}</span>${chat.unread_count>0?`<span class="unread-badge">${chat.unread_count}</span>`:''}</div>
                </div>
            </div>`;
        }).join('');
    }

    // ========== MESSAGES ==========
    async function loadMessages(type, id, forceRender = false) {
        const container = DOM.messagesContainer;
        if (!container) return;
        if (forceRender) container.innerHTML = '<div class="loading-spinner"></div>';
        try {
            let url;
            if (type === 'personal') url = `/api/messages/${id}`;
            else if (type === 'group') url = `/api/group_messages/${id}`;
            else if (type === 'channel') url = `/api/channel_messages/${id}`;
            else return;
            const res = await fetch(`${url}?after=0&limit=50`);
            const data = await res.json();
            const msgs = data.messages || (data.success && data.messages) || [];
            const newHash = getMessagesHash(msgs);
            const cacheKey = `${type}_${id}`;
            const oldHash = cachedMessages.get(cacheKey) || '';
            if (forceRender || newHash !== oldHash) {
                cachedMessages.set(cacheKey, newHash);
                await renderMessages(msgs);
                applyWallpaper();
            }
        } catch (e) {
            if (forceRender) container.innerHTML = '<div class="empty-state"><p>Error</p></div>';
        }
    }

    async function renderMessages(msgs) {
        const c = DOM.messagesContainer;
        if (!c) return;
        let h = '', ld = null;
        for (const m of msgs) {
            const md = new Date(m.timestamp||Date.now());
            const ds = md.toLocaleDateString();
            if (ds !== ld) {
                const t = new Date(), y = new Date(t); y.setDate(y.getDate()-1);
                let dt = '';
                if (md.toDateString()===t.toDateString()) dt='Today';
                else if (md.toDateString()===y.toDateString()) dt='Yesterday';
                else dt=md.toLocaleDateString(undefined,{month:'long',day:'numeric'});
                h += `<div class="message-date-divider">${dt}</div>`;
                ld = ds;
            }
            h += renderMessage(m);
        }
        c.innerHTML = h || '<div class="empty-state"><p>No messages</p></div>';
        c.scrollTop = c.scrollHeight;
    }

    function renderMessage(m) {
        const isOwn = m.is_own || m.sender_id === window.currentUserId;
        let att = '';
        if (m.has_attachment) {
            if (m.file_type==='image') att = `<img src="${m.file_url}" class="message-image" onclick="openImageViewer('${m.file_url}')">`;
            else att = `<div class="file-attachment"><span>📎</span><a href="${m.file_url}" target="_blank">${m.file_name||'File'}</a></div>`;
        }
        let reply = '';
        if (m.reply_to_id) reply = `<div class="reply-indicator"><span>↩️ Reply</span><div style="font-size:11px">${escapeHtml(m.reply_to_content||'')}</div></div>`;
        const content = m.content||'';
        return `<div class="message-wrapper ${isOwn?'outgoing':'incoming'}" id="msg-${m.id}">
            ${!isOwn?`<div class="message-sender">${escapeHtml(m.sender_name||'User')}</div>`:''}
            <div class="message-bubble">
                ${reply}${att}${content?`<div class="message-text">${escapeHtml(content).replace(/\n/g,'<br>')}</div>`:''}
                <div class="message-meta"><span class="message-time">${m.timestamp_formatted||''}</span>${isOwn?`<span>${m.is_read?'✓✓':'✓'}</span>`:''}</div>
            </div>
        </div>`;
    }

    function applyWallpaper() {}

    // ========== SEND MESSAGE (offline queue) ==========
    async function sendMessage() {
        const content = DOM.messageInput?.value.trim();
        if (!content || !window.activeChat) return;

        const payload = { content };
        let url;
        if (window.activeChat.type === 'personal') {
            url = '/api/send_message';
            payload.receiver_id = window.activeChat.id;
        } else if (window.activeChat.type === 'group') {
            url = '/api/send_group_message';
            payload.group_id = window.activeChat.id;
        } else if (window.activeChat.type === 'channel') {
            url = '/api/send_channel_message';
            payload.channel_id = window.activeChat.id;
        }

        if (window.replyToMessage) {
            payload.reply_to_id = window.replyToMessage;
            window.replyToMessage = null;
            if (DOM.replyPreview) DOM.replyPreview.style.display = 'none';
        }

        const tempId = 'temp_' + Date.now() + Math.random();
        const optimisticMsg = {
            id: tempId,
            content: content,
            sender_id: window.currentUserId,
            sender_name: window.currentUserDisplayName,
            timestamp: new Date().toISOString(),
            timestamp_formatted: new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),
            is_own: true,
            is_read: false,
            has_attachment: false,
            reactions: {}
        };
        const container = DOM.messagesContainer;
        if (container) {
            if (container.querySelector('.empty-state')) container.innerHTML = '';
            container.insertAdjacentHTML('beforeend', renderMessage(optimisticMsg));
            container.scrollTop = container.scrollHeight;
        }
        DOM.messageInput.value = '';
        handleMessageInput();

        if (!isOnline) {
            offlineQueue.push({
                ...payload,
                temp_id: tempId,
                target_type: window.activeChat.type,
                target_id: window.activeChat.id
            });
            showToast('Message queued for offline', 'info');
            return;
        }

        try {
            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await r.json();
            if (d.success && d.message) {
                const tempEl = document.getElementById(`msg-${tempId}`);
                if (tempEl) tempEl.outerHTML = renderMessage(d.message);
                loadChatList();
            } else {
                document.getElementById(`msg-${tempId}`)?.remove();
                showToast('Failed to send', 'error');
            }
        } catch (e) {
            document.getElementById(`msg-${tempId}`)?.remove();
            offlineQueue.push({...payload, temp_id: tempId, target_type: window.activeChat.type, target_id: window.activeChat.id});
            showToast('Offline – message queued', 'info');
        }
    }

    // ========== OPEN CHAT ==========
    window.openChat = async (type, id) => {
        window.activeChat = { type, id };
        document.querySelectorAll('.chat-item').forEach(i => i.classList.remove('active'));
        document.querySelector(`.chat-item[data-chat-type="${type}"][data-chat-id="${id}"]`)?.classList.add('active');
        hideAllPanels();
        if (DOM.chatView) DOM.chatView.style.display = 'flex';
        await loadChatInfo(type, id);
        await loadMessages(type, id, true);
        if (type === 'personal') await fetch(`/api/mark_read/${id}`, { method:'POST' });
        DOM.messageInput?.focus();
    };

    async function loadChatInfo(type, id) {
        if (type === 'personal') {
            try {
                const r = await fetch('/api/users');
                const d = await r.json();
                const u = d.users?.find(u => u.id===id);
                if (u) {
                    if (DOM.chatHeaderName) DOM.chatHeaderName.textContent = u.display_name||u.username;
                    if (DOM.chatHeaderStatus) {
                        DOM.chatHeaderStatus.textContent = u.is_online?'Online':'Offline';
                        DOM.chatHeaderStatus.classList.toggle('online', u.is_online);
                    }
                    if (DOM.chatHeaderAvatar) {
                        DOM.chatHeaderAvatar.textContent = u.username[0].toUpperCase();
                        DOM.chatHeaderAvatar.className = 'chat-header-avatar personal';
                    }
                }
            } catch (e) {}
        } else {
            if (DOM.chatHeaderName) DOM.chatHeaderName.textContent = type==='group'?'Group':'Channel';
            if (DOM.chatHeaderAvatar) {
                DOM.chatHeaderAvatar.textContent = type==='group'?'👥':'📢';
                DOM.chatHeaderAvatar.className = `chat-header-avatar ${type}`;
            }
        }
    }

    function hideAllPanels() {
        [DOM.emptyChat, DOM.chatView, DOM.contactsView, DOM.createGroupView, DOM.createChannelView].forEach(el => { if (el) el.style.display = 'none'; });
    }

    // ========== SETTINGS / THEME / FONT ==========
    function togglePopoutMenu() { document.body.classList.toggle('popout-open'); getEl('menuBtn')?.classList.toggle('active'); }
    window.closePopout = () => { document.body.classList.remove('popout-open'); getEl('menuBtn')?.classList.remove('active'); };
    window.closeAllPanels = () => { getEl('settingsPanel')?.classList.remove('open'); getEl('privacyPanel')?.classList.remove('open'); getEl('panelOverlay')?.classList.remove('visible'); };
    window.openSettingsPanel = () => { window.closeAllPanels(); getEl('settingsPanel')?.classList.add('open'); getEl('panelOverlay')?.classList.add('visible'); window.closePopout(); };
    window.closeSettingsPanel = () => { getEl('settingsPanel')?.classList.remove('open'); getEl('panelOverlay')?.classList.remove('visible'); };
    window.openPrivacyPanel = () => { window.closeAllPanels(); getEl('privacyPanel')?.classList.add('open'); getEl('panelOverlay')?.classList.add('visible'); window.closePopout(); };
    window.closePrivacyPanel = () => { getEl('privacyPanel')?.classList.remove('open'); getEl('panelOverlay')?.classList.remove('visible'); };

    window.setTheme = (theme) => {
        document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('active'));
        if (event?.currentTarget) event.currentTarget.classList.add('active');
        if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
        else if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
        else document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('kiselgram_theme', theme);
    };
    function loadThemePreference() { const t = localStorage.getItem('kiselgram_theme'); if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark'); else if (t === 'light') document.documentElement.setAttribute('data-theme', 'light'); }
    window.setFont = (el) => { const name = el.querySelector('.font-name')?.textContent.split(' ')[0]; if (!FREE_FONTS.includes(name)) { showToast('🔒 Premium font', 'error'); showPremiumModal('fonts'); return; } document.querySelectorAll('.font-option').forEach(o => o.classList.remove('active')); el.classList.add('active'); document.body.style.setProperty('--font-family', el.dataset.font); localStorage.setItem('kiselgram_font', el.dataset.font); showToast('Font updated', 'success'); };
    function loadFontPreference() { const f = localStorage.getItem('kiselgram_font'); if (f) document.body.style.setProperty('--font-family', f); }

    // ========== PREMIUM MODAL ==========
    window.showPremiumModal = (feature='feature') => {
        const msgs = { fonts: 'Unlock 9+ premium fonts!', stories: 'Stories disappear after 24h - Premium only!', wallpapers: 'Custom wallpapers - Premium only!' };
        const m = document.createElement('div');
        m.className = 'modal-overlay';
        m.style.display = 'flex';
        m.onclick = e => { if (e.target===m) m.remove(); };
        m.innerHTML = `
            <div class="modal-container" style="max-width:450px">
                <div class="modal-header" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white">
                    <h3>✨ Kiselgram Premium</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color:white">✕</button>
                </div>
                <div class="modal-body" style="text-align:center;padding:24px">
                    <div style="font-size:48px;margin-bottom:16px">👑</div>
                    <p>${msgs[feature]||'Unlock all premium features!'}</p>
                    <button class="modal-btn modal-btn-primary" onclick="location.href='/premium'" style="margin-top:20px;background:linear-gradient(135deg,#fb6340,#2dce89)">Upgrade Now</button>
                </div>
            </div>
        `;
        document.body.appendChild(m);
    };

    // ========== REPLY / FORWARD / REACTIONS ==========
    window.setReply = (id) => { window.replyToMessage = id; const msg = getEl(`msg-${id}`); if (msg && DOM.replyPreview) { const t = msg.querySelector('.message-text')?.textContent||''; DOM.replyPreview.querySelector('.reply-preview-name').textContent = 'Replying'; DOM.replyPreview.querySelector('.reply-preview-text').textContent = t.substring(0,50); DOM.replyPreview.style.display = 'flex'; } };
    window.cancelReply = () => { window.replyToMessage = null; if (DOM.replyPreview) DOM.replyPreview.style.display = 'none'; };
    window.deleteMessage = async (id) => { if (!confirm('Delete?')) return; try { await fetch(`/api/messages/${id}`, { method:'DELETE' }); getEl(`msg-${id}`)?.remove(); } catch (e) {} };
    window.openImageViewer = (url) => window.open(url, '_blank');

    // ========== CONTACTS ==========
    window.showContactsView = () => { window.closePopout(); hideAllPanels(); if (DOM.contactsView) DOM.contactsView.style.display = 'flex'; loadContacts(); };
    window.hideContactsView = () => { if (DOM.contactsView) DOM.contactsView.style.display = 'none'; if (window.activeChat) { if (DOM.chatView) DOM.chatView.style.display = 'flex'; } else { if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; } };
    async function loadContacts() { const c = getEl('contactsList'); if (!c) return; try { const r = await fetch('/api/contacts'); const d = await r.json(); if (d.success) { c.innerHTML = d.contacts.map(u => `<div class="contact-item" onclick="openChat('personal',${u.id})"><div class="contact-avatar">${u.username[0].toUpperCase()}</div><div class="contact-info"><div class="contact-name">${escapeHtml(u.display_name)}</div><div class="contact-username">@${escapeHtml(u.username)}</div></div></div>`).join('') || '<div class="empty-state"><p>No contacts</p></div>'; } } catch (e) {} }

    // ========== GLOBAL SEARCH ==========
    async function handleGlobalSearch() { const q = DOM.globalSearchInput?.value.trim(); const r = DOM.searchResults; if (!r) return; if (!q||q.length<2) { r.innerHTML = ''; r.classList.remove('active'); return; } try { const res = await fetch(`/api/search/global?q=${encodeURIComponent(q)}`); const d = await res.json(); if (d.success) { let h = ''; if (d.results.users?.length) { h += '<div class="search-result-section">Users</div>'; d.results.users.forEach(u => { h += `<div class="search-result-item" onclick="openChat('personal',${u.id});closeSearchResults()"><div class="search-result-avatar">${u.username[0].toUpperCase()}</div><div class="search-result-info"><div class="search-result-name">${escapeHtml(u.display_name)}</div><div class="search-result-type">@${escapeHtml(u.username)}</div></div></div>`; }); } if (d.results.groups?.length) { h += '<div class="search-result-section">Groups</div>'; d.results.groups.forEach(g => { h += `<div class="search-result-item" onclick="openChat('group',${g.id});closeSearchResults()"><div class="search-result-avatar">👥</div><div class="search-result-info"><div class="search-result-name">${escapeHtml(g.name)}</div><div class="search-result-type">Group</div></div></div>`; }); } r.innerHTML = h || '<div class="search-result-item">No results</div>'; r.classList.add('active'); } } catch (e) {} }
    window.closeSearchResults = () => { DOM.searchResults?.classList.remove('active'); if (DOM.globalSearchInput) DOM.globalSearchInput.value = ''; };

    // ========== CREATE GROUP ==========
    window.showCreateGroupView = () => { window.closePopout(); hideAllPanels(); if (DOM.createGroupView) DOM.createGroupView.style.display = 'flex'; window.selectedMembers = []; const c = getEl('selectedMembers'); if (c) c.innerHTML = ''; };
    window.hideCreateGroupView = () => { if (DOM.createGroupView) DOM.createGroupView.style.display = 'none'; if (window.activeChat) { if (DOM.chatView) DOM.chatView.style.display = 'flex'; } else { if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; } };
    window.createGroup = async () => { const n = getEl('groupName')?.value.trim(); if (!n) { showToast('Enter name', 'error'); return; } const fd = new FormData(); fd.append('name', n); fd.append('member_ids', JSON.stringify(window.selectedMembers||[])); const a = getEl('groupAvatarInput'); if (a?.files[0]) fd.append('avatar', a.files[0]); try { const r = await fetch('/api/groups/create', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { showToast('Created!', 'success'); window.hideCreateGroupView(); loadChatList(); openChat('group', d.group.id); } } catch (e) {} };

    // ========== CREATE CHANNEL ==========
    window.showCreateChannelView = () => { window.closePopout(); hideAllPanels(); if (DOM.createChannelView) DOM.createChannelView.style.display = 'flex'; };
    window.hideCreateChannelView = () => { if (DOM.createChannelView) DOM.createChannelView.style.display = 'none'; if (window.activeChat) { if (DOM.chatView) DOM.chatView.style.display = 'flex'; } else { if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; } };
    window.createChannel = async () => { const n = getEl('channelName')?.value.trim(); if (!n) { showToast('Enter name', 'error'); return; } const fd = new FormData(); fd.append('name', n); const a = getEl('channelAvatarInput'); if (a?.files[0]) fd.append('avatar', a.files[0]); try { const r = await fetch('/api/channels/create', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { showToast('Created!', 'success'); window.hideCreateChannelView(); loadChatList(); openChat('channel', d.channel.id); } } catch (e) {} };

    // ========== PROFILE ==========
    window.openProfileModal = () => { const m = getEl('profileModal'); if (m) m.style.display = 'flex'; loadProfileData(); };
    window.closeProfileModal = () => { const m = getEl('profileModal'); if (m) m.style.display = 'none'; };
    async function loadProfileData() { try { const r = await fetch('/api/profile'); const d = await r.json(); if (d.success && d.user) { const u = d.user; const dn = getEl('profileDisplayName'), un = getEl('profileUsername'), av = getEl('profileAvatar'), bio = getEl('profileBio'); if (dn) dn.textContent = u.display_name; if (un) un.textContent = '@'+u.username; if (bio) bio.textContent = u.bio||'No bio yet'; if (av) av.innerHTML = u.avatar_url ? `<img src="${u.avatar_url}" class="profile-avatar">` : `<div class="profile-avatar-placeholder">${u.username[0].toUpperCase()}</div>`; } } catch (e) {} }
    window.openEditProfileModal = () => { const m = getEl('editProfileModal'); if (!m) return; const dn = window.currentUserDisplayName; const un = window.currentUserUsername; const bio = getEl('profileBio')?.textContent || ''; const ed = getEl('editDisplayName'), eu = getEl('editUsername'), eb = getEl('editBio'), cc = getEl('bioCharCount'); if (ed) ed.value = dn; if (eu) eu.value = un; if (eb) { eb.value = bio==='No bio yet'?'':bio; if (cc) { cc.textContent = eb.value.length; eb.addEventListener('input', () => cc.textContent = eb.value.length); } } m.style.display = 'flex'; };
    window.closeEditProfileModal = () => { const m = getEl('editProfileModal'); if (m) m.style.display = 'none'; };
    window.saveProfile = async () => { const dn = getEl('editDisplayName')?.value.trim()||''; const un = getEl('editUsername')?.value.trim()||''; const bio = getEl('editBio')?.value.trim()||''; if (!dn) { showToast('Display name required', 'error'); return; } if (!un || un.length<3) { showToast('Username min 3 chars', 'error'); return; } if (!/^[a-zA-Z0-9_]+$/.test(un)) { showToast('Invalid username', 'error'); return; } try { const r = await fetch('/api/profile/update', { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({display_name:dn, username:un, bio}) }); const d = await r.json(); if (d.success) { window.currentUserDisplayName = dn; window.currentUserUsername = un; window.currentUserAvatar = un[0].toUpperCase(); updateUI(); closeEditProfileModal(); loadProfileData(); showToast('Profile updated!', 'success'); } else { showToast(d.error||'Failed', 'error'); } } catch (e) { showToast('Error', 'error'); } };
    window.triggerAvatarUpload = () => getEl('avatarInput')?.click();
    window.uploadAvatar = async (i) => { const f = i.files?.[0]; if (!f) return; const fd = new FormData(); fd.append('avatar', f); try { const r = await fetch('/files/upload_avatar', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { showToast('Avatar updated!', 'success'); window.currentUserAvatar = window.currentUserUsername[0].toUpperCase(); updateUI(); loadProfileData(); } } catch (e) {} };

    // ========== FILE UPLOAD ==========
    window.triggerFileUpload = () => getEl('fileInput')?.click();
    window.handleFileSelect = (i) => { const f = i.files; if (!f?.length) return; const fn = getEl('uploadFileName'); const ua = getEl('uploadArea'); if (fn) fn.textContent = f.length===1 ? f[0].name : `${f.length} files`; if (ua) ua.classList.add('active'); };
    window.uploadFile = async () => { const i = getEl('fileInput'); const f = i?.files; if (!f?.length || !window.activeChat) { window.cancelUpload(); return; } for (const file of f) { const fd = new FormData(); fd.append('file', file); if (window.activeChat.type==='personal') fd.append('receiver_id', window.activeChat.id); else fd.append('group_id', window.activeChat.id); try { const r = await fetch('/files/upload_file', { method:'POST', body:fd }); const d = await r.json(); if (d.success && DOM.messagesContainer) { if (DOM.messagesContainer.querySelector('.empty-state')) DOM.messagesContainer.innerHTML = ''; DOM.messagesContainer.insertAdjacentHTML('beforeend', renderMessage(d.message)); DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight; } } catch (e) {} } window.cancelUpload(); };
    window.cancelUpload = () => { const ua = getEl('uploadArea'); const fi = getEl('fileInput'); if (ua) ua.classList.remove('active'); if (fi) fi.value = ''; };

    // ========== CHAT MENU ==========
    window.showChatInfo = () => showToast('Chat info', 'info');
    window.showChatMenu = () => { if (!window.activeChat) return; const m = document.createElement('div'); m.className = 'modal-overlay'; m.onclick = e => { if (e.target===m) m.remove(); }; m.innerHTML = `<div class="chat-menu-dropdown" style="position:fixed;top:60px;right:20px;background:var(--bg-secondary);border-radius:12px;box-shadow:var(--shadow-lg);padding:8px 0;min-width:200px;z-index:2000"><div class="chat-menu-item" onclick="showChatInfo();this.closest('.modal-overlay').remove()"><span>ℹ️</span> View Info</div>${window.activeChat.type==='personal'?`<div class="chat-menu-divider"></div><div class="chat-menu-item danger" onclick="blockUser(${window.activeChat.id});this.closest('.modal-overlay').remove()"><span>🚫</span> Block</div><div class="chat-menu-item danger" onclick="clearChat(${window.activeChat.id});this.closest('.modal-overlay').remove()"><span>🗑️</span> Clear</div>`:''}</div>`; document.body.appendChild(m); };
    window.blockUser = async (id) => { if (!confirm('Block?')) return; try { await fetch(`/api/block_user/${id}`, { method:'POST' }); showToast('Blocked', 'success'); window.activeChat = null; if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; if (DOM.chatView) DOM.chatView.style.display = 'none'; loadChatList(); } catch (e) {} };
    window.clearChat = async (id) => { if (!confirm('Clear?')) return; try { await fetch(`/api/clear_chat/${id}`, { method:'POST' }); showToast('Cleared', 'success'); if (window.activeChat?.id===id && DOM.messagesContainer) DOM.messagesContainer.innerHTML = '<div class="empty-state"><p>No messages</p></div>'; loadChatList(); } catch (e) {} };

    window.showAddContactModal = () => { const m = document.createElement('div'); m.className = 'modal-overlay'; m.style.display = 'flex'; m.onclick = e => { if (e.target===m) m.remove(); }; m.innerHTML = `<div class="modal-container" style="max-width:400px"><div class="modal-header"><h3>Add Contact</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div><div class="modal-body"><input type="text" id="addContactSearch" class="modal-input" placeholder="Search username..."><div id="addContactResults" style="max-height:300px;overflow-y:auto"></div></div></div>`; document.body.appendChild(m); const si = getEl('addContactSearch'); if (si) { si.addEventListener('input', debounce(async () => { const q = si.value.trim(); if (q.length<2) return; try { const r = await fetch(`/api/users?search=${encodeURIComponent(q)}`); const d = await r.json(); if (d.success) { const res = getEl('addContactResults'); if (res) res.innerHTML = d.users.map(u => `<div class="contact-item" onclick="openChat('personal',${u.id});closeAllModals()"><div class="contact-avatar">${u.username[0].toUpperCase()}</div><div class="contact-info"><div class="contact-name">${escapeHtml(u.display_name)}</div><div class="contact-username">@${escapeHtml(u.username)}</div></div></div>`).join(''); } } catch (e) {} }, 300)); si.focus(); } };
    window.closeAllModals = () => { document.querySelectorAll('.modal-overlay').forEach(m => m.remove()); const pm = getEl('profileModal'); if (pm) pm.style.display = 'none'; const em = getEl('editProfileModal'); if (em) em.style.display = 'none'; };

    window.showChatsView = () => { hideAllPanels(); if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; };
    window.showFollowers = () => showToast('Followers', 'info');
    window.showFollowing = () => showToast('Following', 'info');
    window.showGroups = () => showToast('Groups', 'info');
    window.savePrivacySettings = () => { showToast('Saved', 'success'); window.closePrivacyPanel(); };
    window.toggleMobileSidebar = () => getEl('chatSidebar')?.classList.toggle('mobile-visible');
    window.logout = () => fetch('/api/auth/logout', { method:'POST' }).then(() => location.href='/login');
    window.triggerGroupAvatarUpload = () => getEl('groupAvatarInput')?.click();
    window.previewGroupAvatar = (i) => { if (i.files?.[0]) { const r = new FileReader(); r.onload = e => { const p = getEl('groupAvatarPreview'); if (p) p.innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`; }; r.readAsDataURL(i.files[0]); } };
    window.triggerChannelAvatarUpload = () => getEl('channelAvatarInput')?.click();
    window.previewChannelAvatar = (i) => { if (i.files?.[0]) { const r = new FileReader(); r.onload = e => { const p = getEl('channelAvatarPreview'); if (p) p.innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`; }; r.readAsDataURL(i.files[0]); } };
})();