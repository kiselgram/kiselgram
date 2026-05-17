// static/js/chats/common.js
// Shared functionality for Kiselgram Free & Premium

// ==================== GLOBALS ====================
let currentUser = null;
let currentUserId = null;
let activeChat = null;
let activeChatType = null;
let replyToMessage = null;
let selectedMembers = [];
let pendingFiles = [];

// ==================== UTILITIES ====================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const colors = { success: '#10b981', error: '#ef4444', info: '#667eea' };
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = `
        position:fixed; bottom:80px; left:50%; transform:translateX(-50%);
        background:${colors[type] || colors.info}; color:white; padding:12px 24px;
        border-radius:30px; font-weight:500; z-index:9999; box-shadow:0 4px 12px rgba(0,0,0,0.3);
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function debounce(fn, wait) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const sizes = ['B','KB','MB','GB'];
    let i = 0;
    while (bytes >= 1024 && i < sizes.length-1) { bytes /= 1024; i++; }
    return `${bytes.toFixed(1)} ${sizes[i]}`;
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
}

// ==================== USER LOADING ====================
async function loadCurrentUser() {
    try {
        const res = await fetch('/api/profile');
        const data = await res.json();
        if (data.success && data.user) {
            currentUser = data.user;
            currentUserId = data.user.id;
            updateUserUI();
        }
    } catch (e) { console.error('Failed to load user', e); }
}

function updateUserUI() {
    const avatar = document.getElementById('menuUserAvatar');
    const name = document.getElementById('menuUserName');
    const username = document.getElementById('menuUserUsername');
    if (avatar && currentUser) avatar.textContent = currentUser.username[0].toUpperCase();
    if (name) name.textContent = currentUser.display_name || currentUser.username;
    if (username) username.textContent = '@' + currentUser.username;
}

// ==================== MENU & PANELS ====================
function togglePopoutMenu() {
    document.body.classList.toggle('popout-open');
    document.getElementById('menuBtn').classList.toggle('active');
}
function closePopout() {
    document.body.classList.remove('popout-open');
    document.getElementById('menuBtn').classList.remove('active');
}
function closeAllPanels() {
    ['settingsPanel','privacyPanel','sessionsPanel'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('open');
    });
    document.getElementById('panelOverlay').classList.remove('visible');
}

function openSettingsPanel() {
    closeAllPanels();
    document.getElementById('settingsPanel').classList.add('open');
    document.getElementById('panelOverlay').classList.add('visible');
    closePopout();
}
function closeSettingsPanel() {
    document.getElementById('settingsPanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('visible');
}

// ----- Privacy Panel -----
function openPrivacyPanel() {
    closeAllPanels();
    document.getElementById('privacyPanel').classList.add('open');
    document.getElementById('panelOverlay').classList.add('visible');
    closePopout();
}
function closePrivacyPanel() {
    document.getElementById('privacyPanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('visible');
}
async function savePrivacySettings() {
    const settings = {
        last_seen: document.getElementById('privacyLastSeen').value,
        photo: document.getElementById('privacyPhoto').value,
        calls: document.getElementById('privacyCalls').value,
        messages: document.getElementById('privacyMessages').value,
    };
    try {
        const res = await fetch('/api/profile/privacy', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (res.ok) showToast('Privacy saved', 'success');
    } catch (e) { showToast('Error saving privacy', 'error'); }
}

// ----- Sessions Panel (calls Flask endpoints) -----
function openSessionsPanel() {
    closeAllPanels();
    loadSessions();
    document.getElementById('sessionsPanel').classList.add('open');
    document.getElementById('panelOverlay').classList.add('visible');
    closePopout();
}
function closeSessionsPanel() {
    document.getElementById('sessionsPanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('visible');
}
async function loadSessions() {
    const list = document.getElementById('sessionsList');
    list.innerHTML = '<div class="loading-spinner"></div>';
    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();
        if (data.success) {
            list.innerHTML = data.sessions.map(s => `
                <div class="session-item" style="padding:12px; border-bottom:1px solid var(--border-color); display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <i class="fas fa-desktop"></i> ${escapeHtml(s.device || 'Unknown')}
                        <div style="font-size:12px; color:var(--text-muted);">IP: ${s.ip || 'N/A'} · ${s.last_activity}</div>
                    </div>
                    <button class="modal-btn modal-btn-secondary" onclick="terminateSession('${s.session_token}')" style="padding:6px 12px;"><i class="fas fa-times"></i> Terminate</button>
                </div>
            `).join('');
            if (!data.sessions.length) list.innerHTML = '<div class="empty-state"><p>No other active sessions</p></div>';
        }
    } catch(e) { list.innerHTML = '<div class="empty-state"><p>Failed to load sessions</p></div>'; }
}
async function terminateSession(token) {
    if (!confirm('Terminate this session?')) return;
    try {
        await fetch('/api/sessions/terminate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_token: token })
        });
        showToast('Session terminated', 'success');
        loadSessions();
    } catch(e) { showToast('Error', 'error'); }
}
async function terminateAllSessions() {
    if (!confirm('Terminate all other sessions?')) return;
    try {
        await fetch('/api/sessions/terminate_all', { method: 'POST' });
        showToast('All other sessions terminated', 'success');
        loadSessions();
    } catch(e) { showToast('Error', 'error'); }
}

// ==================== PROFILE MODAL ====================
function openProfileModal() {
    window.location.href = '/profile';
}

// ==================== SAVED MESSAGES ====================
function openSavedMessages() {
    if (currentUserId) openChat('personal', currentUserId);
}

// ==================== PINNED CHATS ====================
async function togglePin(chatId) {
    try {
        const res = await fetch('/api/pin_chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chat_id: chatId })
        });
        const data = await res.json();
        if (data.success) loadChatList();
    } catch(e) { console.error(e); }
}

// ==================== CHAT LIST ====================
async function loadChatList() {
    const container = document.getElementById('chatList');
    try {
        const res = await fetch('/api/chat_list');
        const data = await res.json();
        if (data.success) renderChatList(data.chats);
        else container.innerHTML = '<div class="empty-state"><i class="fas fa-comment-slash"></i><p>No chats yet</p></div>';
    } catch(e) {
        container.innerHTML = '<div class="empty-state"><p>Failed to load chats</p></div>';
    }
}

function renderChatList(chats) {
    const pinned = chats.filter(c => c.is_pinned);
    const unpinned = chats.filter(c => !c.is_pinned);
    const pinnedContainer = document.getElementById('pinnedChatsContainer');
    if (pinnedContainer) pinnedContainer.innerHTML = pinned.map(c => renderChatItem(c, true)).join('');

    const list = document.getElementById('chatList');
    if (!list) return;

    // Remove all chat items EXCEPT saved-messages
    const toRemove = list.querySelectorAll('.chat-item:not(.saved-messages)');
    toRemove.forEach(el => el.remove());

    // Remove the loading spinner (if still present)
    const spinner = list.querySelector('.loading-spinner');
    if (spinner) spinner.remove();

    s// Append unpinned chats
    const html = unpinned.map(c => renderChatItem(c, false)).join('');
    list.insertAdjacentHTML('beforeend', html);
}

function renderChatItem(chat, isPinned) {
    const activeClass = (activeChat && activeChat.id == chat.id && activeChat.type == chat.type) ? 'active' : '';
    const typeIcon = { personal: 'fa-user', group: 'fa-users', channel: 'fa-bullhorn' };
    const avatarHtml = chat.avatar_url
        ? `<img src="${chat.avatar_url}" alt="">`
        : `<i class="fas ${typeIcon[chat.type] || 'fa-comment'}"></i>`;

    return `
        <div class="chat-item ${isPinned ? 'pinned' : ''} ${activeClass}"
             data-chat-id="${chat.id}" data-chat-type="${chat.type}"
             onclick="openChat('${chat.type}', ${chat.id})">
            ${isPinned ? `<div class="pin-button" onclick="event.stopPropagation(); togglePin(${chat.id})"><i class="fas fa-thumbtack"></i></div>` : ''}
            <div class="chat-avatar ${chat.type}">
                ${avatarHtml}
                ${chat.type === 'personal' && chat.is_online ? '<span class="online-indicator"></span>' : ''}
            </div>
            <div class="chat-info">
                <div class="chat-name-row">
                    <span class="chat-name">${escapeHtml(chat.name)}</span>
                    <span class="chat-time">${chat.timestamp || ''}</span>
                </div>
                <div class="chat-preview">
                    <span class="chat-message">${escapeHtml(chat.last_message || '')}</span>
                    ${chat.unread_count > 0 ? `<span class="chat-badge">${chat.unread_count}</span>` : ''}
                </div>
            </div>
        </div>
    `;
}

// ==================== CHAT VIEW ====================
function hideAllPanels() {
    ['emptyChat','chatView','contactsView','createGroupView','createChannelView'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
}

function showChatsView() {
    hideAllPanels();
    document.getElementById('emptyChat').style.display = 'flex';
}

async function openChat(type, id) {
    activeChat = { type, id };
    activeChatType = type;
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    const item = document.querySelector(`.chat-item[data-chat-type="${type}"][data-chat-id="${id}"]`);
    if (item) item.classList.add('active');

    hideAllPanels();
    document.getElementById('chatView').style.display = 'flex';

    await loadChatInfo(type, id);
    await loadMessages(type, id);
    if (type === 'personal') {
        await fetch(`/api/mark_read/${id}`, { method: 'POST' });
    }
    document.getElementById('messageInput').focus();
}

async function loadChatInfo(type, id) {
    const headerName = document.getElementById('chatHeaderName');
    const headerAvatar = document.getElementById('chatHeaderAvatar');
    const headerStatus = document.getElementById('chatHeaderStatus');

    if (type === 'personal') {
        try {
            const res = await fetch('/api/users');
            const data = await res.json();
            const user = data.users?.find(u => u.id == id);
            if (user) {
                headerName.textContent = user.display_name || user.username;
                headerStatus.textContent = user.is_online ? 'Online' : 'Offline';
                headerStatus.className = `chat-header-status ${user.is_online ? 'online' : ''}`;
                headerAvatar.innerHTML = user.avatar_url ? `<img src="${user.avatar_url}" alt="">` : user.username[0].toUpperCase();
            }
        } catch(e) {}
    } else if (type === 'group') {
        try {
            const res = await fetch(`/api/groups/${id}`);
            const data = await res.json();
            if (data.success && data.group) {
                headerName.textContent = data.group.name;
                headerStatus.textContent = `${data.group.member_count || 0} members`;
                headerAvatar.innerHTML = data.group.avatar_url ? `<img src="${data.group.avatar_url}" alt="">` : '<i class="fas fa-users"></i>';
            }
        } catch(e) {}
    } else if (type === 'channel') {
        try {
            const res = await fetch(`/api/channels/${id}`);
            const data = await res.json();
            if (data.success && data.channel) {
                headerName.textContent = data.channel.name;
                headerStatus.textContent = `${data.channel.subscriber_count || 0} subscribers`;
                headerAvatar.innerHTML = data.channel.avatar_url ? `<img src="${data.channel.avatar_url}" alt="">` : '<i class="fas fa-bullhorn"></i>';
            }
        } catch(e) {}
    }
}

// ---- loadMessages ----
async function loadMessages(type, id) {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = '<div class="loading-spinner"></div>';
    let url = '';
    if (type === 'personal') url = `/api/messages/${id}`;
    else if (type === 'group') url = `/api/group_messages/${id}`;
    else if (type === 'channel') url = `/api/channel_messages/${id}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        if (data.success) {
            renderMessages(data.messages);
        } else {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-comment-dots"></i><p>No messages yet</p></div>';
        }
    } catch(e) {
        container.innerHTML = '<div class="empty-state"><p>Failed to load messages</p></div>';
    }
}

