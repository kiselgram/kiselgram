// static/js/spa_app.js
// Kiselgram Free Version - Orange & Lime Theme

// ============ GLOBAL STATE ============

let currentUserId = null;
let currentUserUsername = '';
let currentUserDisplayName = '';
let currentUserAvatar = '?';
let isPremium = false;

// Only basic fonts available
const AVAILABLE_FONTS = ['Inter', 'Courier New'];

// App state
let activeChat = null;
let selectedMembers = [];
let replyToMessage = null;

// ============ INITIALIZATION ============

document.addEventListener('DOMContentLoaded', async () => {
    await loadCurrentUser();
    await loadChatList();
    setupEventListeners();
    loadThemePreference();
    loadFontPreference();

    setInterval(loadChatList, 30000);
    setInterval(() => {
        if (activeChat) loadMessages(activeChat.type, activeChat.id);
    }, 5000);
});

async function loadCurrentUser() {
    try {
        const response = await fetch('/api/profile');
        const data = await response.json();

        if (data.success && data.user) {
            currentUserId = data.user.id;
            currentUserUsername = data.user.username;
            currentUserDisplayName = data.user.display_name || data.user.username;
            currentUserAvatar = data.user.username[0].toUpperCase();
            updateUserUI();
        } else {
            const menuUsername = document.getElementById('menuUserUsername');
            if (menuUsername) {
                const username = menuUsername.textContent.replace('@', '');
                currentUserUsername = username;
                currentUserAvatar = username[0]?.toUpperCase() || '?';
            }
        }
    } catch (error) {
        console.error('Error loading current user:', error);
    }
}

function updateUserUI() {
    const menuAvatar = document.getElementById('menuUserAvatar');
    const menuName = document.getElementById('menuUserName');
    const menuUsername = document.getElementById('menuUserUsername');

    if (menuAvatar) menuAvatar.textContent = currentUserAvatar;
    if (menuName) menuName.textContent = currentUserDisplayName;
    if (menuUsername) menuUsername.textContent = '@' + currentUserUsername;
}

function setupEventListeners() {
    const menuBtn = document.getElementById('menuBtn');
    if (menuBtn) menuBtn.addEventListener('click', togglePopoutMenu);

    const searchInput = document.getElementById('globalSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleGlobalSearch, 300));
        searchInput.addEventListener('focus', () => {
            document.getElementById('searchResults')?.classList.add('active');
        });
    }

    document.addEventListener('click', (e) => {
        const searchContainer = document.querySelector('.global-search');
        if (searchContainer && !searchContainer.contains(e.target)) {
            document.getElementById('searchResults')?.classList.remove('active');
        }

        // Don't close edit profile modal when clicking outside
        const editModal = document.getElementById('editProfileModal');
        if (editModal && editModal.style.display === 'flex') {
            if (!editModal.querySelector('.modal-container').contains(e.target) &&
                !e.target.closest('.profile-info-item')) {
                // Do nothing - keep modal open
                return;
            }
        }
    });

    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', handleMessageInput);
        messageInput.addEventListener('keydown', handleMessageKeydown);
    }

    const contactSearch = document.getElementById('contactSearchInput');
    if (contactSearch) contactSearch.addEventListener('input', debounce(handleContactSearch, 300));

    const memberSearch = document.getElementById('memberSearchInput');
    if (memberSearch) memberSearch.addEventListener('input', debounce(handleMemberSearch, 300));
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============ POPOUT MENU ============

function togglePopoutMenu() {
    document.body.classList.toggle('popout-open');
    document.getElementById('menuBtn')?.classList.toggle('active');
}

function closePopout() {
    document.body.classList.remove('popout-open');
    document.getElementById('menuBtn')?.classList.remove('active');
}

// ============ PANELS ============

function closeAllPanels() {
    document.getElementById('settingsPanel')?.classList.remove('open');
    document.getElementById('privacyPanel')?.classList.remove('open');
    document.getElementById('panelOverlay')?.classList.remove('visible');
}

function openSettingsPanel() {
    closeAllPanels();
    document.getElementById('settingsPanel')?.classList.add('open');
    document.getElementById('panelOverlay')?.classList.add('visible');
    closePopout();
}

function closeSettingsPanel() {
    document.getElementById('settingsPanel')?.classList.remove('open');
    document.getElementById('panelOverlay')?.classList.remove('visible');
}

function openPrivacyPanel() {
    closeAllPanels();
    document.getElementById('privacyPanel')?.classList.add('open');
    document.getElementById('panelOverlay')?.classList.add('visible');
    closePopout();
}

function closePrivacyPanel() {
    document.getElementById('privacyPanel')?.classList.remove('open');
    document.getElementById('panelOverlay')?.classList.remove('visible');
}

// ============ THEME & FONT ============

function setTheme(theme) {
    document.querySelectorAll('.theme-option').forEach(opt => opt.classList.remove('active'));
    event.currentTarget.classList.add('active');

    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }

    localStorage.setItem('kiselgram_theme', theme);
}

function loadThemePreference() {
    const theme = localStorage.getItem('kiselgram_theme');
    if (theme) {
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else if (theme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
        }

        document.querySelectorAll('.theme-option').forEach(opt => {
            const text = opt.textContent.trim();
            if ((theme === 'light' && text.includes('Light')) ||
                (theme === 'dark' && text.includes('Dark')) ||
                (theme === 'auto' && text.includes('Auto'))) {
                opt.classList.add('active');
            }
        });
    }
}

