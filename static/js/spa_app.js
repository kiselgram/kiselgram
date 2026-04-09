/* static/js/spa_app.js */

// ============ GLOBAL STATE ============
let currentUser = null;
let currentChat = null;
let currentChatType = null;
let currentView = 'empty';
let chatsList = [];
let contactsList = [];
let usersList = [];
let storiesList = [];
let selectedMembers = new Set();
let replyToMsg = null;
let selectedFile = null;
let pollingInterval = null;
let lastMessageId = 0;
let chatSettings = {
    fontSize: 'medium',
    borderRadius: '18px',
    fontFamily: 'Segoe UI',
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

    pollingInterval = setInterval(() => {
        loadChats();
        if (currentChat) loadMessages();
    }, 3000);

    setupEventListeners();
});

function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
}

function initSettings() {
    const saved = localStorage.getItem('chatSettings');
    if (saved) {
        chatSettings = { ...chatSettings, ...JSON.parse(saved) };
        applyChatSettings();
    }
}

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const filtered = chatsList.filter(chat =>
                chat.name.toLowerCase().includes(term)
            );
            renderChatList(filtered);
        });
    }

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
}

function hideCreateChannelView() {
    showView(currentChat ? 'chat' : 'empty');
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
                ${chat.avatar || chat.name.charAt(0).toUpperCase()}
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
    currentChat = { type, id, name };
    currentChatType = type;
    lastMessageId = 0;

    showView('chat');

    document.getElementById('chatHeaderName').textContent = name;

    const avatarDiv = document.getElementById('chatHeaderAvatar');
    if (type === 'group') {
        avatarDiv.textContent = '👥';
        avatarDiv.style.background = 'linear-gradient(135deg, var(--accent-green), #2dce89)';
    } else if (type === 'channel') {
        avatarDiv.textContent = '📢';
        avatarDiv.style.background = 'linear-gradient(135deg, var(--accent-orange), #fb6340)';
    } else {
        avatarDiv.textContent = name.charAt(0).toUpperCase();
        avatarDiv.style.background = 'linear-gradient(135deg, var(--accent-blue), #764ba2)';
    }

    document.querySelectorAll('.chat-item').forEach(item => item.classList.remove('active'));
    const activeItem = document.querySelector(`.chat-item[data-id="${id}"]`);
    if (activeItem) activeItem.classList.add('active');

    await loadMessages();

    if (type === 'personal') {
        await fetch(`/api/mark_read/${id}`, { method: 'POST' });
    }
}