function renderMessages(messages) {
    const container = document.getElementById('messagesContainer');
    if (!messages.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-comment-dots"></i><p>No messages yet</p></div>';
        return;
    }
    let html = '';
    messages.forEach(m => {
        const isOwn = m.sender_id === currentUserId;
        html += `
            <div class="message-wrapper ${isOwn ? 'outgoing' : 'incoming'}" id="msg-${m.id}">
                ${!isOwn ? `<div class="message-sender">${escapeHtml(m.sender_name)}</div>` : ''}
                <div class="message-bubble">
                    ${m.has_attachment ? (m.file_type === 'image'
                        ? `<img src="${m.file_url}" class="message-image" onclick="openImageViewer('${m.file_url}')">`
                        : `<div class="file-attachment"><i class="fas fa-file"></i> <a href="${m.file_url}" target="_blank">${m.file_name}</a> (${formatFileSize(m.file_size)})</div>`) : ''}
                    ${m.content ? `<div class="message-text">${escapeHtml(m.content)}</div>` : ''}
                    <div class="message-meta">
                        <span class="message-time">${m.timestamp_formatted}</span>
                        ${isOwn ? `<span>${m.is_read ? '✓✓' : '✓'}</span>` : ''}
                    </div>
                </div>
            </div>`;
    });
    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
}