function setFont(element) {
    const fontName = element.querySelector('.font-name')?.textContent.split(' ')[0];

    // Check if font is locked
    if (element.classList.contains('locked')) {
        showToast('🔒 This font requires Kiselgram Premium', 'error');
        showPremiumModal('fonts');
        return;
    }

    document.querySelectorAll('.font-option').forEach(opt => opt.classList.remove('active'));
    element.classList.add('active');

    const fontFamily = element.dataset.font;
    document.body.style.setProperty('--font-family', fontFamily);
    localStorage.setItem('kiselgram_font', fontFamily);
    showToast('Font updated', 'success');
}

function loadFontPreference() {
    const savedFont = localStorage.getItem('kiselgram_font');
    if (savedFont) {
        document.body.style.setProperty('--font-family', savedFont);
        document.querySelectorAll('.font-option').forEach(opt => {
            if (opt.dataset.font === savedFont) {
                opt.classList.add('active');
            }
        });
    }
}

function toggleSetting(element, setting) {
    element.classList.toggle('active');
    const isEnabled = element.classList.contains('active');
    localStorage.setItem(`kiselgram_${setting}`, isEnabled);
}

// ============ PREMIUM MODAL ============

function showPremiumModal(feature = 'feature') {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.display = 'flex';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

    const messages = {
        'fonts': 'Unlock 9+ premium fonts including Satoshi, DM Sans, Poppins, and more!',
        'stories': 'Stories are a premium feature. Share moments that disappear after 24 hours!',
        'wallpapers': 'Custom chat wallpapers are available with Kiselgram Premium!',
        'feature': 'This feature is available with Kiselgram Premium!'
    };

    modal.innerHTML = `
        <div class="modal-container premium-modal" style="max-width: 400px;">
            <div class="modal-header" style="background: linear-gradient(135deg, #fb6340, #2dce89); color: white;">
                <h3>🍊 Kiselgram Premium 🍋</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color: white;">✕</button>
            </div>
            <div class="modal-body" style="text-align: center; padding: 24px;">
                <div style="font-size: 48px; margin-bottom: 16px;">👑</div>
                <p style="font-size: 16px; margin-bottom: 20px;">${messages[feature] || messages.feature}</p>

                <div style="background: linear-gradient(135deg, rgba(251, 99, 64, 0.1), rgba(45, 206, 137, 0.1)); border-radius: 16px; padding: 16px; margin-bottom: 20px;">
                    <h4 style="margin-bottom: 12px;">Premium Benefits:</h4>
                    <ul style="text-align: left; color: var(--text-secondary);">
                        <li>✨ 11 Premium Fonts</li>
                        <li>📸 Stories Feature</li>
                        <li>🎨 Custom Chat Wallpapers</li>
                        <li>💬 Priority Support</li>
                        <li>🔮 Early Access to New Features</li>
                    </ul>
                </div>

                <p style="font-size: 24px; font-weight: 700; margin-bottom: 20px; background: linear-gradient(135deg, #fb6340, #2dce89); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    $4.99/month
                </p>
            </div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-secondary" onclick="this.closest('.modal-overlay').remove()">Maybe Later</button>
                <button class="modal-btn modal-btn-primary" onclick="goToPremium()" style="background: linear-gradient(135deg, #fb6340, #2dce89);">
                    Upgrade Now 🍊
                </button>
            </div>
        </div>
    `;

    document.getElementById('modalRoot').appendChild(modal);
}

function goToPremium() {
    window.location.href = '/premium';
}

// ============ TOAST NOTIFICATIONS ============

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'success' ? '#2dce89' : type === 'error' ? '#fb6340' : '#fb6340'};
        color: white;
        padding: 12px 24px;
        border-radius: 30px;
        font-weight: 500;
        z-index: 9999;
        box-shadow: var(--shadow-lg);
        animation: fadeIn 0.3s ease;
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============ CHAT LIST ============

async function loadChatList() {
    try {
        const response = await fetch('/api/chat_list');
        const data = await response.json();

        if (data.success) {
            renderChatList(data.chats);
        }
    } catch (error) {
        console.error('Error loading chat list:', error);
    }
}

