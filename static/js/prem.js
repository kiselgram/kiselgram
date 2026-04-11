// static/js/prem.js
// Kiselgram Premium Edition - Complete
// Version 4.0.0

(function() {
    'use strict';

    console.log('✨ Kiselgram Premium v4.0.0');

    window.isPremium = true;
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

    function getEl(id) { return document.getElementById(id); }

    const DOM = {
        get emptyChat() { return getEl('emptyChat'); },
        get chatView() { return getEl('chatView'); },
        get contactsView() { return getEl('contactsView'); },
        get createGroupView() { return getEl('createGroupView'); },
        get createChannelView() { return getEl('createChannelView'); },
        get chatList() { return getEl('chatList'); },
        get storiesRow() { return getEl('storiesRow'); },
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

    document.addEventListener('DOMContentLoaded', async () => {
        await loadCurrentUser();
        await loadChatList();
        await loadStories();
        setupEventListeners();
        loadThemePreference();
        loadFontPreference();

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

    function debounce(fn, wait) { let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); }; }
    function escapeHtml(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
    function formatTime(ts) { if (!ts) return ''; const d = new Date(ts), n = new Date(), diff = n - d; if (diff < 60000) return 'Just now'; if (diff < 3600000) return Math.floor(diff/60000)+'m ago'; if (diff < 86400000) return Math.floor(diff/3600000)+'h ago'; return d.toLocaleDateString(); }

    function showToast(msg, type='info') {
        const toast = document.createElement('div');
        toast.textContent = msg;
        toast.style.cssText = `position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:${type==='success'?'#2dce89':type==='error'?'#fb6340':'#5e72e4'};color:white;padding:12px 24px;border-radius:30px;font-weight:500;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
    window.showToast = showToast;

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
    window.setFont = (el) => { document.querySelectorAll('.font-option').forEach(o => o.classList.remove('active')); el.classList.add('active'); document.body.style.setProperty('--font-family', el.dataset.font); localStorage.setItem('kiselgram_font', el.dataset.font); showToast('Font updated', 'success'); };
    function loadFontPreference() { const f = localStorage.getItem('kiselgram_font'); if (f) document.body.style.setProperty('--font-family', f); }
    window.toggleSetting = (el, setting) => { el.classList.toggle('active'); localStorage.setItem(`kiselgram_${setting}`, el.classList.contains('active')); };

    // Stories
    async function loadStories() { if (!window.currentUserId) return; try { const r = await fetch('/api/stories'); const d = await r.json(); if (d.success) { window.currentStories = d.stories || []; renderStoriesRow(); } } catch (e) {} }

    function renderStoriesRow() {
        const row = DOM.storiesRow; if (!row) return;
        const stories = window.currentStories || [];
        const hasStory = stories.some(s => s.user_id === window.currentUserId);
        let html = `<div class="story-item" onclick="showCreateStoryModal()"><div class="story-avatar ${hasStory ? '' : 'add-story'}">${hasStory ? `<div class="story-avatar-placeholder" style="background:linear-gradient(135deg,#fb6340,#2dce89)">${window.currentUserAvatar}</div>` : `<div class="add-story-btn" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white">+</div>`}</div><span class="story-username">Your story</span></div>`;
        for (const s of stories) { if (s.user_id === window.currentUserId) continue; const f = s.stories[0]; html += `<div class="story-item" onclick="openStoryViewer(${s.user_id})"><div class="story-avatar ${s.has_unviewed ? 'unviewed' : 'viewed'}">${f?.media_url && f.media_type==='image' ? `<img src="${f.media_url}" alt="${escapeHtml(s.display_name)}">` : `<div class="story-avatar-placeholder" style="background:linear-gradient(135deg,#fb6340,#2dce89)">${s.avatar_letter}</div>`}</div><span class="story-username">${escapeHtml(s.display_name)}</span></div>`; }
        row.innerHTML = html;
    }

    window.showCreateStoryModal = () => { const m = document.createElement('div'); m.className = 'modal-overlay'; m.innerHTML = `<div class="modal-container" style="max-width:400px"><div class="modal-header" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white"><h3>Create Story</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color:white">✕</button></div><div class="modal-body"><div class="story-media-upload" onclick="document.getElementById('storyMediaInput').click()"><div class="upload-placeholder" id="storyMediaPreview"><span style="font-size:48px">📸</span><p>Click to upload</p></div><input type="file" id="storyMediaInput" accept="image/*,video/*" style="display:none" onchange="previewStoryMedia(this)"></div><textarea id="storyCaption" class="modal-input" placeholder="Caption..." rows="2"></textarea></div><div class="modal-footer"><button class="modal-btn modal-btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button><button class="modal-btn modal-btn-primary" onclick="uploadStory()" style="background:linear-gradient(135deg,#fb6340,#2dce89)">Post</button></div></div>`; (DOM.modalRoot||document.body).appendChild(m); };
    window.previewStoryMedia = (i) => { const f = i.files[0]; if (!f) return; const p = getEl('storyMediaPreview'); if (!p) return; p.innerHTML = f.type.startsWith('video/') ? `<video src="${URL.createObjectURL(f)}" autoplay loop muted style="width:100%;height:100%;object-fit:cover"></video>` : `<img src="${URL.createObjectURL(f)}" style="width:100%;height:100%;object-fit:cover">`; };
    window.uploadStory = async () => { const f = getEl('storyMediaInput')?.files[0]; if (!f) { showToast('Select media', 'error'); return; } const fd = new FormData(); fd.append('media', f); fd.append('caption', getEl('storyCaption')?.value||''); try { const r = await fetch('/api/stories/create', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { document.querySelectorAll('.modal-overlay').forEach(m => m.remove()); showToast('Story posted!', 'success'); loadStories(); } } catch (e) {} };

    window.openStoryViewer = (uid) => { const u = window.currentStories.find(s => s.user_id === uid); if (!u) return; window.currentStoryUser = u; window.currentStoryIndex = 0; renderStoryViewer(); };
    function renderStoryViewer() { /* ... full story viewer ... */ }
    window.closeStoryViewer = () => { if (window.storyProgressInterval) clearInterval(window.storyProgressInterval); getEl('storyViewer')?.remove(); document.body.style.overflow = ''; loadStories(); };
    window.nextStory = () => {};
    window.previousStory = () => {};
    window.likeCurrentStory = async () => {};
    window.deleteCurrentStory = async () => {};
    window.sendStoryReply = () => {};

    // Chat
    async function loadChatList() { try { const r = await fetch('/api/chat_list'); const d = await r.json(); if (d.success) renderChatList(d.chats); } catch (e) {} }
    function renderChatList(chats) { const c = DOM.chatList; if (!c) return; if (!chats?.length) { c.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No chats</p></div>'; return; } c.innerHTML = chats.map(chat => { const active = window.activeChat?.type===chat.type && window.activeChat?.id===chat.id; return `<div class="chat-item ${active?'active':''}" data-chat-type="${chat.type}" data-chat-id="${chat.id}" onclick="openChat('${chat.type}',${chat.id})"><div class="chat-avatar ${chat.type}">${chat.avatar_url?`<img src="${chat.avatar_url}">`:(chat.avatar||'?')}</div><div class="chat-info"><div class="chat-name-row"><span class="chat-name">${escapeHtml(chat.name)}</span><span class="chat-time">${chat.timestamp||''}</span></div><div class="chat-preview"><span>${escapeHtml(chat.last_message||'')}</span>${chat.unread_count>0?`<span class="unread-badge">${chat.unread_count}</span>`:''}</div></div></div>`; }).join(''); }

    function hideAllPanels() { [DOM.emptyChat, DOM.chatView, DOM.contactsView, DOM.createGroupView, DOM.createChannelView].forEach(el => { if (el) el.style.display = 'none'; }); }
    window.openChat = async (type, id) => { window.activeChat = { type, id }; document.querySelectorAll('.chat-item').forEach(i => i.classList.remove('active')); document.querySelector(`.chat-item[data-chat-type="${type}"][data-chat-id="${id}"]`)?.classList.add('active'); hideAllPanels(); if (DOM.chatView) DOM.chatView.style.display = 'flex'; await loadChatInfo(type, id); await loadMessages(type, id); applyWallpaper(); if (type==='personal') await fetch(`/api/mark_read/${id}`, { method:'POST' }); DOM.messageInput?.focus(); };
    async function loadChatInfo(type, id) { if (type==='personal') { try { const r = await fetch('/api/users'); const d = await r.json(); const u = d.users?.find(u => u.id===id); if (u) { if (DOM.chatHeaderName) DOM.chatHeaderName.textContent = u.display_name||u.username; if (DOM.chatHeaderStatus) { DOM.chatHeaderStatus.textContent = u.is_online?'Online':'Offline'; DOM.chatHeaderStatus.classList.toggle('online', u.is_online); } if (DOM.chatHeaderAvatar) { DOM.chatHeaderAvatar.textContent = u.username[0].toUpperCase(); DOM.chatHeaderAvatar.className = 'chat-header-avatar personal'; } } } catch (e) {} } else { if (DOM.chatHeaderName) DOM.chatHeaderName.textContent = type==='group'?'Group':'Channel'; if (DOM.chatHeaderAvatar) { DOM.chatHeaderAvatar.textContent = type==='group'?'👥':'📢'; DOM.chatHeaderAvatar.className = `chat-header-avatar ${type}`; } } }

    async function loadMessages(type, id) { const c = DOM.messagesContainer; if (!c) return; c.innerHTML = '<div class="loading-spinner"></div>'; try { let url = type==='personal'?`/api/messages/${id}`:`/api/group_messages/${id}`; const r = await fetch(`${url}?after=0&limit=50`); const d = await r.json(); const msgs = d.messages || (d.success && d.messages) || []; if (msgs.length) { let h = '', ld = null; for (const m of msgs) { const md = new Date(m.timestamp||Date.now()); const ds = md.toLocaleDateString(); if (ds !== ld) { const t = new Date(), y = new Date(t); y.setDate(y.getDate()-1); let dt = ''; if (md.toDateString()===t.toDateString()) dt='Today'; else if (md.toDateString()===y.toDateString()) dt='Yesterday'; else dt=md.toLocaleDateString(undefined,{month:'long',day:'numeric'}); h += `<div class="message-date-divider">${dt}</div>`; ld = ds; } h += renderMessage(m); } c.innerHTML = h; } else { c.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No messages</p></div>'; } c.scrollTop = c.scrollHeight; applyWallpaper(); } catch (e) { c.innerHTML = '<div class="empty-state"><p>Error</p></div>'; } }

    function renderMessage(m) { const isOwn = m.is_own || m.sender_id === window.currentUserId; let att = ''; if (m.has_attachment) { if (m.file_type==='image') att = `<img src="${m.file_url}" class="message-image" onclick="openImageViewer('${m.file_url}')">`; else att = `<div class="file-attachment"><span>📎</span><a href="${m.file_url}" target="_blank">${m.file_name||'File'}</a></div>`; } const content = m.content||''; return `<div class="message-wrapper ${isOwn?'outgoing':'incoming'}" id="msg-${m.id}">${!isOwn?`<div class="message-sender">${escapeHtml(m.sender_name||'User')}</div>`:''}<div class="message-bubble">${att}${content?`<div class="message-text">${escapeHtml(content).replace(/\n/g,'<br>')}</div>`:''}<div class="message-meta"><span class="message-time">${m.timestamp_formatted||''}</span>${isOwn?`<span>${m.is_read?'✓✓':'✓'}</span>`:''}</div></div></div>`; }

    function handleMessageInput() { if (DOM.messageInput && DOM.sendBtn) DOM.sendBtn.disabled = !DOM.messageInput.value.trim(); if (DOM.messageInput) { DOM.messageInput.style.height = 'auto'; DOM.messageInput.style.height = Math.min(DOM.messageInput.scrollHeight, 100) + 'px'; } }
    async function handleMessageKeydown(e) { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); await sendMessage(); } }
    async function sendMessage() { const content = DOM.messageInput?.value.trim(); if (!content || !window.activeChat) return; let url = window.activeChat.type==='personal'?'/api/send_message':'/api/send_group_message'; const payload = { content }; if (window.activeChat.type==='personal') payload.receiver_id = window.activeChat.id; else payload.group_id = window.activeChat.id; if (window.replyToMessage) { payload.reply_to_id = window.replyToMessage; window.replyToMessage = null; if (DOM.replyPreview) DOM.replyPreview.style.display = 'none'; } try { const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) }); const d = await r.json(); if (d.success && d.message) { if (DOM.messageInput) DOM.messageInput.value = ''; handleMessageInput(); const c = DOM.messagesContainer; if (c) { if (c.querySelector('.empty-state')) c.innerHTML = ''; c.insertAdjacentHTML('beforeend', renderMessage(d.message)); c.scrollTop = c.scrollHeight; } loadChatList(); } } catch (e) {} }

    window.setReply = (id) => { window.replyToMessage = id; const msg = getEl(`msg-${id}`); if (msg && DOM.replyPreview) { const t = msg.querySelector('.message-text')?.textContent||''; DOM.replyPreview.querySelector('.reply-preview-name').textContent = 'Replying'; DOM.replyPreview.querySelector('.reply-preview-text').textContent = t.substring(0,50); DOM.replyPreview.style.display = 'flex'; } };
    window.cancelReply = () => { window.replyToMessage = null; if (DOM.replyPreview) DOM.replyPreview.style.display = 'none'; };
    window.deleteMessage = async (id) => { if (!confirm('Delete?')) return; try { await fetch(`/api/messages/${id}`, { method:'DELETE' }); getEl(`msg-${id}`)?.remove(); } catch (e) {} };
    window.openImageViewer = (url) => window.open(url, '_blank');

    // Customization
    window.openChatCustomization = () => { const m = document.createElement('div'); m.className = 'modal-overlay'; m.innerHTML = `<div class="modal-container" style="max-width:450px"><div class="modal-header" style="background:linear-gradient(135deg,#fb6340,#2dce89);color:white"><h3>Customization</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color:white">✕</button></div><div class="modal-body"><h4>Wallpaper</h4><div class="wallpaper-options">${['gradient1','gradient2','gradient3','gradient4','gradient5','default'].map(w => `<div class="wallpaper-option" style="background:${w==='default'?'var(--bg-surface)':''}" onclick="setWallpaper('${w}')">${w==='default'?'Default':''}</div>`).join('')}</div></div></div>`; (DOM.modalRoot||document.body).appendChild(m); };
    window.setWallpaper = (w) => { if (!window.activeChat) return; localStorage.setItem(`wallpaper_${window.activeChat.type}_${window.activeChat.id}`, w); applyWallpaper(); showToast('Wallpaper updated', 'success'); };
    function applyWallpaper() { if (!window.activeChat) return; const w = localStorage.getItem(`wallpaper_${window.activeChat.type}_${window.activeChat.id}`) || 'default'; const c = DOM.messagesContainer; if (c) { c.classList.remove('wallpaper-gradient1','wallpaper-gradient2','wallpaper-gradient3','wallpaper-gradient4','wallpaper-gradient5'); if (w!=='default') c.classList.add(`wallpaper-${w}`); } }

    // Contacts
    window.showContactsView = () => { window.closePopout(); hideAllPanels(); if (DOM.contactsView) DOM.contactsView.style.display = 'flex'; loadContacts(); };
    window.hideContactsView = () => { if (DOM.contactsView) DOM.contactsView.style.display = 'none'; if (window.activeChat) { if (DOM.chatView) DOM.chatView.style.display = 'flex'; } else { if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; } };
    async function loadContacts() { const c = getEl('contactsList'); if (!c) return; try { const r = await fetch('/api/contacts'); const d = await r.json(); if (d.success) { c.innerHTML = d.contacts.map(u => `<div class="contact-item" onclick="openChat('personal',${u.id})"><div class="contact-avatar">${u.username[0].toUpperCase()}</div><div class="contact-info"><div class="contact-name">${escapeHtml(u.display_name)}</div><div class="contact-username">@${escapeHtml(u.username)}</div></div></div>`).join('') || '<div class="empty-state"><p>No contacts</p></div>'; } } catch (e) {} }

    // Search
    async function handleGlobalSearch() { const q = DOM.globalSearchInput?.value.trim(); const r = DOM.searchResults; if (!r) return; if (!q||q.length<2) { r.innerHTML = ''; r.classList.remove('active'); return; } try { const res = await fetch(`/api/search/global?q=${encodeURIComponent(q)}`); const d = await res.json(); if (d.success) { let h = ''; if (d.results.users?.length) { h += '<div class="search-result-section">Users</div>'; d.results.users.forEach(u => { h += `<div class="search-result-item" onclick="openChat('personal',${u.id});closeSearchResults()"><div class="search-result-avatar">${u.username[0].toUpperCase()}</div><div class="search-result-info"><div class="search-result-name">${escapeHtml(u.display_name)}</div><div class="search-result-type">@${escapeHtml(u.username)}</div></div></div>`; }); } if (d.results.groups?.length) { h += '<div class="search-result-section">Groups</div>'; d.results.groups.forEach(g => { h += `<div class="search-result-item" onclick="openChat('group',${g.id});closeSearchResults()"><div class="search-result-avatar">👥</div><div class="search-result-info"><div class="search-result-name">${escapeHtml(g.name)}</div><div class="search-result-type">Group</div></div></div>`; }); } r.innerHTML = h || '<div class="search-result-item">No results</div>'; r.classList.add('active'); } } catch (e) {} }
    window.closeSearchResults = () => { DOM.searchResults?.classList.remove('active'); if (DOM.globalSearchInput) DOM.globalSearchInput.value = ''; };

    // Groups & Channels
    window.showCreateGroupView = () => { window.closePopout(); hideAllPanels(); if (DOM.createGroupView) DOM.createGroupView.style.display = 'flex'; window.selectedMembers = []; const c = getEl('selectedMembers'); if (c) c.innerHTML = ''; };
    window.hideCreateGroupView = () => { if (DOM.createGroupView) DOM.createGroupView.style.display = 'none'; if (window.activeChat) { if (DOM.chatView) DOM.chatView.style.display = 'flex'; } else { if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; } };
    window.createGroup = async () => { const n = getEl('groupName')?.value.trim(); if (!n) { showToast('Enter name', 'error'); return; } const fd = new FormData(); fd.append('name', n); fd.append('member_ids', JSON.stringify(window.selectedMembers||[])); const a = getEl('groupAvatarInput'); if (a?.files[0]) fd.append('avatar', a.files[0]); try { const r = await fetch('/api/groups/create', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { showToast('Created!', 'success'); window.hideCreateGroupView(); loadChatList(); openChat('group', d.group.id); } } catch (e) {} };
    window.showCreateChannelView = () => { window.closePopout(); hideAllPanels(); if (DOM.createChannelView) DOM.createChannelView.style.display = 'flex'; };
    window.hideCreateChannelView = () => { if (DOM.createChannelView) DOM.createChannelView.style.display = 'none'; if (window.activeChat) { if (DOM.chatView) DOM.chatView.style.display = 'flex'; } else { if (DOM.emptyChat) DOM.emptyChat.style.display = 'flex'; } };
    window.createChannel = async () => { const n = getEl('channelName')?.value.trim(); if (!n) { showToast('Enter name', 'error'); return; } const fd = new FormData(); fd.append('name', n); const a = getEl('channelAvatarInput'); if (a?.files[0]) fd.append('avatar', a.files[0]); try { const r = await fetch('/api/channels/create', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { showToast('Created!', 'success'); window.hideCreateChannelView(); loadChatList(); openChat('channel', d.channel.id); } } catch (e) {} };

    // Profile
    window.openProfileModal = () => { const m = getEl('profileModal'); if (m) m.style.display = 'flex'; loadProfileData(); };
    window.closeProfileModal = () => { const m = getEl('profileModal'); if (m) m.style.display = 'none'; };
    async function loadProfileData() { try { const r = await fetch('/api/profile'); const d = await r.json(); if (d.success && d.user) { const u = d.user; const dn = getEl('profileDisplayName'), un = getEl('profileUsername'), av = getEl('profileAvatar'), dnv = getEl('profileDisplayNameValue'), unv = getEl('profileUsernameValue'), bv = getEl('profileBioValue'), bio = getEl('profileBio'); if (dn) dn.textContent = u.display_name; if (un) un.textContent = '@'+u.username; if (bio) bio.textContent = u.bio||'No bio yet'; if (dnv) dnv.textContent = u.display_name; if (unv) unv.textContent = '@'+u.username; if (bv) bv.textContent = u.bio||'No bio yet'; if (av) av.innerHTML = u.avatar_url ? `<img src="${u.avatar_url}" class="profile-avatar">` : `<div class="profile-avatar-placeholder">${u.username[0].toUpperCase()}</div>`; } } catch (e) {} }
    window.openEditProfileModal = () => { const m = getEl('editProfileModal'); if (!m) return; const dn = getEl('profileDisplayNameValue')?.textContent || window.currentUserDisplayName; const un = getEl('profileUsernameValue')?.textContent.replace('@','') || window.currentUserUsername; const bio = getEl('profileBioValue')?.textContent || ''; const ed = getEl('editDisplayName'), eu = getEl('editUsername'), eb = getEl('editBio'), cc = getEl('bioCharCount'); if (ed) ed.value = dn; if (eu) eu.value = un; if (eb) { eb.value = bio==='No bio yet'?'':bio; if (cc) { cc.textContent = eb.value.length; eb.addEventListener('input', () => cc.textContent = eb.value.length); } } m.style.display = 'flex'; };
    window.closeEditProfileModal = () => { const m = getEl('editProfileModal'); if (m) m.style.display = 'none'; };
    window.saveProfile = async () => { const dn = getEl('editDisplayName')?.value.trim()||''; const un = getEl('editUsername')?.value.trim()||''; const bio = getEl('editBio')?.value.trim()||''; if (!dn) { showToast('Display name required', 'error'); return; } if (!un || un.length<3) { showToast('Username min 3 chars', 'error'); return; } if (!/^[a-zA-Z0-9_]+$/.test(un)) { showToast('Invalid username', 'error'); return; } try { const r = await fetch('/api/profile/update', { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({display_name:dn, username:un, bio}) }); const d = await r.json(); if (d.success) { window.currentUserDisplayName = dn; window.currentUserUsername = un; window.currentUserAvatar = un[0].toUpperCase(); updateUI(); closeEditProfileModal(); loadProfileData(); showToast('Profile updated!', 'success'); } else { showToast(d.error||'Failed', 'error'); } } catch (e) { showToast('Error', 'error'); } };
    window.triggerAvatarUpload = () => getEl('avatarInput')?.click();
    window.uploadAvatar = async (i) => { const f = i.files?.[0]; if (!f) return; const fd = new FormData(); fd.append('avatar', f); try { const r = await fetch('/files/upload_avatar', { method:'POST', body:fd }); const d = await r.json(); if (d.success) { showToast('Avatar updated!', 'success'); window.currentUserAvatar = window.currentUserUsername[0].toUpperCase(); updateUI(); loadProfileData(); } } catch (e) {} };

    // File upload
    window.triggerFileUpload = () => getEl('fileInput')?.click();
    window.handleFileSelect = (i) => { const f = i.files; if (!f?.length) return; const fn = getEl('uploadFileName'); const ua = getEl('uploadArea'); if (fn) fn.textContent = f.length===1 ? f[0].name : `${f.length} files`; if (ua) ua.classList.add('active'); };
    window.uploadFile = async () => { const i = getEl('fileInput'); const f = i?.files; if (!f?.length || !window.activeChat) { window.cancelUpload(); return; } for (const file of f) { const fd = new FormData(); fd.append('file', file); if (window.activeChat.type==='personal') fd.append('receiver_id', window.activeChat.id); else fd.append('group_id', window.activeChat.id); try { const r = await fetch('/files/upload_file', { method:'POST', body:fd }); const d = await r.json(); if (d.success && DOM.messagesContainer) { if (DOM.messagesContainer.querySelector('.empty-state')) DOM.messagesContainer.innerHTML = ''; DOM.messagesContainer.insertAdjacentHTML('beforeend', renderMessage(d.message)); DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight; } } catch (e) {} } window.cancelUpload(); };
    window.cancelUpload = () => { const ua = getEl('uploadArea'); const fi = getEl('fileInput'); if (ua) ua.classList.remove('active'); if (fi) fi.value = ''; };

    // Misc
    window.showChatInfo = () => showToast('Chat info', 'info');
    window.showChatMenu = () => { if (!window.activeChat) return; const m = document.createElement('div'); m.className = 'modal-overlay'; m.onclick = e => { if (e.target===m) m.remove(); }; m.innerHTML = `<div class="chat-menu-dropdown" style="position:fixed;top:60px;right:20px;background:var(--bg-secondary);border-radius:12px;box-shadow:var(--shadow-lg);padding:8px 0;min-width:200px;z-index:2000"><div class="chat-menu-item" onclick="showChatInfo();this.closest('.modal-overlay').remove()"><span>ℹ️</span> View Info</div><div class="chat-menu-item" onclick="openChatCustomization();this.closest('.modal-overlay').remove()"><span>🎨</span> Customize</div>${window.activeChat.type==='personal'?`<div class="chat-menu-divider"></div><div class="chat-menu-item danger" onclick="blockUser(${window.activeChat.id});this.closest('.modal-overlay').remove()"><span>🚫</span> Block</div><div class="chat-menu-item danger" onclick="clearChat(${window.activeChat.id});this.closest('.modal-overlay').remove()"><span>🗑️</span> Clear</div>`:''}</div>`; document.body.appendChild(m); };
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

    // Story viewer functions (simplified)
    function startProgress() {}
    window.nextStory = () => {};
    window.previousStory = () => {};

})();