// ---- sendMessage ----
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content || !activeChat) return;
    const payload = { content };
    let url = '';
    if (activeChat.type === 'personal') { url = '/api/send_message'; payload.receiver_id = activeChat.id; }
    else if (activeChat.type === 'group') { url = '/api/send_group_message'; payload.group_id = activeChat.id; }
    else if (activeChat.type === 'channel') { url = '/api/send_channel_message'; payload.channel_id = activeChat.id; }

    if (replyToMessage) {
        payload.reply_to_id = replyToMessage;
        cancelReply();
    }

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            input.value = '';
            document.getElementById('sendBtn').disabled = true;
            addMessageToView(data.message);
        }
    } catch(e) { showToast('Error sending message', 'error'); }
}

function addMessageToView(msg) {
    const container = document.getElementById('messagesContainer');
    if (container.querySelector('.empty-state')) container.innerHTML = '';
    const isOwn = msg.sender_id === currentUserId;
    const html = `
        <div class="message-wrapper ${isOwn ? 'outgoing' : 'incoming'}" id="msg-${msg.id}">
            ${!isOwn ? `<div class="message-sender">${escapeHtml(msg.sender_name)}</div>` : ''}
            <div class="message-bubble">
                ${msg.content ? `<div class="message-text">${escapeHtml(msg.content)}</div>` : ''}
                <div class="message-meta">
                    <span class="message-time">${msg.timestamp_formatted}</span>
                    ${isOwn ? '<span>✓</span>' : ''}
                </div>
            </div>
        </div>`;
    container.insertAdjacentHTML('beforeend', html);
    container.scrollTop = container.scrollHeight;
}