function renderChatList(chats) {
    const chatList = document.getElementById('chatList');
    if (!chatList) return;

    if (!chats || chats.length === 0) {
        chatList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">💬</div>
                <p>No chats yet</p>
                <p style="font-size: 13px; margin-top: 8px;">Start a conversation from Contacts</p>
            </div>
        `;
        return;
    }

    let html = '';

    for (const chat of chats) {
        const isActive = activeChat && activeChat.type === chat.type && activeChat.id === chat.id;

        let avatarHtml = '';
        if (chat.avatar_url) {
            avatarHtml = `<img src="${chat.avatar_url}" alt="${escapeHtml(chat.name)}">`;
        } else {
            avatarHtml = chat.avatar || '?';
        }

        let statusHtml = '';
        if (chat.type === 'personal' && chat.is_online) {
            statusHtml = '<span class="online-indicator"></span>';
        }

        let unreadHtml = '';
        if (chat.unread_count > 0) {
            unreadHtml = `<span class="unread-badge">${chat.unread_count}</span>`;
        }

        html += `
            <div class="chat-item ${isActive ? 'active' : ''}"
                 data-chat-type="${chat.type}"
                 data-chat-id="${chat.id}"
                 data-user-id="${chat.type === 'personal' ? chat.id : ''}"
                 onclick="openChat('${chat.type}', ${chat.id})">
                <div class="chat-avatar ${chat.type}">
                    ${avatarHtml}
                    ${statusHtml}
                </div>
                <div class="chat-info">
                    <div class="chat-name-row">
                        <span class="chat-name">${escapeHtml(chat.name)}</span>
                        <span class="chat-time">${chat.timestamp || ''}</span>
                    </div>
                    <div class="chat-preview">
                        <span>${escapeHtml(chat.last_message || '')}</span>
                        ${unreadHtml}
                    </div>
                </div>
            </div>
        `;
    }

    chatList.innerHTML = html;
}

// ============ CHAT VIEW ============

function hideAllPanels() {
    document.getElementById('emptyChat').style.display = 'none';
    document.getElementById('chatView').style.display = 'none';
    document.getElementById('contactsView').style.display = 'none';
    document.getElementById('createGroupView').style.display = 'none';
    document.getElementById('createChannelView').style.display = 'none';
}

async function openChat(type, id) {
    activeChat = { type, id };

    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`.chat-item[data-chat-type="${type}"][data-chat-id="${id}"]`)?.classList.add('active');

    hideAllPanels();
    document.getElementById('chatView').style.display = 'flex';

    await loadChatInfo(type, id);
    await loadMessages(type, id);

    if (type === 'personal') {
        await fetch(`/api/mark_read/${id}`, { method: 'POST' });
    }

    document.getElementById('messageInput')?.focus();
}

async function loadChatInfo(type, id) {
    try {
        let info = null;

        if (type === 'personal') {
            const response = await fetch('/api/users');
            const data = await response.json();
            info = data.users?.find(u => u.id === id);
        }

        const headerAvatar = document.getElementById('chatHeaderAvatar');
        const headerName = document.getElementById('chatHeaderName');
        const headerStatus = document.getElementById('chatHeaderStatus');

        if (info) {
            headerName.textContent = info.display_name || info.username;
            headerStatus.textContent = info.is_online ? 'Online' : 'Offline';
            headerStatus.classList.toggle('online', info.is_online);

            if (info.avatar_url) {
                headerAvatar.innerHTML = `<img src="${info.avatar_url}" alt="${info.display_name}">`;
            } else {
                headerAvatar.textContent = info.username[0].toUpperCase();
            }
            headerAvatar.className = `chat-header-avatar ${type}`;
        } else {
            headerName.textContent = type === 'personal' ? 'Chat' : (type === 'group' ? 'Group' : 'Channel');
            headerAvatar.textContent = type === 'personal' ? '💬' : (type === 'group' ? '👥' : '📢');
            headerAvatar.className = `chat-header-avatar ${type}`;
        }
    } catch (error) {
        console.error('Error loading chat info:', error);
    }
}

async function loadMessages(type, id, afterId = 0) {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = '<div class="loading-messages"><div class="loading-spinner"></div><p>Loading messages...</p></div>';

    try {
        let url = '';
        if (type === 'personal') url = `/api/messages/${id}`;
        else if (type === 'group') url = `/api/group_messages/${id}`;
        else if (type === 'channel') url = `/api/channel_messages/${id}`;

        const response = await fetch(`${url}?after=${afterId}&limit=50`);
        const data = await response.json();

        if (data.success && data.messages) {
            renderMessages(data.messages);
        } else {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No messages yet</p></div>';
        }
    } catch (error) {
        console.error('Error loading messages:', error);
        container.innerHTML = '<div class="empty-state"><p>Error loading messages</p></div>';
    }
}

function renderMessages(messages) {
    const container = document.getElementById('messagesContainer');

    if (!messages || messages.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">💬</div>
                <p>No messages yet</p>
                <p style="font-size: 13px;">Send a message to start the conversation</p>
            </div>
        `;
        return;
    }

    let html = '';
    let lastDate = null;

    for (const msg of messages) {
        const msgDate = msg.timestamp ? new Date(msg.timestamp) : new Date();
        const dateStr = msgDate.toLocaleDateString();

        if (dateStr !== lastDate) {
            html += `<div class="message-date-divider">${formatDateDivider(msgDate)}</div>`;
            lastDate = dateStr;
        }

        html += renderMessage(msg);
    }

    container.innerHTML = html;
    scrollToBottom();
}

function renderMessage(msg) {
    const isOwn = msg.is_own || msg.sender_id === currentUserId;
    const wrapperClass = isOwn ? 'outgoing' : 'incoming';

    let attachmentHtml = '';
    if (msg.has_attachment) {
        if (msg.file_type === 'image') {
            attachmentHtml = `<img src="${msg.file_url}" alt="${msg.file_name || 'Image'}" class="message-image" onclick="openImageViewer('${msg.file_url}')">`;
        } else {
            attachmentHtml = `
                <div class="file-attachment">
                    <span>📎</span>
                    <a href="${msg.file_url}" target="_blank" class="file-link">${msg.file_name || 'File'}</a>
                </div>
            `;
        }
    }

    return `
        <div class="message-wrapper ${wrapperClass}" data-message-id="${msg.id}" id="msg-${msg.id}">
            ${!isOwn ? `<div class="message-sender">${escapeHtml(msg.sender_name || 'User')}</div>` : ''}
            <div class="message-bubble">
                ${attachmentHtml}
                ${msg.content ? `<div class="message-text">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>` : ''}
                <div class="message-meta">
                    <span class="message-time">${msg.timestamp_formatted || ''}</span>
                    ${isOwn ? `<span class="message-status">${msg.is_read ? '✓✓' : '✓'}</span>` : ''}
                </div>
            </div>
            <div class="message-actions">
                <span class="action-icon" onclick="setReply(${msg.id})">↩️</span>
                ${isOwn ? `<span class="action-icon" onclick="deleteMessage(${msg.id})">🗑️</span>` : ''}
            </div>
        </div>
    `;
}

