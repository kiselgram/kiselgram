// static/js/chats/premium.js
// Premium-only extensions: stories, wallpaper customization, bots

// ============== STORIES (PREMIUM) ==============
let currentStories = [];
let currentStoryIndex = 0;
let currentStoryUser = null;
let storyProgressInterval = null;

async function loadStories() {
    if (!currentUserId) return;
    try {
        const res = await fetch('/api/stories');
        const data = await res.json();
        if (data.success) {
            currentStories = data.stories || [];
            renderStoriesRow();
        }
    } catch (e) { console.error('Failed to load stories', e); }
}

function renderStoriesRow() {
    const row = document.getElementById('storiesRow');
    if (!row) return;
    const hasStory = currentStories.some(s => s.user_id === currentUserId);
    let html = '';

    // Add story button
    html += `
        <div class="story-circle" onclick="openStoryUpload()">
            <div class="add-story-btn" style="background:linear-gradient(135deg, var(--accent-orange), var(--accent-green)); color:white;">
                <i class="fas fa-plus"></i>
            </div>
            <span class="story-username">My Story</span>
        </div>
    `;

    // Other users' stories
    currentStories.forEach(s => {
        if (s.user_id === currentUserId) return;
        const avatarHtml = s.avatar_url
            ? `<img src="${s.avatar_url}" alt="">`
            : `<span>${s.avatar_letter || '?'}</span>`;
        html += `
            <div class="story-circle" onclick="openStoryViewer(${s.user_id})">
                <div class="story-avatar-wrapper ${s.has_unviewed ? '' : 'viewed'}">
                    <div class="story-avatar">
                        ${avatarHtml}
                    </div>
                </div>
                <span class="story-username">${escapeHtml(s.display_name || s.username)}</span>
            </div>
        `;
    });

    row.innerHTML = html;
}

// Story upload modal (no caption input) – called from template include
function openStoryUpload() {
    document.getElementById('storyUploadModal').classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

function uploadStory() {
    // Called from story_upload.html button
    const fileInput = document.getElementById('storyFileInput');
    const privacy = document.getElementById('storyPrivacy').value;
    if (!fileInput.files[0]) return showToast('Please select a file', 'error');
    const formData = new FormData();
    formData.append('media', fileInput.files[0]);
    formData.append('privacy', privacy);
    // No caption sent
    fetch('/api/stories/create', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                closeModal('storyUploadModal');
                loadStories();
                showToast('Story published!', 'success');
            } else {
                showToast('Failed to publish story', 'error');
            }
        });
}

// ============== STORY VIEWER ==============
function openStoryViewer(userId) {
    const userStory = currentStories.find(s => s.user_id === userId);
    if (!userStory) return;
    currentStoryUser = userStory;
    currentStoryIndex = 0;
    showStoryModal();
}

function showStoryModal() {
    const story = currentStoryUser.stories[currentStoryIndex];
    if (!story) return;
    const modal = document.getElementById('storyViewerModal');
    modal.classList.add('active');

    // Progress bars
    const progressBar = document.getElementById('storyProgressBar');
    progressBar.innerHTML = currentStoryUser.stories.map((_, i) => `
        <div class="story-progress-segment">
            <div class="story-progress-fill" id="progress-${i}"></div>
        </div>
    `).join('');

    // User info
    document.getElementById('storyUserAvatar').innerHTML = story.avatar_url
        ? `<img src="${story.avatar_url}" alt="">`
        : `<i class="fas fa-user-circle"></i>`;
    document.getElementById('storyUserName').textContent = story.display_name || story.username;
    document.getElementById('storyTime').textContent = formatStoryTime(story.created_at);
    document.getElementById('storyCaption').textContent = story.caption || '';

    // Media
    const mediaContainer = document.getElementById('storyMedia');
    if (story.media_type === 'video') {
        mediaContainer.innerHTML = `<video src="${story.media_url}" autoplay loop muted></video>`;
    } else {
        mediaContainer.innerHTML = `<img src="${story.media_url}" alt="">`;
    }

    // Actions (like, reply, reactions, stats)
    const actions = document.getElementById('storyActions');
    if (story.user_id === currentUserId) {
        actions.innerHTML = `<button class="story-action-btn" onclick="showStoryStats(${story.id})"><i class="fas fa-chart-bar"></i></button>`;
    } else {
        actions.innerHTML = `
            <button class="story-action-btn" onclick="likeCurrentStory()"><i class="fas fa-heart"></i></button>
            <div class="story-reactions">
                <span class="story-reaction" onclick="reactToCurrentStory('❤️')">❤️</span>
                <span class="story-reaction" onclick="reactToCurrentStory('🔥')">🔥</span>
                <span class="story-reaction" onclick="reactToCurrentStory('👎')">👎</span>
                <span class="story-reaction" onclick="reactToCurrentStory('👍')">👍</span>
            </div>
        `;
    }

    // Start timer
    startStoryTimer();
}