// ==================== REPLY / FORWARD / DELETE ====================
function setReply(messageId) {
    const msgEl = document.getElementById(`msg-${messageId}`);
    if (!msgEl) return;
    replyToMessage = messageId;
    const text = msgEl.querySelector('.message-text')?.textContent || '';
    const preview = document.getElementById('replyPreview');
    if (preview) {
        preview.querySelector('.reply-preview-name').textContent = 'Replying';
        preview.querySelector('.reply-preview-text').textContent = text.substring(0, 50);
        preview.style.display = 'flex';
    }
    document.getElementById('messageInput').focus();
}

function cancelReply() {
    replyToMessage = null;
    const preview = document.getElementById('replyPreview');
    if (preview) preview.style.display = 'none';
}

async function deleteMessage(messageId) {
    if (!confirm('Delete this message?')) return;
    try {
        const res = await fetch(`/api/messages/${messageId}`, { method: 'DELETE' });
        if (res.ok) {
            document.getElementById(`msg-${messageId}`)?.remove();
            showToast('Deleted', 'success');
        }
    } catch(e) { showToast('Error', 'error'); }
}

// ==================== FILE HANDLING ====================
function triggerFileUpload() { document.getElementById('fileInput').click(); }

function handleFileSelect(input) {
    const files = Array.from(input.files);
    if (!files.length) return;
    pendingFiles = files;

    const previewBody = document.getElementById('previewBody');
    let html = '';
    let totalSize = 0;
    files.forEach(file => {
        totalSize += file.size;
        const ext = file.name.split('.').pop().toLowerCase();
        const isImage = ['jpg','jpeg','png','gif','webp'].includes(ext);
        const isVideo = ['mp4','webm','mov'].includes(ext);
        if (isImage) {
            const url = URL.createObjectURL(file);
            html += `<div class="preview-item"><img src="${url}" style="max-width:100%;max-height:200px;border-radius:8px;"><div class="preview-info"><span>${escapeHtml(file.name)}</span><span>${formatFileSize(file.size)}</span></div></div>`;
        } else if (isVideo) {
            const url = URL.createObjectURL(file);
            html += `<div class="preview-item"><video src="${url}" controls style="max-width:100%;max-height:200px;border-radius:8px;"></video><div class="preview-info"><span>${escapeHtml(file.name)}</span><span>${formatFileSize(file.size)}</span></div></div>`;
        } else {
            html += `<div class="preview-item"><div style="padding:20px; background:var(--bg-tertiary); border-radius:8px; text-align:center;"><i class="fas fa-file" style="font-size:48px;"></i><div style="margin-top:10px;"><strong>${escapeHtml(file.name)}</strong><div>${ext.toUpperCase()}</div></div></div><div class="preview-info"><span>${escapeHtml(file.name)}</span><span>${formatFileSize(file.size)}</span></div></div>`;
        }
    });
    html += `<div class="preview-summary"><div>Files: ${files.length}</div><div>Total size: ${formatFileSize(totalSize)}</div></div>`;
    previewBody.innerHTML = html;
    document.getElementById('filePreviewModal').classList.add('active');
}