function formatDateDivider(date) {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString(undefined, { month: 'long', day: 'numeric' });
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    if (container) container.scrollTop = container.scrollHeight;
}

// ============ SEND MESSAGE ============

function handleMessageInput() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    if (input && sendBtn) {
        sendBtn.disabled = !input.value.trim();
    }
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 100) + 'px';
}

function handleMessageKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();

    if (!content || !activeChat) return;

    let url = '';
    const payload = { content };

    if (activeChat.type === 'personal') {
        url = '/api/send_message';
        payload.receiver_id = activeChat.id;
    } else if (activeChat.type === 'group') {
        url = '/api/send_group_message';
        payload.group_id = activeChat.id;
    } else if (activeChat.type === 'channel') {
        url = '/api/send_channel_message';
        payload.channel_id = activeChat.id;
    }

    if (replyToMessage) {
        payload.reply_to_id = replyToMessage;
        cancelReply();
    }

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.success) {
            input.value = '';
            handleMessageInput();
            addMessageToView(data.message);
            loadChatList();
        } else {
            showToast(data.error || 'Failed to send message', 'error');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        showToast('Error sending message', 'error');
    }
}

function addMessageToView(message) {
    const container = document.getElementById('messagesContainer');
    const existingEmpty = container.querySelector('.empty-state');
    if (existingEmpty) container.innerHTML = '';

    container.insertAdjacentHTML('beforeend', renderMessage(message));
    scrollToBottom();
}

function setReply(messageId) {
    const msgElement = document.getElementById(`msg-${messageId}`);
    if (!msgElement) return;

    replyToMessage = messageId;

    const text = msgElement.querySelector('.message-text')?.textContent || 'Message';
    const preview = document.getElementById('replyPreview');
    if (preview) {
        preview.querySelector('.reply-preview-name').textContent = 'Replying to message';
        preview.querySelector('.reply-preview-text').textContent = text.substring(0, 50) + (text.length > 50 ? '...' : '');
        preview.style.display = 'flex';
    }

    document.getElementById('messageInput')?.focus();
}

function cancelReply() {
    replyToMessage = null;
    const preview = document.getElementById('replyPreview');
    if (preview) preview.style.display = 'none';
}