// ============ STORIES ============
async function loadStories() {
    try {
        const response = await fetch('/api/stories');
        const data = await response.json();
        if (data.success) {
            storiesList = data.stories;
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
                        `<img src="${storyGroup.avatar_url}" alt="${storyGroup.display_name}">` :
                        `<div class="story-avatar-placeholder">${storyGroup.display_name.charAt(0).toUpperCase()}</div>`
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
        const response = await fetch('/api/stories/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            showToast('Story uploaded!', 'success');
            loadStories();
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
                    `<div class="story-avatar-placeholder">${storyGroup.display_name.charAt(0)}</div>`
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

    function showStory(index) {
        const story = stories[index];
        const content = document.getElementById('storyContent');

        if (story.media_type === 'image') {
            content.innerHTML = `<img src="${story.media_url}" class="stories-media">`;
        } else {
            content.innerHTML = `<video src="${story.media_url}" class="stories-media" autoplay></video>`;
        }

        fetch(`/api/stories/${story.id}/view`, { method: 'POST' });

        const progressFill = document.getElementById(`progress-${index}`);
        let width = 0;
        const interval = setInterval(() => {
            width += 2;
            if (progressFill) progressFill.style.width = width + '%';
            if (width >= 100) {
                clearInterval(interval);
                if (index < stories.length - 1) {
                    currentIndex++;
                    showStory(currentIndex);
                } else {
                    viewer.remove();
                }
            }
        }, 100);
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
            <div class="contact-avatar">${contact.username.charAt(0).toUpperCase()}</div>
            <div class="contact-info">
                <div class="contact-name">${escapeHtml(contact.display_name || contact.username)}</div>
                <div class="contact-username">@${escapeHtml(contact.username)}</div>
            </div>
        </div>
    `).join('');
}

function startChatWithContact(userId, username) {
    selectChat('personal', userId, username);
}

// ============ CREATE GROUP ============
async function loadUsersForGroup() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        if (data.success) {
            usersList = data.users;
            renderUserListForGroup(usersList);
        }
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function renderUserListForGroup(users) {
    const container = document.getElementById('userListForGroup');
    if (!container) return;

    container.innerHTML = users.map(user => `
        <div class="user-select-item ${selectedMembers.has(user.id) ? 'selected' : ''}"
             onclick="toggleMemberSelection(${user.id})">
            <div class="user-avatar">${user.username.charAt(0).toUpperCase()}</div>
            <div class="user-info">
                <div class="user-name">${escapeHtml(user.display_name || user.username)}</div>
                <div class="user-username">@${escapeHtml(user.username)}</div>
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
        container.innerHTML = '<p style="color: var(--text-muted);">No members selected</p>';
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

async function createGroup() {
    const name = document.getElementById('groupName')?.value.trim();
    const description = document.getElementById('groupDescription')?.value.trim();
    const isPublic = document.getElementById('groupIsPublic')?.checked ?? true;

    if (!name) {
        showToast('Please enter a group name', 'error');
        return;
    }

    try {
        const response = await fetch('/api/groups/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description,
                is_public: isPublic,
                member_ids: Array.from(selectedMembers)
            })
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
async function createChannel() {
    const name = document.getElementById('channelName')?.value.trim();
    const description = document.getElementById('channelDescription')?.value.trim();
    const isPublic = document.getElementById('channelIsPublic')?.checked ?? true;

    if (!name) {
        showToast('Please enter a channel name', 'error');
        return;
    }

    try {
        const response = await fetch('/api/channels/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, is_public: isPublic })
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
    if (!currentChat) return;

    let url;
    if (currentChatType === 'personal') {
        url = `/api/messages/${currentChat.id}`;
    } else if (currentChatType === 'group') {
        url = `/api/group_messages/${currentChat.id}`;
    } else {
        url = `/api/channel_messages/${currentChat.id}`;
    }

    try {
        const response = await fetch(`${url}?after=${lastMessageId}`);
        const data = await response.json();
        const container = document.getElementById('messagesContainer');

        if (data.messages && data.messages.length > 0) {
            if (container.querySelector('.loading-messages')) {
                container.innerHTML = '';
            }
            data.messages.forEach(msg => {
                addMessageToUI(msg, msg.is_own);
                if (msg.id > lastMessageId) lastMessageId = msg.id;
            });
            scrollToBottom();
        } else if (lastMessageId === 0) {
            container.innerHTML = `
                <div class="empty-chat" style="padding: 40px;">
                    <div class="empty-chat-icon">💬</div>
                    <h3>No messages yet</h3>
                    <p>Send a message to start the conversation!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

function addMessageToUI(message, isOwn) {
    const container = document.getElementById('messagesContainer');
    if (container.querySelector('.empty-chat')) {
        container.innerHTML = '';
    }

    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${isOwn ? 'outgoing' : 'incoming'}`;
    wrapper.id = `message-${message.id}`;

    let html = '<div class="message-bubble" style="border-radius: ' + chatSettings.borderRadius + ';">';

    if (message.forwarded_from) {
        html += `<div class="forward-indicator">📨 Forwarded from ${escapeHtml(message.forwarded_from)}</div>`;
    }

    if (message.reply_to_id) {
        html += `<div class="reply-indicator">
            <span class="reply-to-name">↩️ ${escapeHtml(message.reply_to_sender)}</span>
            <div>${escapeHtml(message.reply_to_content || '')}</div>
        </div>`;
    }

    if (message.file_url) {
        if (message.file_type === 'image') {
            html += `<img src="${message.file_url}" style="max-width: 200px; border-radius: 8px; cursor: pointer;" onclick="window.open('${message.file_url}', '_blank')">`;
        } else {
            html += `<div>📎 ${escapeHtml(message.file_name)}</div>`;
        }
    }

    if (message.content) {
        html += `<div class="message-text">${escapeHtml(message.content)}</div>`;
    }

    html += `<div class="message-time">${message.timestamp_formatted || ''}</div>`;
    html += `<div class="message-reactions" id="reactions-${message.id}"></div>`;
    html += '</div>';

    html += `<div class="message-actions">
        <span class="action-icon" onclick="showReactionPickerModal(${message.id})">😊</span>
        <span class="action-icon" onclick="setReplyTo(${message.id}, '${escapeHtml(message.sender_name)}', '${escapeHtml((message.content || '[Media]').substring(0, 100))}')">↩️</span>
        <span class="action-icon" onclick="showForwardModal(${message.id})">📤</span>
        <span class="action-icon" onclick="pinMessage(${message.id})">📌</span>
    </div>`;

    wrapper.innerHTML = html;
    container.appendChild(wrapper);

    loadMessageReactions(message.id);
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content || !currentChat) return;

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

    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();

        if (data.success) {
            input.value = '';
            addMessageToUI(data.message, true);
            cancelReply();
            scrollToBottom();
            updateSendButton();
            loadChats();
        }
    } catch (error) {
        showToast('Error sending message', 'error');
    } finally {
        sendBtn.disabled = false;
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
    btn.disabled = !input.value.trim();
}

async function pinMessage(messageId) {
    try {
        await fetch('/api/pin_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_id: messageId })
        });
        showToast('Message pinned', 'success');
    } catch (error) {
        console.error('Error pinning message:', error);
    }
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

// ============ CHAT CUSTOMIZATION ============
function applyChatSettings() {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    if (chatSettings.wallpaper) {
        container.style.backgroundImage = `url(${chatSettings.wallpaper})`;
        container.style.backgroundSize = 'cover';
    }

    document.querySelectorAll('.message-bubble').forEach(bubble => {
        bubble.style.borderRadius = chatSettings.borderRadius;
    });
}

function openChatCustomization() {
    showModal('Chat Customization', `
        <div class="settings-section">
            <h3>Message Style</h3>
            <label>Font Size</label>
            <select class="modal-input" id="fontSizeSelect">
                <option value="small">Small</option>
                <option value="medium" selected>Medium</option>
                <option value="large">Large</option>
            </select>

            <label>Border Radius</label>
            <select class="modal-input" id="borderRadiusSelect">
                <option value="4px">Square</option>
                <option value="12px">Rounded</option>
                <option value="18px" selected>Bubble</option>
                <option value="24px">Round</option>
            </select>

            <label>Your Message Color</label>
            <input type="color" class="modal-input" id="ownColorInput" value="${chatSettings.ownMessageColor}">

            <label>Other Message Color</label>
            <input type="color" class="modal-input" id="otherColorInput" value="${chatSettings.otherMessageColor}">
        </div>
    `, () => {
        chatSettings.fontSize = document.getElementById('fontSizeSelect').value;
        chatSettings.borderRadius = document.getElementById('borderRadiusSelect').value;
        chatSettings.ownMessageColor = document.getElementById('ownColorInput').value;
        chatSettings.otherMessageColor = document.getElementById('otherColorInput').value;

        localStorage.setItem('chatSettings', JSON.stringify(chatSettings));
        applyChatSettings();
        showToast('Settings saved', 'success');
    }, null, 'Save', 'Cancel');
}

// ============ PROFILE ============
async function loadUserProfile() {
    try {
        const response = await fetch('/api/profile');
        const data = await response.json();
        if (data.success) {
            currentUser = data.user;
            updateProfileUI(currentUser);
        }
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

function updateProfileUI(user) {
    document.getElementById('menuUserAvatar').textContent = user.username.charAt(0).toUpperCase();
    document.getElementById('menuUserName').textContent = user.display_name || user.username;
    document.getElementById('menuUserUsername').textContent = '@' + user.username;
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
    } else {
        document.documentElement.removeAttribute('data-theme');
    }

    showToast(`Theme set to ${theme}`, 'success');
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

function showReactionPickerModal(messageId) {
    const reactions = ['👍', '❤️', '😂', '😮', '😢', '👏', '🔥', '🎉'];
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
    showConfirmModal('Sign Out', 'Are you sure?', () => {
        fetch('/api/auth/logout', { method: 'POST' })
            .then(() => window.location.href = '/login');
    });
}

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
window.pinMessage = pinMessage;
window.likeStory = likeStory;
window.viewStories = viewStories;
window.triggerStoryUpload = triggerStoryUpload;
window.openSettingsPanel = openSettingsPanel;
window.closeSettingsPanel = closeSettingsPanel;
window.openPrivacyPanel = openPrivacyPanel;
window.closePrivacyPanel = closePrivacyPanel;
window.closeAllPanels = closeAllPanels;
window.toggleSetting = toggleSetting;
window.setTheme = setTheme;
window.logout = logout;
window.toggleMobileSidebar = toggleMobileSidebar;
window.showReactionPickerModal = showReactionPickerModal;
window.showForwardModal = showForwardModal;