async function sendFilesWithPreview() {
    if (!activeChat || !pendingFiles.length) return;
    closeModal('filePreviewModal');

    for (const file of pendingFiles) {
        const formData = new FormData();
        formData.append('file', file);
        let url = '/files/upload_file';
        if (activeChat.type === 'personal') formData.append('receiver_id', activeChat.id);
        else if (activeChat.type === 'group') formData.append('group_id', activeChat.id);
        else if (activeChat.type === 'channel') formData.append('channel_id', activeChat.id);

        try {
            const res = await fetch(url, { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success && data.message) addMessageToView(data.message);
        } catch(e) { showToast('File upload failed', 'error'); }
    }
    pendingFiles = [];
    document.getElementById('fileInput').value = '';
}

// ==================== CONTACTS ====================
function showContactsView() {
    closePopout();
    hideAllPanels();
    document.getElementById('contactsView').style.display = 'flex';
    loadContacts();
}
function hideContactsView() {
    document.getElementById('contactsView').style.display = 'none';
    if (activeChat) document.getElementById('chatView').style.display = 'flex';
    else document.getElementById('emptyChat').style.display = 'flex';
}

async function loadContacts() {
    const list = document.getElementById('contactsList');
    list.innerHTML = '<div class="loading-spinner"></div>';
    try {
        const res = await fetch('/api/contacts');
        const data = await res.json();
        if (data.success) {
            list.innerHTML = data.contacts.map(c => `
                <div class="contact-item" onclick="openChat('personal', ${c.id})">
                    <div class="contact-avatar">
                        ${c.avatar_url ? `<img src="${c.avatar_url}" alt="">` : c.username[0].toUpperCase()}
                    </div>
                    <div class="contact-info">
                        <div class="contact-name">${escapeHtml(c.display_name)}</div>
                        <div class="contact-username">@${escapeHtml(c.username)}</div>
                    </div>
                    ${c.is_online ? '<i class="fas fa-circle" style="color:var(--online-green);"></i>' : ''}
                </div>
            `).join('');
        }
    } catch(e) { list.innerHTML = '<div class="empty-state"><p>Error loading contacts</p></div>'; }
}
function showAddContactModal() {
    alert('Add contact modal – TBD');
}

// ==================== GLOBAL SEARCH ====================
async function handleGlobalSearch() {
    const query = document.getElementById('globalSearchInput').value.trim();
    const results = document.getElementById('searchResults');
    if (query.length < 2) { results.innerHTML = ''; results.classList.remove('active'); return; }
    try {
        const res = await fetch(`/api/search/global?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data.success) {
            let html = '';
            if (data.results.users?.length) {
                html += '<div class="search-result-section">Users</div>';
                data.results.users.forEach(u => {
                    html += `<div class="search-result-item" onclick="openChat('personal', ${u.id}); closeSearchResults()">
                        <div class="search-result-avatar">${u.username[0].toUpperCase()}</div>
                        <div class="search-result-info"><div class="search-result-name">${escapeHtml(u.display_name)}</div><div class="search-result-type">@${escapeHtml(u.username)}</div></div>
                    </div>`;
                });
            }
            // groups / channels omitted for brevity – you can add them similarly
            results.innerHTML = html || '<div class="search-result-item">No results</div>';
            results.classList.add('active');
        }
    } catch(e) { console.error(e); }
}
function closeSearchResults() {
    document.getElementById('searchResults').classList.remove('active');
    document.getElementById('globalSearchInput').value = '';
}

// ==================== GROUP / CHANNEL CREATION ====================
function showCreateGroupView() {
    closePopout();
    hideAllPanels();
    document.getElementById('createGroupView').style.display = 'flex';
    selectedMembers = [];
    document.getElementById('selectedMembers').innerHTML = '';
    document.getElementById('userListForGroup').innerHTML = '';
}
function hideCreateGroupView() {
    document.getElementById('createGroupView').style.display = 'none';
    showChatsView();
}

async function createGroup() {
    const name = document.getElementById('groupName').value.trim();
    if (!name) { showToast('Group name required', 'error'); return; }
    const formData = new FormData();
    formData.append('name', name);
    formData.append('member_ids', JSON.stringify(selectedMembers));
    const avatarFile = document.getElementById('groupAvatarInput').files[0];
    if (avatarFile) formData.append('avatar', avatarFile);

    try {
        const res = await fetch('/api/groups/create', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
            showToast('Group created!', 'success');
            hideCreateGroupView();
            loadChatList();
            openChat('group', data.group.id);
        }
    } catch(e) { showToast('Error', 'error'); }
}

function triggerGroupAvatarUpload() { document.getElementById('groupAvatarInput').click(); }
function previewGroupAvatar(input) {
    if (input.files[0]) {
        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('groupAvatarPreview').innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;">`;
        };
        reader.readAsDataURL(input.files[0]);
    }
}

async function handleMemberSearch() {
    const query = document.getElementById('memberSearchInput').value.trim();
    const container = document.getElementById('userListForGroup');
    if (query.length < 2) { container.innerHTML = ''; return; }
    try {
        const res = await fetch(`/api/users?search=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data.success) {
            container.innerHTML = data.users.map(u => {
                const sel = selectedMembers.includes(u.id);
                return `<div class="user-select-item ${sel ? 'selected' : ''}" onclick="toggleMemberSelection(${u.id})">
                    <div class="user-select-avatar">${u.username[0].toUpperCase()}</div>
                    <div class="user-select-info"><div class="user-select-name">${escapeHtml(u.display_name)}</div><div class="user-select-username">@${escapeHtml(u.username)}</div></div>
                    ${sel ? '<div class="selection-indicator"><i class="fas fa-check"></i></div>' : ''}
                </div>`;
            }).join('');
        }
    } catch(e) {}
}
function toggleMemberSelection(userId) {
    const idx = selectedMembers.indexOf(userId);
    if (idx > -1) selectedMembers.splice(idx, 1);
    else selectedMembers.push(userId);
    renderSelectedMembers();
    handleMemberSearch();
}
function renderSelectedMembers() {
    const container = document.getElementById('selectedMembers');
    container.innerHTML = selectedMembers.map(id => `<span class="selected-member-tag">User #${id} <button onclick="toggleMemberSelection(${id})"><i class="fas fa-times"></i></button></span>`).join('');
}

// ---- Channel creation ----
function showCreateChannelView() {
    closePopout();
    hideAllPanels();
    document.getElementById('createChannelView').style.display = 'flex';
}
function hideCreateChannelView() {
    document.getElementById('createChannelView').style.display = 'none';
    showChatsView();
}
async function createChannel() {
    const name = document.getElementById('channelName').value.trim();
    if (!name) { showToast('Channel name required', 'error'); return; }
    const formData = new FormData();
    formData.append('name', name);
    const avatarFile = document.getElementById('channelAvatarInput').files[0];
    if (avatarFile) formData.append('avatar', avatarFile);

    try {
        const res = await fetch('/api/channels/create', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
            showToast('Channel created!', 'success');
            hideCreateChannelView();
            loadChatList();
            openChat('channel', data.channel.id);
        }
    } catch(e) { showToast('Error', 'error'); }
}
function triggerChannelAvatarUpload() { document.getElementById('channelAvatarInput').click(); }
function previewChannelAvatar(input) {
    if (input.files[0]) {
        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('channelAvatarPreview').innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;">`;
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// ==================== THEME / FONTS ====================
function setTheme(theme) {
    document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('active'));
    if (event.currentTarget) event.currentTarget.classList.add('active');
    if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
    else document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('kiselgram_theme', theme);
}

function loadThemePreference() {
    const t = localStorage.getItem('kiselgram_theme');
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
}

function setFont(element) {
    if (element.classList.contains('locked')) {
        showToast('This font requires Premium', 'error');
        return;
    }
    document.querySelectorAll('.font-option').forEach(o => o.classList.remove('active'));
    element.classList.add('active');
    document.body.style.setProperty('--font-family', element.dataset.font);
    localStorage.setItem('kiselgram_font', element.dataset.font);
    showToast('Font updated', 'success');
}

// ==================== EVENT LISTENERS ====================
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('menuBtn').addEventListener('click', togglePopoutMenu);
    document.getElementById('globalSearchInput').addEventListener('input', debounce(handleGlobalSearch, 300));
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', () => {
            document.getElementById('sendBtn').disabled = !messageInput.value.trim();
        });
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
    }
    document.addEventListener('click', (e) => {
        const search = document.querySelector('.global-search');
        if (search && !search.contains(e.target)) {
            document.getElementById('searchResults').classList.remove('active');
        }
    });

    loadThemePreference();
    loadCurrentUser().then(() => loadChatList());
});

