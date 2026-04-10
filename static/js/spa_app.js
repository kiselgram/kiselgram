/* static/js/spa_app.js - Kiselgram V3.1 SPA Application */

// ============ GLOBAL STATE ============
let currentUser = null;
let currentChat = null;
let currentChatType = null;
let currentView = 'empty';
let currentChatId = null;
let chatsList = [];
let contactsList = [];
let usersList = [];
let storiesList = [];
let selectedMembers = new Set();
let replyToMsg = null;
let selectedFile = null;
let groupAvatarFile = null;
let channelAvatarFile = null;
let pollingInterval = null;
let messagePollingInterval = null;
let lastMessageId = 0;
let isLoadingMessages = false;
let chatSettings = {
    fontSize: 'medium',
    borderRadius: '18px',
    fontFamily: "'Segoe UI', Roboto, sans-serif",
    ownMessageColor: '#5e72e4',
    otherMessageColor: '#ffffff',
    wallpaper: null
};

// ============ INITIALIZATION ============
document.addEventListener('DOMContentLoaded', function() {
    initMenu();
    loadUserProfile();
    loadChats();
    loadStories();
    initTheme();
    initSettings();
    initGlobalSearch();

    pollingInterval = setInterval(() => {
        loadChats();
    }, 3000);

    setupEventListeners();
});

function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (savedTheme === 'auto') {
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    }

    const savedFont = localStorage.getItem('fontFamily');
    if (savedFont) {
        document.documentElement.style.setProperty('--font-family', savedFont);
        chatSettings.fontFamily = savedFont;
    }
}

function initSettings() {
    const saved = localStorage.getItem('chatSettings');
    if (saved) {
        chatSettings = { ...chatSettings, ...JSON.parse(saved) };
        applyChatSettings();
    }
}