function startStoryTimer() {
    if (storyProgressInterval) clearInterval(storyProgressInterval);
    const duration = 5000; // 5 seconds per story
    let startTime = Date.now();
    storyProgressInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min((elapsed / duration) * 100, 100);
        const bar = document.getElementById(`progress-${currentStoryIndex}`);
        if (bar) bar.style.width = progress + '%';
        if (progress >= 100) {
            clearInterval(storyProgressInterval);
            nextStory();
        }
    }, 50);
}

function nextStory() {
    if (currentStoryIndex < currentStoryUser.stories.length - 1) {
        currentStoryIndex++;
        showStoryModal();
    } else {
        // Move to next user
        const idx = currentStories.findIndex(s => s.user_id === currentStoryUser.user_id);
        if (idx < currentStories.length - 1) {
            currentStoryUser = currentStories[idx + 1];
            currentStoryIndex = 0;
            showStoryModal();
        } else {
            closeStoryViewer();
        }
    }
}

function previousStory() {
    if (currentStoryIndex > 0) {
        currentStoryIndex--;
        showStoryModal();
    }
}

function closeStoryViewer() {
    if (storyProgressInterval) clearInterval(storyProgressInterval);
    document.getElementById('storyViewerModal').classList.remove('active');
    loadStories(); // refresh unread statuses
}

// Story interactions (API calls)
async function likeCurrentStory() {
    const story = currentStoryUser.stories[currentStoryIndex];
    try {
        const res = await fetch(`/api/stories/${story.id}/like`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            // animate heart
        }
    } catch(e) {}
}

async function reactToCurrentStory(reaction) {
    const story = currentStoryUser.stories[currentStoryIndex];
    try {
        await fetch(`/api/stories/${story.id}/reaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reaction })
        });
    } catch(e) {}
}

async function showStoryStats(storyId) {
    // Fetch stats and show modal
}

function formatStoryTime(timestamp) {
    const diff = (Date.now() - new Date(timestamp).getTime()) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff/60) + 'm ago';
    if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
    return new Date(timestamp).toLocaleDateString();
}

// ============== WALLPAPER & CUSTOMIZATION ==============
function openChatCustomization() {
    // opens modal with wallpaper choices and text size
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:450px">
            <div class="modal-header"><h3><i class="fas fa-paint-brush"></i> Chat Style</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()"><i class="fas fa-times"></i></button></div>
            <div class="modal-body">
                <h4>Wallpaper</h4>
                <div class="wallpaper-options" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
                    ${['gradient1','gradient2','gradient3','gradient4','gradient5','default'].map(w => `
                        <div style="aspect-ratio:1; border-radius:8px; border:2px solid var(--border-color); cursor:pointer; ${w==='default'?"background:var(--bg-surface); display:flex; align-items:center; justify-content:center;":''}" onclick="setWallpaper('${w}')">${w==='default'?'Default':''}</div>
                    `).join('')}
                </div>
                <h4 style="margin-top:20px">Text Size</h4>
                <div style="display:flex; gap:8px">
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
    document.body.appendChild(modal);
}

function setWallpaper(wallpaper) {
    if (!activeChat) return;
    localStorage.setItem(`wallpaper_${activeChat.type}_${activeChat.id}`, wallpaper);
    applyChatCustomization();
}
function applyChatCustomization() {
    const container = document.getElementById('messagesContainer');
    if (!container) return;
    if (!activeChat) return;
    const w = localStorage.getItem(`wallpaper_${activeChat.type}_${activeChat.id}`) || 'default';
    container.classList.remove('wallpaper-gradient1','wallpaper-gradient2','wallpaper-gradient3','wallpaper-gradient4','wallpaper-gradient5');
    if (w !== 'default') container.classList.add(`wallpaper-${w}`);
}
function setTextSize(size) {
    const container = document.getElementById('messagesContainer');
    if (container) {
        container.classList.remove('text-small','text-medium','text-large');
        container.classList.add(`text-${size}`);
        localStorage.setItem('chat_text_size', size);
    }
}
function resetChatCustomization() {
    if (activeChat) localStorage.removeItem(`wallpaper_${activeChat.type}_${activeChat.id}`);
}

// ============== INITIALIZATION ==============
if (typeof loadStories === 'function') {
    // Override the original loadChatList to also refresh stories after load
    const origLoadChatList = loadChatList;
    loadChatList = async function() {
        await origLoadChatList();
        if (currentUserId) loadStories();
    };
}