// Periodic refresh
setInterval(() => {
    if (activeChat) loadMessages(activeChat.type, activeChat.id);
    loadChatList();
}, 10000);

// ==================== CHAT INFO / MENU ====================
function showChatInfo() {
    if (!activeChat) return;
    alert(`Chat info for ${activeChat.type} #${activeChat.id}`);
}

function showChatMenu() {
    if (!activeChat) return;
    const menu = document.createElement('div');
    menu.className = 'modal-overlay';
    menu.onclick = e => { if (e.target === menu) menu.remove(); };
    menu.innerHTML = `
        <div class="chat-menu-dropdown" style="position:fixed;top:60px;right:20px;background:var(--bg-primary);border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.2);padding:8px 0;min-width:200px;z-index:2000;border:1px solid var(--border-color);">
            <div class="chat-menu-item" onclick="showChatInfo(); this.closest('.modal-overlay').remove()"><i class="fas fa-info-circle"></i> View Info</div>
            <div class="chat-menu-item" onclick="this.closest('.modal-overlay').remove()"><i class="fas fa-paint-brush"></i> Wallpaper</div>
            <div class="chat-menu-item danger" onclick="blockUser(${activeChat.id}); this.closest('.modal-overlay').remove()"><i class="fas fa-ban"></i> Block User</div>
            <div class="chat-menu-item danger" onclick="clearChat(); this.closest('.modal-overlay').remove()"><i class="fas fa-eraser"></i> Clear Chat</div>
        </div>
    `;
    document.body.appendChild(menu);
}