function initGlobalSearch() {
    const searchInput = document.getElementById('globalSearchInput');
    const searchResults = document.getElementById('searchResults');

    if (!searchInput || !searchResults) return;

    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();

        if (query.length < 2) {
            searchResults.classList.remove('active');
            return;
        }

        searchTimeout = setTimeout(() => {
            fetch(`/api/search/global?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        renderSearchResults(data.results);
                    }
                });
        }, 300);
    });

    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.remove('active');
        }
    });

    searchInput.addEventListener('focus', function() {
        if (this.value.length >= 2) {
            searchResults.classList.add('active');
        }
    });
}

function renderSearchResults(results) {
    const container = document.getElementById('searchResults');
    if (!container) return;

    const allResults = [
        ...(results.users || []).map(u => ({ ...u, resultType: 'user' })),
        ...(results.groups || []).map(g => ({ ...g, resultType: 'group' })),
        ...(results.channels || []).map(c => ({ ...c, resultType: 'channel' }))
    ];

    if (allResults.length === 0) {
        container.innerHTML = '<div class="search-result-item"><span>No results found</span></div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = allResults.map(item => {
        let icon = '👤';
        if (item.resultType === 'group') icon = '👥';
        if (item.resultType === 'channel') icon = '📢';

        return `
            <div class="search-result-item" onclick="navigateToSearchResult('${item.resultType}', ${item.id})">
                <div class="search-result-avatar">${icon}</div>
                <div class="search-result-info">
                    <div class="search-result-name">${escapeHtml(item.name || item.username)}</div>
                    <div class="search-result-type">${item.resultType}</div>
                </div>
            </div>
        `;
    }).join('');

    container.classList.add('active');
}

function navigateToSearchResult(type, id) {
    document.getElementById('searchResults').classList.remove('active');
    document.getElementById('globalSearchInput').value = '';

    if (type === 'user') {
        selectChat('personal', id, `User ${id}`);
    } else if (type === 'group') {
        selectChat('group', id, `Group ${id}`);
    } else if (type === 'channel') {
        selectChat('channel', id, `Channel ${id}`);
    }
}

function setupEventListeners() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', updateSendButton);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    const contactSearch = document.getElementById('contactSearchInput');
    if (contactSearch) {
        contactSearch.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const filtered = contactsList.filter(c =>
                c.username.toLowerCase().includes(term) ||
                (c.display_name || '').toLowerCase().includes(term)
            );
            renderContactsList(filtered);
        });
    }

    const memberSearch = document.getElementById('memberSearchInput');
    if (memberSearch) {
        memberSearch.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const filtered = usersList.filter(u =>
                u.username.toLowerCase().includes(term)
            );
            renderUserListForGroup(filtered);
        });
    }
}

// ============ MENU FUNCTIONS ============
function initMenu() {
    const menuBtn = document.getElementById('menuBtn');
    const popoutMenu = document.getElementById('popoutMenu');
    const body = document.body;

    if (menuBtn) {
        menuBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            body.classList.toggle('popout-open');
            menuBtn.classList.toggle('active');
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && body.classList.contains('popout-open')) {
            body.classList.remove('popout-open');
            menuBtn?.classList.remove('active');
        }
    });

    document.addEventListener('click', (event) => {
        if (!body.classList.contains('popout-open')) return;
        if (popoutMenu && popoutMenu.contains(event.target)) return;
        if (menuBtn && menuBtn.contains(event.target)) return;
        body.classList.remove('popout-open');
        menuBtn?.classList.remove('active');
    });
}

function closePopout() {
    document.body.classList.remove('popout-open');
    document.getElementById('menuBtn')?.classList.remove('active');
}

// ============ VIEW MANAGEMENT ============
function showView(viewName) {
    const views = ['emptyChat', 'chatView', 'contactsView', 'createGroupView', 'createChannelView'];
    views.forEach(v => {
        const el = document.getElementById(v);
        if (el) el.style.display = 'none';
    });

    currentView = viewName;

    switch(viewName) {
        case 'empty':
            document.getElementById('emptyChat').style.display = 'flex';
            break;
        case 'chat':
            document.getElementById('chatView').style.display = 'flex';
            break;
        case 'contacts':
            document.getElementById('contactsView').style.display = 'flex';
            loadContacts();
            break;
        case 'createGroup':
            document.getElementById('createGroupView').style.display = 'flex';
            loadUsersForGroup();
            break;
        case 'createChannel':
            document.getElementById('createChannelView').style.display = 'flex';
            break;
    }

    if (window.innerWidth <= 768) {
        document.getElementById('chatSidebar').classList.remove('mobile-open');
    }
}

function showContactsView() {
    showView('contacts');
    closePopout();
}

function showCreateGroupView() {
    showView('createGroup');
    closePopout();
}

function showCreateChannelView() {
    showView('createChannel');
    closePopout();
}

function hideContactsView() {
    showView(currentChat ? 'chat' : 'empty');
}

function hideCreateGroupView() {
    showView(currentChat ? 'chat' : 'empty');
    selectedMembers.clear();
    groupAvatarFile = null;
    document.getElementById('groupAvatarPreview').innerHTML = '👥';
}

function hideCreateChannelView() {
    showView(currentChat ? 'chat' : 'empty');
    channelAvatarFile = null;
    document.getElementById('channelAvatarPreview').innerHTML = '📢';
}

// ============ CHAT LIST ============
async function loadChats() {
    try {
        const response = await fetch('/api/chat_list');
        const data = await response.json();
        if (data.chats) {
            chatsList = data.chats;
            renderChatList(chatsList);
        }
    } catch (error) {
        console.error('Error loading chats:', error);
    }
}

function renderChatList(chats) {
    const container = document.getElementById('chatList');
    if (!container) return;

    if (!chats || chats.length === 0) {
        container.innerHTML = `
            <div class="empty-chat" style="padding: 40px;">
                <div class="empty-chat-icon">💬</div>
                <h3>No chats yet</h3>
                <p>Start a conversation from Contacts</p>
            </div>
        `;
        return;
    }

    container.innerHTML = chats.map(chat => `
        <div class="chat-item ${chat.is_pinned ? 'pinned' : ''}"
             data-type="${chat.type}" data-id="${chat.id}"
             onclick="selectChat('${chat.type}', ${chat.id}, '${escapeHtml(chat.name)}')">
            <div class="chat-avatar ${chat.type === 'group' ? 'group' : chat.type === 'channel' ? 'channel' : ''}">
                ${chat.avatar_url ? `<img src="${chat.avatar_url}" alt="${escapeHtml(chat.name)}">` : (chat.avatar || chat.name.charAt(0).toUpperCase())}
                ${chat.is_online ? '<span class="online-indicator"></span>' : ''}
            </div>
            <div class="chat-info">
                <div class="chat-name-row">
                    <span class="chat-name">
                        ${chat.is_pinned ? '<span class="pin-indicator">📌</span>' : ''}
                        ${escapeHtml(chat.name)}
                    </span>
                    <span class="chat-time">${chat.timestamp || ''}</span>
                </div>
                <div class="chat-preview">
                    <span>${escapeHtml(chat.last_message || 'No messages yet')}</span>
                    ${chat.unread_count > 0 ? `<span class="unread-badge">${chat.unread_count}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');

    if (currentChat) {
        const activeItem = document.querySelector(`.chat-item[data-id="${currentChat.id}"]`);
        if (activeItem) activeItem.classList.add('active');
    }
}

async function selectChat(type, id, name) {
    if (messagePollingInterval) {
        clearInterval(messagePollingInterval);
        messagePollingInterval = null;
    }

    currentChat = { type, id, name };
    currentChatType = type;
    currentChatId = id;
    lastMessageId = 0;
    isLoadingMessages = false;

    const container = document.getElementById('messagesContainer');
    if (container) {
        container.innerHTML = `
            <div class="loading-messages">
                <div class="loading-spinner"></div>
                <p>Loading messages...</p>
            </div>
        `;
    }

    showView('chat');

    document.getElementById('chatHeaderName').textContent = name;

    const avatarDiv = document.getElementById('chatHeaderAvatar');
    avatarDiv.className = 'chat-header-avatar';
    if (type === 'group') {
        avatarDiv.textContent = '👥';
        avatarDiv.classList.add('group');
    } else if (type === 'channel') {
        avatarDiv.textContent = '📢';
        avatarDiv.classList.add('channel');
    } else {
        avatarDiv.textContent = name.charAt(0).toUpperCase();
    }

    document.querySelectorAll('.chat-item').forEach(item => item.classList.remove('active'));
    const activeItem = document.querySelector(`.chat-item[data-id="${id}"]`);
    if (activeItem) activeItem.classList.add('active');

    await loadMessages();

    if (type === 'personal') {
        await fetch(`/api/mark_read/${id}`, { method: 'POST' });
    }

    messagePollingInterval = setInterval(async () => {
        if (currentChatId === id) {
            await loadNewMessages();
        }
    }, 2000);
}

// ============ STORIES ============
async function loadStories() {
    try {
        const response = await fetch('/api/stories');
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            return;
        }

        const data = await response.json();
        if (data.success) {
            storiesList = data.stories || [];
            renderStoriesRow(storiesList);
        }
    } catch (error) {
        console.error('Error loading stories:', error);
    }
}

function renderStoriesRow(stories) {
    const container = document.getElementById('storiesRow');
    if (!container) return;

    let html = `
        <div class="story-item" onclick="triggerStoryUpload()">
            <div class="add-story-btn">+</div>
            <span class="story-username">Add Story</span>
        </div>
    `;

    stories.forEach(storyGroup => {
        const hasUnviewed = storyGroup.stories.some(s => !s.viewed);
        html += `
            <div class="story-item" onclick="viewStories(${storyGroup.user_id})">
                <div class="story-avatar ${!hasUnviewed ? 'viewed' : ''}">
                    ${storyGroup.avatar_url ?
                        `<img src="${storyGroup.avatar_url}" alt="${escapeHtml(storyGroup.display_name)}">` :
                        `<div class="story-avatar-placeholder">${(storyGroup.display_name || '?').charAt(0).toUpperCase()}</div>`
                    }
                </div>
                <span class="story-username">${escapeHtml(storyGroup.display_name)}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

function triggerStoryUpload() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*,video/*';
    input.onchange = (e) => uploadStory(e.target.files[0]);
    input.click();
}

async function uploadStory(file) {
    if (!file) return;

    const formData = new FormData();
    formData.append('media', file);

    try {
        const response = await fetch('/files/upload_story', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            showToast('Story uploaded!', 'success');
            loadStories();
        } else {
            showToast(data.error || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Error uploading story', 'error');
    }
}

function viewStories(userId) {
    const userStories = storiesList.find(s => s.user_id === userId);
    if (!userStories) return;
    showStoryViewer(userStories);
}

function showStoryViewer(storyGroup) {
    let currentIndex = 0;
    const stories = storyGroup.stories;

    const viewer = document.createElement('div');
    viewer.className = 'stories-viewer';
    viewer.innerHTML = `
        <div class="stories-header">
            <div class="story-avatar" style="width: 40px; height: 40px;">
                ${storyGroup.avatar_url ?
                    `<img src="${storyGroup.avatar_url}" style="width: 100%; height: 100%; border-radius: 50%;">` :
                    `<div class="story-avatar-placeholder">${(storyGroup.display_name || '?').charAt(0)}</div>`
                }
            </div>
            <span style="color: white; font-weight: 600;">${escapeHtml(storyGroup.display_name)}</span>
            <button onclick="this.closest('.stories-viewer').remove()" style="margin-left: auto; background: none; border: none; color: white; font-size: 24px; cursor: pointer;">✕</button>
        </div>
        <div class="stories-progress">
            ${stories.map((_, i) => `
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-${i}" style="width: 0%"></div>
                </div>
            `).join('')}
        </div>
        <div class="stories-content" id="storyContent"></div>
        <div class="stories-actions">
            <button class="story-action-btn" onclick="likeStory(${stories[currentIndex]?.id})">❤️</button>
        </div>
    `;

    document.body.appendChild(viewer);

    let progressInterval;

    function showStory(index) {
        if (progressInterval) clearInterval(progressInterval);

        const story = stories[index];
        const content = document.getElementById('storyContent');

        if (story.media_type === 'image') {
            content.innerHTML = `<img src="${story.media_url}" class="stories-media">`;
        } else {
            content.innerHTML = `<video src="${story.media_url}" class="stories-media" autoplay loop></video>`;
        }

        fetch(`/api/stories/${story.id}/view`, { method: 'POST' });

        const progressFill = document.getElementById(`progress-${index}`);
        let width = 0;
        progressInterval = setInterval(() => {
            width += 1.67;
            if (progressFill) progressFill.style.width = width + '%';
            if (width >= 100) {
                clearInterval(progressInterval);
                if (index < stories.length - 1) {
                    currentIndex++;
                    showStory(currentIndex);
                } else {
                    viewer.remove();
                }
            }
        }, 50);

        viewer.onclick = (e) => {
            if (e.target.classList.contains('stories-viewer')) {
                if (index < stories.length - 1) {
                    currentIndex++;
                    showStory(currentIndex);
                } else {
                    viewer.remove();
                }
            }
        };
    }

    showStory(0);
}

async function likeStory(storyId) {
    try {
        const response = await fetch(`/api/stories/${storyId}/like`, { method: 'POST' });
        const data = await response.json();
        showToast(data.action === 'liked' ? 'Liked!' : 'Unliked', 'success');
    } catch (error) {
        console.error('Error liking story:', error);
    }
}

// ============ CONTACTS ============
async function loadContacts() {
    try {
        const response = await fetch('/api/contacts');
        const data = await response.json();
        if (data.success) {
            contactsList = data.contacts;
            renderContactsList(contactsList);
        }
    } catch (error) {
        console.error('Error loading contacts:', error);
    }
}

function renderContactsList(contacts) {
    const container = document.getElementById('contactsList');
    if (!container) return;

    if (!contacts || contacts.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 40px; text-align: center;">
                <div class="empty-icon">👥</div>
                <h3>No contacts yet</h3>
                <p>Start chatting with someone to add them</p>
            </div>
        `;
        return;
    }

    container.innerHTML = contacts.map(contact => `
        <div class="contact-item" onclick="startChatWithContact(${contact.id}, '${escapeHtml(contact.username)}')">
            <div class="contact-avatar">
                ${contact.avatar_url ? `<img src="${contact.avatar_url}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;">` : contact.username.charAt(0).toUpperCase()}
            </div>
            <div class="contact-info">
                <div class="contact-name">${escapeHtml(contact.display_name || contact.username)}</div>
                <div class="contact-username">@${escapeHtml(contact.username)}</div>
                ${contact.is_online ? '<span class="online-badge">● Online</span>' : ''}
            </div>
        </div>
    `).join('');
}

function startChatWithContact(userId, username) {
    selectChat('personal', userId, username);
}

function showAddContactModal() {
    showPromptModal('Add Contact', 'Enter username:', async (username) => {
        try {
            const response = await fetch('/api/users');
            const data = await response.json();
            const user = data.users?.find(u => u.username === username);

            if (user) {
                startChatWithContact(user.id, user.username);
                showToast(`Starting chat with ${username}`, 'success');
            } else {
                showToast('User not found', 'error');
            }
        } catch (error) {
            showToast('Error finding user', 'error');
        }
    });
}

// ============ CREATE GROUP ============
async function loadUsersForGroup() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        if (data.success) {
            usersList = data.users.filter(u => u.id !== currentUser?.id);
            renderUserListForGroup(usersList);
        }
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function renderUserListForGroup(users) {
    const container = document.getElementById('userListForGroup');
    if (!container) return;

    if (!users || users.length === 0) {
        container.innerHTML = '<p style="padding: 16px; color: var(--text-muted);">No users found</p>';
        return;
    }

    container.innerHTML = users.map(user => `
        <div class="user-select-item ${selectedMembers.has(user.id) ? 'selected' : ''}"
             onclick="toggleMemberSelection(${user.id})">
            <div class="user-select-avatar">
                ${user.avatar_url ? `<img src="${user.avatar_url}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;">` : user.username.charAt(0).toUpperCase()}
            </div>
            <div class="user-select-info">
                <div class="user-select-name">${escapeHtml(user.display_name || user.username)}</div>
                <div class="user-select-username">@${escapeHtml(user.username)}</div>
            </div>
            <div class="selection-indicator">${selectedMembers.has(user.id) ? '✓' : ''}</div>
        </div>
    `).join('');
}

function toggleMemberSelection(userId) {
    if (selectedMembers.has(userId)) {
        selectedMembers.delete(userId);
    } else {
        selectedMembers.add(userId);
    }
    renderUserListForGroup(usersList);
    updateSelectedMembersDisplay();
}

function updateSelectedMembersDisplay() {
    const container = document.getElementById('selectedMembers');
    if (!container) return;

    if (selectedMembers.size === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); padding: 8px;">No members selected</p>';
        return;
    }

    container.innerHTML = Array.from(selectedMembers).map(id => {
        const user = usersList.find(u => u.id === id);
        return `
            <span class="selected-member-tag">
                ${escapeHtml(user?.username || 'User')}
                <button onclick="toggleMemberSelection(${id})">✕</button>
            </span>
        `;
    }).join('');
}

function triggerGroupAvatarUpload() {
    document.getElementById('groupAvatarInput').click();
}

function previewGroupAvatar(input) {
    if (input.files && input.files[0]) {
        groupAvatarFile = input.files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('groupAvatarPreview').innerHTML = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
        };
        reader.readAsDataURL(groupAvatarFile);
    }
}

async function createGroup() {
    const name = document.getElementById('groupName')?.value.trim();
    const description = document.getElementById('groupDescription')?.value.trim();
    const isPublic = document.getElementById('groupIsPublic')?.checked ?? true;

    if (!name) {
        showToast('Please enter a group name', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('is_public', isPublic);
    formData.append('member_ids', JSON.stringify(Array.from(selectedMembers)));

    if (groupAvatarFile) {
        formData.append('avatar', groupAvatarFile);
    }

    try {
        const response = await fetch('/api/groups/create', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.success) {
            showToast('Group created!', 'success');
            hideCreateGroupView();
            loadChats();
            selectChat('group', data.group.id, data.group.name);
        } else {
            showToast(data.error || 'Failed to create group', 'error');
        }
    } catch (error) {
        showToast('Error creating group', 'error');
    }
}

// ============ CREATE CHANNEL ============
function triggerChannelAvatarUpload() {
    document.getElementById('channelAvatarInput').click();
}

function previewChannelAvatar(input) {
    if (input.files && input.files[0]) {
        channelAvatarFile = input.files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('channelAvatarPreview').innerHTML = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
        };
        reader.readAsDataURL(channelAvatarFile);
    }
}

async function createChannel() {
    const name = document.getElementById('channelName')?.value.trim();
    const description = document.getElementById('channelDescription')?.value.trim();
    const isPublic = document.getElementById('channelIsPublic')?.checked ?? true;

    if (!name) {
        showToast('Please enter a channel name', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('is_public', isPublic);

    if (channelAvatarFile) {
        formData.append('avatar', channelAvatarFile);
    }

    try {
        const response = await fetch('/api/channels/create', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.success) {
            showToast('Channel created!', 'success');
            hideCreateChannelView();
            loadChats();
            selectChat('channel', data.channel.id, data.channel.name);
        } else {
            showToast(data.error || 'Failed to create channel', 'error');
        }
    } catch (error) {
        showToast('Error creating channel', 'error');
    }
}

// ============ MESSAGES ============
async function loadMessages() {
    if (!currentChat || isLoadingMessages) return;

    isLoadingMessages = true;

    let url;
    if (currentChatType === 'personal') {
        url = `/api/messages/${currentChat.id}`;
    } else if (currentChatType === 'group') {
        url = `/api/group_messages/${currentChat.id}`;
    } else {
        url = `/api/channel_messages/${currentChat.id}`;
    }

    try {
        const response = await fetch(`${url}?after=${lastMessageId}&limit=50`);
        const data = await response.json();
        const container = document.getElementById('messagesContainer');

        if (currentChatId !== currentChat.id) {
            isLoadingMessages = false;
            return;
        }

        if (data.messages && data.messages.length > 0) {
            const loadingEl = container.querySelector('.loading-messages');
            if (loadingEl) loadingEl.remove();

            data.messages.forEach(msg => {
                if (!document.getElementById(`message-${msg.id}`)) {
                    addMessageToUI(msg, msg.is_own);
                }
                if (msg.id > lastMessageId) lastMessageId = msg.id;
            });

            scrollToBottom();
        } else if (lastMessageId === 0) {
            container.innerHTML = `
                <div class="empty-chat" style="padding: 40px; text-align: center;">
                    <div class="empty-chat-icon">💬</div>
                    <h3>No messages yet</h3>
                    <p>Send a message to start the conversation!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading messages:', error);
    } finally {
        isLoadingMessages = false;
    }
}

async function loadNewMessages() {
    if (!currentChat || isLoadingMessages) return;

    let url;
    if (currentChatType === 'personal') {
        url = `/api/messages/${currentChat.id}`;
    } else if (currentChatType === 'group') {
        url = `/api/group_messages/${currentChat.id}`;
    } else {
        url = `/api/channel_messages/${currentChat.id}`;
    }

    try {
        const response = await fetch(`${url}?after=${lastMessageId}&limit=20`);
        const data = await response.json();
        const container = document.getElementById('messagesContainer');

        if (currentChatId !== currentChat.id) return;

        if (data.messages && data.messages.length > 0) {
            const emptyEl = container.querySelector('.empty-chat');
            if (emptyEl) emptyEl.remove();

            let newMessages = false;
            data.messages.forEach(msg => {
                if (!document.getElementById(`message-${msg.id}`)) {
                    addMessageToUI(msg, msg.is_own);
                    newMessages = true;
                }
                if (msg.id > lastMessageId) lastMessageId = msg.id;
            });

            if (newMessages) {
                scrollToBottom();
            }
        }
    } catch (error) {
        console.error('Error loading new messages:', error);
    }
}

function addMessageToUI(message, isOwn) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    if (document.getElementById(`message-${message.id}`)) {
        return;
    }

    const emptyEl = container.querySelector('.empty-chat');
    if (emptyEl) emptyEl.remove();

    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${isOwn ? 'outgoing' : 'incoming'}`;
    wrapper.id = `message-${message.id}`;

    let html = '<div class="message-bubble">';

    if (message.forwarded_from) {
        html += `<div class="forward-indicator">📨 Forwarded from ${escapeHtml(message.forwarded_from)}</div>`;
    }

    if (message.reply_to_id) {
        html += `<div class="reply-indicator">
            <span class="reply-to-name">↩️ ${escapeHtml(message.reply_to_sender || 'User')}</span>
            <div class="reply-to-content">${escapeHtml(message.reply_to_content || '')}</div>
        </div>`;
    }

    if (message.file_url) {
        if (message.file_type === 'image') {
            html += `<img src="${message.file_url}" class="message-image" onclick="window.open('${message.file_url}', '_blank')">`;
        } else {
            html += `<div class="file-attachment">
                <span>📎</span>
                <a href="${message.file_url}" target="_blank" class="file-link">${escapeHtml(message.file_name || 'File')}</a>
                <small>${message.formatted_size || ''}</small>
            </div>`;
        }
    }

    if (message.content) {
        html += `<div class="message-text">${formatMessageContent(message.content)}</div>`;
    }

    html += `<div class="message-time">${message.timestamp_formatted || ''}</div>`;
    html += `<div class="message-reactions" id="reactions-${message.id}"></div>`;
    html += '</div>';

    html += `<div class="message-actions">
        <span class="action-icon" onclick="showReactionPickerModal(${message.id})">😊</span>
        <span class="action-icon" onclick="setReplyTo(${message.id}, '${escapeHtml(message.sender_name || 'User')}', '${escapeHtml((message.content || '[Media]').substring(0, 100))}')">↩️</span>
        <span class="action-icon" onclick="showForwardModal(${message.id})">📤</span>
        ${isOwn ? '<span class="action-icon" onclick="deleteMessage(' + message.id + ')">🗑️</span>' : ''}
    </div>`;

    wrapper.innerHTML = html;
    container.appendChild(wrapper);

    if (message.reactions) {
        updateMessageReactions(message.id, message.reactions);
    }
}

function formatMessageContent(content) {
    if (!content) return '';

    let formatted = escapeHtml(content);
    formatted = formatted.replace(/\n/g, '<br>');
    formatted = formatted.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color: inherit; text-decoration: underline;">$1</a>');

    return formatted;
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content || !currentChat) return;

    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;

    let url, body;
    if (currentChatType === 'personal') {
        url = '/api/send_message';
        body = { receiver_id: currentChat.id, content };
    } else if (currentChatType === 'group') {
        url = '/api/send_group_message';
        body = { group_id: currentChat.id, content };
    } else {
        url = '/api/send_channel_message';
        body = { channel_id: currentChat.id, content };
    }

    if (replyToMsg) {
        body.reply_to_id = replyToMsg.id;
    }

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();

        if (data.success) {
            input.value = '';

            if (currentChatId === currentChat.id) {
                if (!document.getElementById(`message-${data.message.id}`)) {
                    addMessageToUI(data.message, true);
                    scrollToBottom();
                }
            }

            cancelReply();
            updateSendButton();

            if (data.message.id > lastMessageId) {
                lastMessageId = data.message.id;
            }

            loadChats();
        } else {
            showToast(data.error || 'Failed to send message', 'error');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        showToast('Error sending message', 'error');
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
}

function setReplyTo(messageId, senderName, content) {
    replyToMsg = { id: messageId, sender: senderName, content };
    const preview = document.getElementById('replyPreview');
    preview.querySelector('.reply-preview-name').textContent = `Replying to ${senderName}`;
    preview.querySelector('.reply-preview-text').textContent = content.substring(0, 50);
    preview.style.display = 'flex';
    document.getElementById('messageInput').focus();
}

function cancelReply() {
    replyToMsg = null;
    document.getElementById('replyPreview').style.display = 'none';
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    setTimeout(() => container.scrollTop = container.scrollHeight, 100);
}

function updateSendButton() {
    const input = document.getElementById('messageInput');
    const btn = document.getElementById('sendBtn');
    if (btn) btn.disabled = !input.value.trim();
}

async function deleteMessage(messageId) {
    showConfirmModal('Delete Message', 'Are you sure you want to delete this message?', async () => {
        try {
            const response = await fetch(`/api/messages/${messageId}`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) {
                document.getElementById(`message-${messageId}`)?.remove();
                showToast('Message deleted', 'success');
            }
        } catch (error) {
            showToast('Error deleting message', 'error');
        }
    });
}

// ============ REACTIONS ============
async function addReaction(messageId, reactionType) {
    try {
        const response = await fetch('/api/reactions/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_id: messageId, reaction_type: reactionType })
        });
        const data = await response.json();
        if (data.success) {
            updateMessageReactions(messageId, data.reactions);
        }
    } catch (error) {
        console.error('Error adding reaction:', error);
    }
}

function updateMessageReactions(messageId, reactions) {
    const container = document.getElementById(`reactions-${messageId}`);
    if (!container) return;

    if (!reactions || reactions.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = reactions.map(r => `
        <div class="reaction-badge" onclick="addReaction(${messageId}, '${r.type}')">
            <span>${r.type}</span>
            <span>${r.count}</span>
        </div>
    `).join('');
}

async function loadMessageReactions(messageId) {
    try {
        const response = await fetch(`/api/reactions/${messageId}`);
        const data = await response.json();
        if (data.success) {
            updateMessageReactions(messageId, data.reactions);
        }
    } catch (error) {
        console.error('Error loading reactions:', error);
    }
}

// ============ CHAT ACTIONS ============
function showChatInfo() {
    if (!currentChat) return;

    let infoHtml = `
        <p><strong>Name:</strong> ${escapeHtml(currentChat.name)}</p>
        <p><strong>Type:</strong> ${currentChatType}</p>
        <p><strong>ID:</strong> ${currentChat.id}</p>
    `;

    showModal('Chat Info', infoHtml, null, null, 'Close');
}

function showChatMenu() {
    if (!currentChat) return;

    const actions = [];

    if (currentChatType === 'personal') {
        actions.push({ label: 'View Profile', action: () => viewUserProfile(currentChat.id) });
        actions.push({ label: 'Block User', action: blockUser, danger: true });
        actions.push({ label: 'Clear Chat', action: clearCurrentChat, danger: true });
    } else if (currentChatType === 'group') {
        actions.push({ label: 'Group Info', action: showChatInfo });
        actions.push({ label: 'Leave Group', action: leaveCurrentGroup, danger: true });
    } else if (currentChatType === 'channel') {
        actions.push({ label: 'Channel Info', action: showChatInfo });
        actions.push({ label: 'Leave Channel', action: leaveCurrentChannel, danger: true });
    }

    const buttonsHtml = actions.map(a => `
        <button class="modal-btn ${a.danger ? 'modal-btn-danger' : 'modal-btn-primary'}"
                style="width: 100%; margin-bottom: 8px;"
                onclick="(${a.action.toString()})(); document.querySelector('.modal-overlay')?.remove();">
            ${a.label}
        </button>
    `).join('');

    showModal('Chat Actions', buttonsHtml, null, null, 'Close');
}

function viewUserProfile(userId) {
    window.location.href = `/profile/${userId}`;
}

function blockUser() {
    showConfirmModal('Block User', 'Are you sure you want to block this user?', async () => {
        try {
            await fetch(`/api/block_user/${currentChat.id}`, { method: 'POST' });
            showToast('User blocked', 'success');
            showView('empty');
            loadChats();
        } catch (error) {
            showToast('Error blocking user', 'error');
        }
    });
}

function clearCurrentChat() {
    showConfirmModal('Clear Chat', 'Delete all messages? This cannot be undone.', async () => {
        try {
            await fetch(`/api/clear_chat/${currentChat.id}`, { method: 'POST' });
            document.getElementById('messagesContainer').innerHTML = `
                <div class="empty-chat" style="padding: 40px;">
                    <div class="empty-chat-icon">💬</div>
                    <h3>No messages yet</h3>
                    <p>Send a message to start the conversation!</p>
                </div>
            `;
            lastMessageId = 0;
            showToast('Chat cleared', 'success');
            loadChats();
        } catch (error) {
            showToast('Error clearing chat', 'error');
        }
    });
}

async function leaveCurrentGroup() {
    showConfirmModal('Leave Group', 'Are you sure you want to leave this group?', async () => {
        try {
            await fetch(`/api/leave_group/${currentChat.id}`, { method: 'POST' });
            showToast('Left group', 'success');
            showView('empty');
            loadChats();
        } catch (error) {
            showToast('Error leaving group', 'error');
        }
    });
}

async function leaveCurrentChannel() {
    showConfirmModal('Leave Channel', 'Are you sure you want to leave this channel?', async () => {
        try {
            await fetch(`/api/leave_channel/${currentChat.id}`, { method: 'POST' });
            showToast('Left channel', 'success');
            showView('empty');
            loadChats();
        } catch (error) {
            showToast('Error leaving channel', 'error');
        }
    });
}

// ============ FILE UPLOAD ============
function triggerFileUpload() {
    document.getElementById('fileInput')?.click();
}

function handleFileSelect(input) {
    if (input.files && input.files.length > 0) {
        selectedFile = input.files[0];
        const uploadArea = document.getElementById('uploadArea');
        const fileNameEl = document.getElementById('uploadFileName');

        if (fileNameEl) fileNameEl.textContent = selectedFile.name;
        if (uploadArea) uploadArea.classList.add('active');

        if (selectedFile.size > 16 * 1024 * 1024) {
            showToast('File must be less than 16MB', 'error');
            cancelUpload();
        }
    }
}

async function uploadFile() {
    if (!selectedFile || !currentChat) {
        showToast('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    if (currentChatType === 'personal') {
        formData.append('receiver_id', currentChat.id);
    } else if (currentChatType === 'group') {
        formData.append('group_id', currentChat.id);
    } else {
        formData.append('channel_id', currentChat.id);
    }

    const uploadBtn = event.target;
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading...';
    }

    try {
        const response = await fetch('/files/upload_file', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.success) {
            if (currentChatId === currentChat.id) {
                addMessageToUI(data.message, true);
                scrollToBottom();
            }
            cancelUpload();
            showToast('File uploaded', 'success');
            loadChats();
        } else {
            showToast(data.error || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload failed', 'error');
    } finally {
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload';
        }
    }
}

function cancelUpload() {
    document.getElementById('uploadArea')?.classList.remove('active');
    selectedFile = null;
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';
    const fileNameEl = document.getElementById('uploadFileName');
    if (fileNameEl) fileNameEl.textContent = 'No file selected';
}

// ============ PROFILE MODAL ============
function openProfileModal() {
    loadUserProfileData();
    document.getElementById('profileModal').style.display = 'flex';
    closePopout();
}

function closeProfileModal() {
    document.getElementById('profileModal').style.display = 'none';
}

function loadUserProfileData() {
    fetch('/api/profile')
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const user = data.user;
                currentUser = user;

                const avatarContainer = document.getElementById('profileAvatar');
                if (user.avatar_url) {
                    avatarContainer.innerHTML = `<img src="${user.avatar_url}" class="profile-avatar" alt="${escapeHtml(user.display_name || user.username)}">`;
                } else {
                    avatarContainer.innerHTML = `<div class="profile-avatar-placeholder">${(user.display_name || user.username || '?').charAt(0).toUpperCase()}</div>`;
                }

                document.getElementById('profileDisplayName').textContent = user.display_name || user.username;
                document.getElementById('profileUsername').textContent = '@' + (user.username || '');
                document.getElementById('profileBio').textContent = user.bio || 'No bio yet';
                document.getElementById('profileDisplayNameValue').textContent = user.display_name || user.username;
                document.getElementById('profileUsernameValue').textContent = user.username || '';
                document.getElementById('profileBioValue').textContent = user.bio || 'Not set';

                document.getElementById('followersCount').textContent = user.followers_count || 0;
                document.getElementById('followingCount').textContent = user.following_count || 0;
                document.getElementById('groupsCount').textContent = user.groups_count || 0;

                updateMenuUserInfo(user);
            }
        });
}

function updateMenuUserInfo(user) {
    const avatar = document.getElementById('menuUserAvatar');
    const name = document.getElementById('menuUserName');
    const username = document.getElementById('menuUserUsername');

    if (avatar) avatar.textContent = (user.display_name || user.username || '?').charAt(0).toUpperCase();
    if (name) name.textContent = user.display_name || user.username;
    if (username) username.textContent = '@' + (user.username || '');
}

function openEditProfileModal() {
    closeProfileModal();

    fetch('/api/profile')
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const user = data.user;
                document.getElementById('editDisplayName').value = user.display_name || '';
                document.getElementById('editUsername').value = user.username || '';
                document.getElementById('editBio').value = user.bio || '';
                document.getElementById('bioCharCount').textContent = (user.bio || '').length;
            }
        });

    document.getElementById('editProfileModal').style.display = 'flex';

    const bioField = document.getElementById('editBio');
    if (bioField) {
        bioField.addEventListener('input', function() {
            document.getElementById('bioCharCount').textContent = this.value.length;
        });
    }
}

function closeEditProfileModal() {
    document.getElementById('editProfileModal').style.display = 'none';
}

function saveProfile() {
    const data = {
        display_name: document.getElementById('editDisplayName').value.trim(),
        username: document.getElementById('editUsername').value.trim(),
        bio: document.getElementById('editBio').value.trim()
    };

    fetch('/api/profile/update', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showToast('Profile updated!', 'success');
            closeEditProfileModal();
            loadUserProfileData();
        } else {
            showToast(data.error || 'Update failed', 'error');
        }
    });
}

function triggerAvatarUpload() {
    document.getElementById('avatarInput').click();
}

function uploadAvatar(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];

        if (file.size > 5 * 1024 * 1024) {
            showToast('File too large. Max 5MB', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('avatar', file);

        fetch('/files/upload_avatar', {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Avatar updated!', 'success');
                loadUserProfileData();
            } else {
                showToast(data.error || 'Upload failed', 'error');
            }
        });
    }
}

function loadUserProfile() {
    loadUserProfileData();
}

// ============ CHAT CUSTOMIZATION ============
function openChatCustomization() {
    const bodyHtml = `
        <div class="settings-section">
            <h3>Wallpaper</h3>
            <div class="wallpaper-options">
                <div class="wallpaper-option gradient1 ${!chatSettings.wallpaper ? 'active' : ''}" onclick="selectWallpaper('gradient1')"></div>
                <div class="wallpaper-option gradient2" onclick="selectWallpaper('gradient2')"></div>
                <div class="wallpaper-option gradient3" onclick="selectWallpaper('gradient3')"></div>
                <div class="wallpaper-option gradient4" onclick="selectWallpaper('gradient4')"></div>
                <div class="wallpaper-option gradient5" onclick="selectWallpaper('gradient5')"></div>
                <div class="wallpaper-option gradient6" onclick="selectWallpaper('gradient6')"></div>
            </div>
            <button class="modal-btn modal-btn-secondary" style="width: 100%; margin-top: 12px;" onclick="uploadCustomWallpaper()">📁 Upload Custom</button>
        </div>
        <div class="settings-section">
            <h3>Message Style</h3>
            <label>Your Message Color</label>
            <input type="color" id="ownColorInput" class="modal-input" value="${chatSettings.ownMessageColor}">
            <label>Other Message Color</label>
            <input type="color" id="otherColorInput" class="modal-input" value="${chatSettings.otherMessageColor}">
        </div>
    `;

    showModal('Chat Customization', bodyHtml, () => {
        chatSettings.ownMessageColor = document.getElementById('ownColorInput').value;
        chatSettings.otherMessageColor = document.getElementById('otherColorInput').value;
        localStorage.setItem('chatSettings', JSON.stringify(chatSettings));
        applyChatSettings();
        showToast('Settings saved', 'success');
    }, null, 'Save', 'Cancel');
}

function selectWallpaper(type) {
    document.querySelectorAll('.wallpaper-option').forEach(opt => opt.classList.remove('active'));
    event.target.classList.add('active');

    const gradients = {
        gradient1: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        gradient2: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        gradient3: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        gradient4: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
        gradient5: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        gradient6: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)'
    };

    chatSettings.wallpaper = gradients[type];
}

function uploadCustomWallpaper() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = (e) => {
        if (e.target.files[0]) {
            const reader = new FileReader();
            reader.onload = (event) => {
                chatSettings.wallpaper = `url(${event.target.result})`;
                applyChatSettings();
                showToast('Wallpaper applied', 'success');
            };
            reader.readAsDataURL(e.target.files[0]);
        }
    };
    input.click();
}

function applyChatSettings() {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    if (chatSettings.wallpaper) {
        container.style.backgroundImage = chatSettings.wallpaper;
        container.style.backgroundSize = 'cover';
        container.style.backgroundPosition = 'center';
    }
}

// ============ SETTINGS ============
function openSettingsPanel() {
    document.getElementById('settingsPanel').classList.add('open');
    document.getElementById('panelOverlay').classList.add('visible');
    closePopout();
}

function closeSettingsPanel() {
    document.getElementById('settingsPanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('visible');
}

function openPrivacyPanel() {
    document.getElementById('privacyPanel').classList.add('open');
    document.getElementById('panelOverlay').classList.add('visible');
}

function closePrivacyPanel() {
    document.getElementById('privacyPanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('visible');
}

function closeAllPanels() {
    closeSettingsPanel();
    closePrivacyPanel();
    closeProfileModal();
    closeEditProfileModal();
}

function toggleSetting(element, setting) {
    element.classList.toggle('active');
    const isEnabled = element.classList.contains('active');
    localStorage.setItem(setting, isEnabled);
    showToast(`${setting} ${isEnabled ? 'enabled' : 'disabled'}`, 'info');
}

function setTheme(theme) {
    document.querySelectorAll('.theme-option').forEach(opt => opt.classList.remove('active'));
    event.target.closest('.theme-option').classList.add('active');
    localStorage.setItem('theme', theme);

    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (theme === 'light') {
        document.documentElement.removeAttribute('data-theme');
    } else if (theme === 'auto') {
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
    }

    showToast(`Theme set to ${theme}`, 'success');
}

function setFont(element) {
    document.querySelectorAll('.font-option').forEach(opt => opt.classList.remove('active'));
    element.classList.add('active');

    const font = element.dataset.font;
    document.documentElement.style.setProperty('--font-family', font);
    chatSettings.fontFamily = font;
    localStorage.setItem('fontFamily', font);
    localStorage.setItem('chatSettings', JSON.stringify(chatSettings));

    showToast('Font updated', 'success');
}

function savePrivacySettings() {
    const visibility = document.getElementById('profileVisibility')?.value || 'everyone';
    localStorage.setItem('profileVisibility', visibility);
    showToast('Privacy settings saved', 'success');
    closePrivacyPanel();
}

// ============ STAT ACTIONS ============
function showFollowers() {
    showToast('Followers list coming soon', 'info');
}

function showFollowing() {
    showToast('Following list coming soon', 'info');
}

function showGroups() {
    showToast('Groups list coming soon', 'info');
}

// ============ MODAL FUNCTIONS ============
function showModal(title, bodyHtml, onConfirm, onCancel, confirmText = 'Confirm', cancelText = 'Cancel', isDanger = false) {
    const modalRoot = document.getElementById('modalRoot');
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h3>${escapeHtml(title)}</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="modal-body">${bodyHtml}</div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-secondary" id="modalCancelBtn">${escapeHtml(cancelText)}</button>
                <button class="modal-btn ${isDanger ? 'modal-btn-danger' : 'modal-btn-primary'}" id="modalConfirmBtn">${escapeHtml(confirmText)}</button>
            </div>
        </div>
    `;

    modalRoot.appendChild(modal);

    const confirmBtn = modal.querySelector('#modalConfirmBtn');
    const cancelBtn = modal.querySelector('#modalCancelBtn');
    const closeBtn = modal.querySelector('.modal-close');

    const closeModal = () => modal.remove();

    confirmBtn.onclick = () => { if (onConfirm) onConfirm(modal); closeModal(); };
    cancelBtn.onclick = () => { if (onCancel) onCancel(); closeModal(); };
    closeBtn.onclick = closeModal;
    modal.onclick = (e) => { if (e.target === modal) closeModal(); };
}

function showConfirmModal(title, message, onConfirm) {
    showModal(title, `<p>${escapeHtml(message)}</p>`, onConfirm, null, 'Yes', 'No', true);
}

function showPromptModal(title, placeholder, onConfirm, defaultValue = '') {
    const bodyHtml = `
        <input type="text" id="modalInput" class="modal-input" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(defaultValue)}" autofocus>
    `;
    showModal(title, bodyHtml, (modal) => {
        const input = modal.querySelector('#modalInput');
        if (input && input.value.trim()) {
            onConfirm(input.value.trim());
        }
    }, null, 'Submit', 'Cancel');
}

function showReactionPickerModal(messageId) {
    const reactions = ['👍', '❤️', '😂', '😮', '😢', '👏', '🔥', '🎉', '💯'];
    const bodyHtml = `
        <div class="reaction-picker-modal">
            ${reactions.map(r => `<button class="reaction-option" onclick="addReaction(${messageId}, '${r}'); this.closest('.modal-overlay').remove()">${r}</button>`).join('')}
        </div>
    `;
    showModal('Add Reaction', bodyHtml, null, null, 'Close', 'Cancel');
}

function showForwardModal(messageId) {
    const bodyHtml = `
        <div class="radio-group">
            <div class="radio-option">
                <input type="radio" name="forwardType" value="user" checked> User
            </div>
            <div class="radio-option">
                <input type="radio" name="forwardType" value="group"> Group
            </div>
            <div class="radio-option">
                <input type="radio" name="forwardType" value="channel"> Channel
            </div>
        </div>
        <input type="text" id="targetIdInput" class="modal-input" placeholder="Enter ID">
    `;

    showModal('Forward Message', bodyHtml, (modal) => {
        const type = modal.querySelector('input[name="forwardType"]:checked').value;
        const targetId = modal.querySelector('#targetIdInput').value.trim();

        if (!targetId) {
            showToast('Please enter a target ID', 'error');
            return;
        }

        fetch('/api/forward_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_id: messageId, target_type: type, target_id: targetId })
        }).then(r => r.json()).then(data => {
            if (data.success) showToast('Forwarded!', 'success');
            else showToast(data.error || 'Forward failed', 'error');
        });
    }, null, 'Forward', 'Cancel');
}

// ============ UTILITIES ============
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
        background: ${type === 'error' ? '#f5365c' : type === 'success' ? '#2dce89' : '#5e72e4'};
        color: white; padding: 12px 24px; border-radius: 50px; font-size: 14px;
        z-index: 3000; animation: fadeIn 0.3s; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        white-space: nowrap;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleMobileSidebar() {
    document.getElementById('chatSidebar').classList.toggle('mobile-open');
}

function logout() {
    showConfirmModal('Sign Out', 'Are you sure you want to sign out?', () => {
        fetch('/api/auth/logout', { method: 'POST' })
            .then(() => window.location.href = '/login')
            .catch(() => window.location.href = '/logout');
    });
}

// ============ CLEANUP ============
window.addEventListener('beforeunload', () => {
    if (pollingInterval) clearInterval(pollingInterval);
    if (messagePollingInterval) clearInterval(messagePollingInterval);
});

// ============ GLOBAL EXPORTS ============
window.showContactsView = showContactsView;
window.showCreateGroupView = showCreateGroupView;
window.showCreateChannelView = showCreateChannelView;
window.hideContactsView = hideContactsView;
window.hideCreateGroupView = hideCreateGroupView;
window.hideCreateChannelView = hideCreateChannelView;
window.selectChat = selectChat;
window.toggleMemberSelection = toggleMemberSelection;
window.createGroup = createGroup;
window.createChannel = createChannel;
window.startChatWithContact = startChatWithContact;
window.setReplyTo = setReplyTo;
window.cancelReply = cancelReply;
window.addReaction = addReaction;
window.deleteMessage = deleteMessage;
window.likeStory = likeStory;
window.viewStories = viewStories;
window.triggerStoryUpload = triggerStoryUpload;
window.triggerGroupAvatarUpload = triggerGroupAvatarUpload;
window.previewGroupAvatar = previewGroupAvatar;
window.triggerChannelAvatarUpload = triggerChannelAvatarUpload;
window.previewChannelAvatar = previewChannelAvatar;
window.openSettingsPanel = openSettingsPanel;
window.closeSettingsPanel = closeSettingsPanel;
window.openPrivacyPanel = openPrivacyPanel;
window.closePrivacyPanel = closePrivacyPanel;
window.closeAllPanels = closeAllPanels;
window.toggleSetting = toggleSetting;
window.setTheme = setTheme;
window.setFont = setFont;
window.savePrivacySettings = savePrivacySettings;
window.openProfileModal = openProfileModal;
window.closeProfileModal = closeProfileModal;
window.openEditProfileModal = openEditProfileModal;
window.closeEditProfileModal = closeEditProfileModal;
window.saveProfile = saveProfile;
window.triggerAvatarUpload = triggerAvatarUpload;
window.uploadAvatar = uploadAvatar;
window.loadUserProfile = loadUserProfile;
window.openChatCustomization = openChatCustomization;
window.selectWallpaper = selectWallpaper;
window.uploadCustomWallpaper = uploadCustomWallpaper;
window.showChatInfo = showChatInfo;
window.showChatMenu = showChatMenu;
window.showAddContactModal = showAddContactModal;
window.triggerFileUpload = triggerFileUpload;
window.handleFileSelect = handleFileSelect;
window.uploadFile = uploadFile;
window.cancelUpload = cancelUpload;
window.showFollowers = showFollowers;
window.showFollowing = showFollowing;
window.showGroups = showGroups;
window.logout = logout;
window.toggleMobileSidebar = toggleMobileSidebar;
window.showReactionPickerModal = showReactionPickerModal;
window.showForwardModal = showForwardModal;
window.navigateToSearchResult = navigateToSearchResult;
window.closePopout = closePopout;