async function deleteMessage(messageId) {
    if (!confirm('Delete this message?')) return;

    try {
        const response = await fetch(`/api/messages/${messageId}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            document.getElementById(`msg-${messageId}`)?.remove();
            showToast('Message deleted', 'success');
        }
    } catch (error) {
        console.error('Error deleting message:', error);
        showToast('Error deleting message', 'error');
    }
}

function openImageViewer(url) {
    window.open(url, '_blank');
}

// ============ STORIES (Premium Only) ============

function loadStories() {
    // Stories are premium only
    const storiesRow = document.getElementById('storiesRow');
    if (storiesRow) {
        storiesRow.innerHTML = `
            <div class="story-item locked-story" onclick="showPremiumModal('stories')">
                <div class="story-avatar add-story locked">
                    <div class="add-story-btn">🔒</div>
                </div>
                <span class="story-username">Premium</span>
            </div>
            <div style="display: flex; align-items: center; padding: 8px 16px; color: var(--text-muted); font-size: 13px;">
                <span>🔒 Stories require Premium</span>
            </div>
        `;
    }
}

function renderStoriesRow() {
    loadStories();
}

function showCreateStoryModal() {
    showPremiumModal('stories');
}

// ============ CONTACTS ============

function showContactsView() {
    closePopout();
    hideAllPanels();
    document.getElementById('contactsView').style.display = 'flex';
    loadContacts();
}

function hideContactsView() {
    document.getElementById('contactsView').style.display = 'none';
    if (activeChat) {
        document.getElementById('chatView').style.display = 'flex';
    } else {
        document.getElementById('emptyChat').style.display = 'flex';
    }
}

async function loadContacts() {
    const container = document.getElementById('contactsList');
    container.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const response = await fetch('/api/contacts');
        const data = await response.json();

        if (data.success) {
            renderContacts(data.contacts);
        }
    } catch (error) {
        console.error('Error loading contacts:', error);
        container.innerHTML = '<div class="empty-state"><p>Error loading contacts</p></div>';
    }
}

function renderContacts(contacts) {
    const container = document.getElementById('contactsList');

    if (!contacts || contacts.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">👥</div>
                <p>No contacts yet</p>
                <p style="font-size: 13px;">Start a conversation to add contacts</p>
            </div>
        `;
        return;
    }

    let html = '';
    for (const contact of contacts) {
        html += `
            <div class="contact-item" onclick="openChat('personal', ${contact.id})">
                <div class="contact-avatar">
                    ${contact.avatar_url ?
                        `<img src="${contact.avatar_url}" alt="${contact.display_name}">` :
                        contact.username[0].toUpperCase()
                    }
                </div>
                <div class="contact-info">
                    <div class="contact-name">${escapeHtml(contact.display_name)}</div>
                    <div class="contact-username">@${escapeHtml(contact.username)}</div>
                </div>
                ${contact.is_online ? '<span class="online-badge">●</span>' : ''}
            </div>
        `;
    }

    container.innerHTML = html;
}

function handleContactSearch() {
    const query = document.getElementById('contactSearchInput').value.toLowerCase();

    document.querySelectorAll('.contact-item').forEach(item => {
        const name = item.querySelector('.contact-name')?.textContent.toLowerCase() || '';
        const username = item.querySelector('.contact-username')?.textContent.toLowerCase() || '';
        item.style.display = (name.includes(query) || username.includes(query)) ? 'flex' : 'none';
    });
}

// ============ GLOBAL SEARCH ============

async function handleGlobalSearch() {
    const query = document.getElementById('globalSearchInput').value.trim();
    const resultsContainer = document.getElementById('searchResults');

    if (query.length < 2) {
        resultsContainer.innerHTML = '';
        resultsContainer.classList.remove('active');
        return;
    }

    try {
        const response = await fetch(`/api/search/global?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.success) {
            renderSearchResults(data.results);
            resultsContainer.classList.add('active');
        }
    } catch (error) {
        console.error('Error searching:', error);
    }
}

function renderSearchResults(results) {
    const container = document.getElementById('searchResults');
    const { users, groups, channels } = results;

    if (!users?.length && !groups?.length && !channels?.length) {
        container.innerHTML = '<div class="search-result-item" style="cursor: default;">No results found</div>';
        return;
    }

    let html = '';

    if (users?.length) {
        html += '<div class="search-result-section">Users</div>';
        for (const user of users) {
            html += `
                <div class="search-result-item" onclick="openChat('personal', ${user.id}); closeSearchResults()">
                    <div class="search-result-avatar">${user.username[0].toUpperCase()}</div>
                    <div class="search-result-info">
                        <div class="search-result-name">${escapeHtml(user.display_name)}</div>
                        <div class="search-result-type">@${escapeHtml(user.username)}</div>
                    </div>
                </div>
            `;
        }
    }

    if (groups?.length) {
        html += '<div class="search-result-section">Groups</div>';
        for (const group of groups) {
            html += `
                <div class="search-result-item" onclick="openChat('group', ${group.id}); closeSearchResults()">
                    <div class="search-result-avatar">👥</div>
                    <div class="search-result-info">
                        <div class="search-result-name">${escapeHtml(group.name)}</div>
                        <div class="search-result-type">Group</div>
                    </div>
                </div>
            `;
        }
    }

    if (channels?.length) {
        html += '<div class="search-result-section">Channels</div>';
        for (const channel of channels) {
            html += `
                <div class="search-result-item" onclick="openChat('channel', ${channel.id}); closeSearchResults()">
                    <div class="search-result-avatar">📢</div>
                    <div class="search-result-info">
                        <div class="search-result-name">${escapeHtml(channel.name)}</div>
                        <div class="search-result-type">Channel</div>
                    </div>
                </div>
            `;
        }
    }

    container.innerHTML = html;
}

function closeSearchResults() {
    document.getElementById('searchResults')?.classList.remove('active');
    document.getElementById('globalSearchInput').value = '';
}

// ============ CREATE GROUP ============

function showCreateGroupView() {
    closePopout();
    hideAllPanels();
    document.getElementById('createGroupView').style.display = 'flex';
    selectedMembers = [];
    updateSelectedMembersDisplay();
}

function hideCreateGroupView() {
    document.getElementById('createGroupView').style.display = 'none';
}

async function handleMemberSearch() {
    const query = document.getElementById('memberSearchInput').value.trim();
    const container = document.getElementById('userListForGroup');

    if (query.length < 2) {
        container.innerHTML = '';
        return;
    }

    try {
        const response = await fetch(`/api/users?search=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.success) {
            renderUserSelectList(data.users, container);
        }
    } catch (error) {
        console.error('Error searching users:', error);
    }
}

function renderUserSelectList(users, container) {
    let html = '';

    for (const user of users) {
        if (user.id === currentUserId) continue;

        const isSelected = selectedMembers.includes(user.id);

        html += `
            <div class="user-select-item ${isSelected ? 'selected' : ''}" onclick="toggleMemberSelection(${user.id})">
                <div class="user-select-avatar">${user.username[0].toUpperCase()}</div>
                <div class="user-select-info">
                    <div class="user-select-name">${escapeHtml(user.display_name)}</div>
                    <div class="user-select-username">@${escapeHtml(user.username)}</div>
                </div>
                ${isSelected ? '<div class="selection-indicator">✓</div>' : ''}
            </div>
        `;
    }

    container.innerHTML = html;
}

function toggleMemberSelection(userId) {
    const index = selectedMembers.indexOf(userId);

    if (index > -1) {
        selectedMembers.splice(index, 1);
    } else {
        selectedMembers.push(userId);
    }

    updateSelectedMembersDisplay();
    handleMemberSearch();
}

function updateSelectedMembersDisplay() {
    const container = document.getElementById('selectedMembers');

    if (selectedMembers.length === 0) {
        container.innerHTML = '';
        return;
    }

    let html = '';
    for (const userId of selectedMembers) {
        html += `
            <div class="selected-member-tag">
                User #${userId}
                <button onclick="toggleMemberSelection(${userId})">✕</button>
            </div>
        `;
    }

    container.innerHTML = html;
}

async function createGroup() {
    const name = document.getElementById('groupName').value.trim();
    const description = document.getElementById('groupDescription').value.trim();
    const isPublic = document.getElementById('groupIsPublic').checked;

    if (!name) {
        showToast('Please enter a group name', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('is_public', isPublic);
    formData.append('member_ids', JSON.stringify(selectedMembers));

    const avatarInput = document.getElementById('groupAvatarInput');
    if (avatarInput.files[0]) {
        formData.append('avatar', avatarInput.files[0]);
    }

    try {
        const response = await fetch('/api/groups/create', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast('Group created successfully!', 'success');
            hideCreateGroupView();
            loadChatList();
            openChat('group', data.group.id);
        } else {
            showToast(data.error || 'Failed to create group', 'error');
        }
    } catch (error) {
        console.error('Error creating group:', error);
        showToast('Error creating group', 'error');
    }
}

function triggerGroupAvatarUpload() {
    document.getElementById('groupAvatarInput').click();
}

function previewGroupAvatar(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const preview = document.getElementById('groupAvatarPreview');
        preview.innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
    };
    reader.readAsDataURL(file);
}

// ============ CREATE CHANNEL ============

function showCreateChannelView() {
    closePopout();
    hideAllPanels();
    document.getElementById('createChannelView').style.display = 'flex';
}

function hideCreateChannelView() {
    document.getElementById('createChannelView').style.display = 'none';
}

async function createChannel() {
    const name = document.getElementById('channelName').value.trim();
    const description = document.getElementById('channelDescription').value.trim();
    const isPublic = document.getElementById('channelIsPublic').checked;

    if (!name) {
        showToast('Please enter a channel name', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('is_public', isPublic);

    const avatarInput = document.getElementById('channelAvatarInput');
    if (avatarInput.files[0]) {
        formData.append('avatar', avatarInput.files[0]);
    }

    try {
        const response = await fetch('/api/channels/create', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast('Channel created successfully!', 'success');
            hideCreateChannelView();
            loadChatList();
            openChat('channel', data.channel.id);
        } else {
            showToast(data.error || 'Failed to create channel', 'error');
        }
    } catch (error) {
        console.error('Error creating channel:', error);
        showToast('Error creating channel', 'error');
    }
}

function triggerChannelAvatarUpload() {
    document.getElementById('channelAvatarInput').click();
}

function previewChannelAvatar(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const preview = document.getElementById('channelAvatarPreview');
        preview.innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
    };
    reader.readAsDataURL(file);
}

// ============ PROFILE MODAL ============

function openProfileModal() {
    document.getElementById('profileModal').style.display = 'flex';
    loadProfileData();
}

function closeProfileModal() {
    document.getElementById('profileModal').style.display = 'none';
}

async function loadProfileData() {
    try {
        const response = await fetch('/api/profile');
        const data = await response.json();

        if (data.success && data.user) {
            const user = data.user;

            document.getElementById('profileDisplayName').textContent = user.display_name;
            document.getElementById('profileUsername').textContent = '@' + user.username;
            document.getElementById('profileBio').textContent = user.bio || 'No bio yet';
            document.getElementById('profileDisplayNameValue').textContent = user.display_name;
            document.getElementById('profileUsernameValue').textContent = '@' + user.username;
            document.getElementById('profileBioValue').textContent = user.bio || 'No bio yet';

            const avatar = document.getElementById('profileAvatar');
            if (user.avatar_url) {
                avatar.innerHTML = `<img src="${user.avatar_url}" alt="${user.display_name}" class="profile-avatar">`;
            } else {
                avatar.innerHTML = `<div class="profile-avatar-placeholder">${user.username[0].toUpperCase()}</div>`;
            }

            document.getElementById('followersCount').textContent = user.followers_count || 0;
            document.getElementById('followingCount').textContent = user.following_count || 0;
            document.getElementById('groupsCount').textContent = user.groups_count || 0;
        }
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

function openEditProfileModal() {
    const displayName = document.getElementById('profileDisplayNameValue').textContent;
    const username = document.getElementById('profileUsernameValue').textContent.replace('@', '');
    const bio = document.getElementById('profileBioValue').textContent;

    document.getElementById('editDisplayName').value = displayName;
    document.getElementById('editUsername').value = username;
    document.getElementById('editBio').value = bio === 'No bio yet' ? '' : bio;
    document.getElementById('bioCharCount').textContent = bio === 'No bio yet' ? 0 : bio.length;

    document.getElementById('editProfileModal').style.display = 'flex';

    document.getElementById('editBio').addEventListener('input', function() {
        document.getElementById('bioCharCount').textContent = this.value.length;
    });
}

function closeEditProfileModal() {
    // Only close if clicking the close button or cancel
    document.getElementById('editProfileModal').style.display = 'none';
}

async function saveProfile() {
    const displayName = document.getElementById('editDisplayName').value.trim();
    const username = document.getElementById('editUsername').value.trim();
    const bio = document.getElementById('editBio').value.trim();

    try {
        const response = await fetch('/api/profile/update', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ display_name: displayName, username, bio })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Profile updated!', 'success');
            closeEditProfileModal();
            currentUserDisplayName = displayName;
            currentUserUsername = username;
            updateUserUI();
            openProfileModal();
        } else {
            showToast(data.error || 'Failed to update profile', 'error');
        }
    } catch (error) {
        console.error('Error updating profile:', error);
        showToast('Error updating profile', 'error');
    }
}

function triggerAvatarUpload() {
    document.getElementById('avatarInput').click();
}

async function uploadAvatar(input) {
    const file = input.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('avatar', file);

    try {
        const response = await fetch('/files/upload_avatar', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast('Avatar updated!', 'success');
            currentUserAvatar = currentUserUsername[0].toUpperCase();
            updateUserUI();
            loadProfileData();
        } else {
            showToast(data.error || 'Failed to upload avatar', 'error');
        }
    } catch (error) {
        console.error('Error uploading avatar:', error);
        showToast('Error uploading avatar', 'error');
    }
}

// ============ FILE UPLOAD ============

function triggerFileUpload() {
    document.getElementById('fileInput').click();
}

function handleFileSelect(input) {
    const files = input.files;
    if (files.length === 0) return;

    const uploadArea = document.getElementById('uploadArea');
    const fileName = document.getElementById('uploadFileName');

    if (files.length === 1) {
        fileName.textContent = files[0].name;
    } else {
        fileName.textContent = `${files.length} files selected`;
    }

    uploadArea.classList.add('active');
}

async function uploadFile() {
    const input = document.getElementById('fileInput');
    const files = input.files;

    if (files.length === 0 || !activeChat) {
        cancelUpload();
        return;
    }

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        if (activeChat.type === 'personal') {
            formData.append('receiver_id', activeChat.id);
        } else if (activeChat.type === 'group') {
            formData.append('group_id', activeChat.id);
        } else if (activeChat.type === 'channel') {
            formData.append('channel_id', activeChat.id);
        }

        try {
            const response = await fetch('/files/upload_file', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                addMessageToView(data.message);
                loadChatList();
            } else {
                showToast(data.error || 'Failed to upload file', 'error');
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            showToast('Error uploading file', 'error');
        }
    }

    cancelUpload();
}

function cancelUpload() {
    document.getElementById('uploadArea').classList.remove('active');
    document.getElementById('fileInput').value = '';
}

// ============ CHAT CUSTOMIZATION (Premium Only) ============

function openChatCustomization() {
    showPremiumModal('wallpapers');
}

function setWallpaper(wallpaper) {
    showPremiumModal('wallpapers');
}

// ============ CHAT INFO & MENU ============

function showChatInfo() {
    if (!activeChat) {
        showToast('No chat selected', 'info');
        return;
    }

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.display = 'flex';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

    modal.innerHTML = `
        <div class="modal-container" style="max-width: 400px;">
            <div class="modal-header">
                <h3>Chat Info</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="modal-body" id="chatInfoBody">
                <div class="loading-spinner"></div>
            </div>
            <div class="modal-footer">
                ${activeChat.type === 'personal' ? `
                    <button class="modal-btn modal-btn-danger" onclick="blockUser(${activeChat.id}); this.closest('.modal-overlay').remove()">Block User</button>
                    <button class="modal-btn modal-btn-secondary" onclick="clearChat(${activeChat.id}); this.closest('.modal-overlay').remove()">Clear Chat</button>
                ` : ''}
                ${activeChat.type === 'group' ? `
                    <button class="modal-btn modal-btn-danger" onclick="leaveGroup(${activeChat.id}); this.closest('.modal-overlay').remove()">Leave Group</button>
                ` : ''}
                ${activeChat.type === 'channel' ? `
                    <button class="modal-btn modal-btn-secondary" onclick="leaveChannel(${activeChat.id}); this.closest('.modal-overlay').remove()">Unsubscribe</button>
                ` : ''}
            </div>
        </div>
    `;

    document.getElementById('modalRoot').appendChild(modal);
    loadChatInfoDetails(activeChat.type, activeChat.id);
}

async function loadChatInfoDetails(type, id) {
    const body = document.getElementById('chatInfoBody');

    try {
        if (type === 'personal') {
            const response = await fetch('/api/users');
            const data = await response.json();
            const user = data.users?.find(u => u.id === id);

            if (user) {
                body.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; padding: 20px;">
                        <div style="width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #fb6340, #2dce89); display: flex; align-items: center; justify-content: center; font-size: 40px; color: white; margin-bottom: 16px;">
                            ${user.username[0].toUpperCase()}
                        </div>
                        <h3>${escapeHtml(user.display_name)}</h3>
                        <p style="color: var(--text-muted);">@${escapeHtml(user.username)}</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading chat info:', error);
        body.innerHTML = '<p>Error loading info</p>';
    }
}

async function blockUser(userId) {
    if (!confirm('Block this user?')) return;

    try {
        const response = await fetch(`/api/block_user/${userId}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('User blocked', 'success');
            activeChat = null;
            document.getElementById('emptyChat').style.display = 'flex';
            document.getElementById('chatView').style.display = 'none';
            loadChatList();
        }
    } catch (error) {
        console.error('Error blocking user:', error);
    }
}

async function clearChat(userId) {
    if (!confirm('Clear chat history?')) return;

    try {
        const response = await fetch(`/api/clear_chat/${userId}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Chat cleared', 'success');
            if (activeChat?.type === 'personal' && activeChat.id === userId) {
                document.getElementById('messagesContainer').innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><p>No messages yet</p></div>';
            }
            loadChatList();
        }
    } catch (error) {
        console.error('Error clearing chat:', error);
    }
}

async function leaveGroup(groupId) {
    if (!confirm('Leave this group?')) return;

    try {
        const response = await fetch(`/api/leave_group/${groupId}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Left group', 'success');
            activeChat = null;
            document.getElementById('emptyChat').style.display = 'flex';
            document.getElementById('chatView').style.display = 'none';
            loadChatList();
        }
    } catch (error) {
        console.error('Error leaving group:', error);
    }
}

async function leaveChannel(channelId) {
    if (!confirm('Unsubscribe from this channel?')) return;

    try {
        const response = await fetch(`/api/leave_channel/${channelId}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Unsubscribed', 'success');
            activeChat = null;
            document.getElementById('emptyChat').style.display = 'flex';
            document.getElementById('chatView').style.display = 'none';
            loadChatList();
        }
    } catch (error) {
        console.error('Error leaving channel:', error);
    }
}

function showChatMenu() {
    if (!activeChat) return;

    const menu = document.createElement('div');
    menu.className = 'modal-overlay';
    menu.onclick = (e) => { if (e.target === menu) menu.remove(); };

    menu.innerHTML = `
        <div class="chat-menu-dropdown" style="position: fixed; top: 60px; right: 20px; background: var(--bg-secondary); border-radius: 12px; box-shadow: var(--shadow-lg); border: 1px solid var(--border-color); padding: 8px 0; min-width: 200px; z-index: 2000;">
            <div class="chat-menu-item" onclick="showChatInfo(); this.closest('.modal-overlay').remove()">
                <span>ℹ️</span> View Info
            </div>
            <div class="chat-menu-item locked" onclick="showPremiumModal('wallpapers'); this.closest('.modal-overlay').remove()">
                <span>🎨</span> Customize Chat <span style="margin-left: auto; font-size: 12px; opacity: 0.7;">🔒</span>
            </div>
            ${activeChat.type === 'personal' ? `
                <div class="chat-menu-divider"></div>
                <div class="chat-menu-item danger" onclick="blockUser(${activeChat.id}); this.closest('.modal-overlay').remove()">
                    <span>🚫</span> Block User
                </div>
                <div class="chat-menu-item danger" onclick="clearChat(${activeChat.id}); this.closest('.modal-overlay').remove()">
                    <span>🗑️</span> Clear Chat
                </div>
            ` : ''}
        </div>
    `;

    document.body.appendChild(menu);
}

function showAddContactModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.display = 'flex';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

    modal.innerHTML = `
        <div class="modal-container" style="max-width: 400px;">
            <div class="modal-header">
                <h3>Add Contact</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="modal-body">
                <label class="modal-label">Search by username</label>
                <input type="text" id="addContactSearch" class="modal-input" placeholder="Enter username...">
                <div id="addContactResults" style="max-height: 300px; overflow-y: auto;"></div>
            </div>
        </div>
    `;

    document.getElementById('modalRoot').appendChild(modal);

    const searchInput = document.getElementById('addContactSearch');
    searchInput.addEventListener('input', debounce(async () => {
        const query = searchInput.value.trim();
        if (query.length < 2) {
            document.getElementById('addContactResults').innerHTML = '';
            return;
        }

        try {
            const response = await fetch(`/api/users?search=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success) {
                const results = document.getElementById('addContactResults');
                results.innerHTML = data.users.map(user => `
                    <div class="contact-item" style="cursor: pointer;" onclick="startChatWithUser(${user.id}); this.closest('.modal-overlay').remove()">
                        <div class="contact-avatar">${user.username[0].toUpperCase()}</div>
                        <div class="contact-info">
                            <div class="contact-name">${escapeHtml(user.display_name)}</div>
                            <div class="contact-username">@${escapeHtml(user.username)}</div>
                        </div>
                    </div>
                `).join('');
            }
        } catch (error) {
            console.error('Error searching users:', error);
        }
    }, 300));

    searchInput.focus();
}

function startChatWithUser(userId) {
    openChat('personal', userId);
}

function showFollowers() {
    showToast('Followers feature coming soon', 'info');
}

function showFollowing() {
    showToast('Following feature coming soon', 'info');
}

function showGroups() {
    showToast('Groups feature coming soon', 'info');
}

function savePrivacySettings() {
    showToast('Privacy settings saved', 'success');
    closePrivacyPanel();
}

function toggleMobileSidebar() {
    document.getElementById('chatSidebar')?.classList.toggle('mobile-visible');
}

// ============ UTILITY ============

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function logout() {
    fetch('/api/auth/logout', { method: 'POST' })
        .then(() => window.location.href = '/login')
        .catch(() => window.location.href = '/login');
}

function closeAllModals() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
    document.getElementById('profileModal').style.display = 'none';
    document.getElementById('editProfileModal').style.display = 'none';
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAllModals();
    }
});

// Prevent closing edit profile modal when clicking outside
document.addEventListener('click', (e) => {
    const editModal = document.getElementById('editProfileModal');
    if (editModal && editModal.style.display === 'flex') {
        if (!editModal.querySelector('.modal-container').contains(e.target) &&
            !e.target.closest('.profile-info-item') &&
            !e.target.closest('.modal-btn')) {
            e.stopPropagation();
        }
    }
});