async function blockUser(userId) {
    if (!confirm('Block this user?')) return;
    try {
        await fetch(`/api/block_user/${userId}`, { method: 'POST' });
        showToast('User blocked', 'success');
    } catch(e) { showToast('Error', 'error'); }
}

async function clearChat() {
    if (!activeChat || activeChat.type !== 'personal') return;
    if (!confirm('Clear entire chat history?')) return;
    try {
        await fetch(`/api/clear_chat/${activeChat.id}`, { method: 'POST' });
        document.getElementById('messagesContainer').innerHTML = '<div class="empty-state"><i class="fas fa-comment-dots"></i><p>Chat cleared</p></div>';
        showToast('Chat cleared', 'success');
    } catch(e) { showToast('Error', 'error'); }
}

function openImageViewer(url) {
    window.open(url, '_blank');
}

// Logout
function logout() {
    fetch('/api/auth/logout', { method: 'POST' }).then(() => window.location.href = '/auth/login');
}

function loadStories() {
    // no-op placeholder
}

// Expose globals needed by inline handlers or premium overrides
window.openChat = openChat;
window.showChatsView = showChatsView;
window.showContactsView = showContactsView;
window.hideContactsView = hideContactsView;
window.showCreateGroupView = showCreateGroupView;
window.hideCreateGroupView = hideCreateGroupView;
window.showCreateChannelView = showCreateChannelView;
window.hideCreateChannelView = hideCreateChannelView;
window.openPrivacyPanel = openPrivacyPanel;
window.closePrivacyPanel = closePrivacyPanel;
window.openSessionsPanel = openSessionsPanel;
window.closeSessionsPanel = closeSessionsPanel;
window.openSavedMessages = openSavedMessages;
window.setReply = setReply;
window.cancelReply = cancelReply;
window.deleteMessage = deleteMessage;
window.sendMessage = sendMessage;
window.triggerFileUpload = triggerFileUpload;
window.handleFileSelect = handleFileSelect;
window.sendFilesWithPreview = sendFilesWithPreview;
window.showToast = showToast;
window.showChatInfo = showChatInfo;
window.showChatMenu = showChatMenu;
window.openProfileModal = openProfileModal;
window.openImageViewer = openImageViewer;
window.showAddContactModal = showAddContactModal;
window.blockUser = blockUser;
window.clearChat = clearChat;
window.loadChatList = loadChatList;
window.loadStories = loadStories;   // will be overridden by free.js / premium.js
window.openStoryViewer = function() { showPremiumModal(); };
window.showCreateStoryModal = function() { showPremiumModal(); };
window.openChatCustomization = function() { showPremiumModal(); };