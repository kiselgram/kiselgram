// static/js/spa_app_prem.js
// Kiselgram Premium Version - Extended Features
// Version 4.0.0

(function() {
    'use strict';

    console.log('✨ Kiselgram Premium initializing...');

    // ============ PREMIUM STATE ============

    window.isPremium = true;

    // All fonts available for premium users
    const PREMIUM_FONTS = [
        'Inter', 'Satoshi', 'DM Sans', 'Roboto', 'Poppins',
        'Public Sans', 'Work Sans', 'SF Pro', 'Nunito',
        'Space Grotesk', 'Courier New'
    ];

    // Story state
    window.currentStories = window.currentStories || [];
    window.currentStoryIndex = window.currentStoryIndex || 0;
    window.currentStoryUser = window.currentStoryUser || null;
    window.storyViewerActive = false;
    window.storyProgressInterval = null;

    // ============ INITIALIZATION ============

    function initializePremium() {
        // Override premium status
        if (typeof window.isPremium !== 'undefined') {
            window.isPremium = true;
        }

        // Update UI for premium
        updateFontOptionsUI();
        unlockPremiumFeatures();

        // Override functions after ensuring base script loaded
        overrideStoriesFunctions();
        overrideCustomizationFunctions();
        overrideSettingsFunctions();

        console.log('✅ Kiselgram Premium activated!');
    }

    // Wait for DOM and base script
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initializePremium, 100);
        });
    } else {
        setTimeout(initializePremium, 100);
    }

    // ============ UI UPDATES ============

    function updateFontOptionsUI() {
        const fontOptions = document.querySelectorAll('.font-option');
        fontOptions.forEach(opt => {
            opt.classList.remove('locked');
            const tag = opt.querySelector('.font-tag');
            if (tag && tag.textContent === 'Premium') {
                tag.remove();
            }
        });
    }

    function unlockPremiumFeatures() {
        // Remove premium locks from UI
        document.querySelectorAll('.premium-locked').forEach(el => {
            el.classList.remove('premium-locked');
        });

        // Update settings panel if exists
        const premiumBtn = document.querySelector('[onclick*="premium"]');
        if (premiumBtn) {
            premiumBtn.innerHTML = premiumBtn.innerHTML.replace('🔒', '✨');
        }
    }

    // ============ STORIES OVERRIDES ============

    function overrideStoriesFunctions() {
        // Override loadStories
        window.loadStories = async function() {
            if (!window.currentUserId) {
                console.log('No current user, skipping stories load');
                return;
            }

            try {
                const response = await fetch('/api/stories');
                const data = await response.json();

                if (data.success) {
                    window.currentStories = data.stories || [];
                    renderStoriesRowPremium();
                }
            } catch (error) {
                console.error('Error loading stories:', error);
            }
        };

        // Override renderStoriesRow
        window.renderStoriesRow = renderStoriesRowPremium;

        // Override showCreateStoryModal
        window.showCreateStoryModal = showCreateStoryModalPremium;

        // Add story viewer functions
        window.openStoryViewer = openStoryViewerPremium;
        window.closeStoryViewer = closeStoryViewerPremium;
        window.nextStory = nextStoryPremium;
        window.previousStory = previousStoryPremium;
        window.likeCurrentStory = likeCurrentStoryPremium;
        window.deleteCurrentStory = deleteCurrentStoryPremium;
        window.sendStoryReply = sendStoryReplyPremium;
    }

    function renderStoriesRowPremium() {
        const storiesRow = document.getElementById('storiesRow');
        if (!storiesRow) return;

        const stories = window.currentStories || [];
        const currentUserId = window.currentUserId;
        const currentUserAvatar = window.currentUserAvatar || '?';

        let html = '';

        // Check if current user has a story
        const currentUserHasStory = stories.some(s => s.user_id === currentUserId);

        // Add story button for current user
        html += `
            <div class="story-item" onclick="showCreateStoryModal()">
                <div class="story-avatar ${currentUserHasStory ? '' : 'add-story'}">
                    ${currentUserHasStory ?
                        `<div class="story-avatar-placeholder" style="background: linear-gradient(135deg, #fb6340, #2dce89);">${currentUserAvatar}</div>` :
                        `<div class="add-story-btn" style="background: linear-gradient(135deg, #fb6340, #2dce89); color: white;">+</div>`
                    }
                </div>
                <span class="story-username">Your story</span>
            </div>
        `;

        // Add other users' stories
        for (const userStory of stories) {
            if (userStory.user_id === currentUserId) continue;

            const firstStory = userStory.stories?.[0];
            const hasUnviewed = userStory.has_unviewed;

            html += `
                <div class="story-item" onclick="openStoryViewer(${userStory.user_id})">
                    <div class="story-avatar ${hasUnviewed ? 'unviewed' : 'viewed'}">
                        ${firstStory && firstStory.media_url && firstStory.media_type === 'image' ?
                            `<img src="${firstStory.media_url}" alt="${escapeHtmlSafe(userStory.display_name)}">` :
                            `<div class="story-avatar-placeholder" style="background: linear-gradient(135deg, #fb6340, #2dce89);">${userStory.avatar_letter || '?'}</div>`
                        }
                    </div>
                    <span class="story-username">${escapeHtmlSafe(userStory.display_name || userStory.username)}</span>
                </div>
            `;
        }

        // If no other stories, show placeholder
        if (stories.length === 0 || (stories.length === 1 && stories[0].user_id === currentUserId)) {
            html += `
                <div style="display: flex; align-items: center; padding: 8px 16px; color: var(--text-muted); font-size: 13px;">
                    <span>No stories yet</span>
                </div>
            `;
        }

        storiesRow.innerHTML = html;
    }

    function showCreateStoryModalPremium() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'storyCreateModal';
        modal.innerHTML = `
            <div class="modal-container story-create-modal" style="max-height: 90vh; overflow-y: auto;">
                <div class="modal-header" style="background: linear-gradient(135deg, #fb6340, #2dce89); color: white;">
                    <h3>Create Story</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color: white;">✕</button>
                </div>
                <div class="modal-body">
                    <div class="story-media-upload" onclick="document.getElementById('storyMediaInput').click()">
                        <div class="upload-placeholder" id="storyMediaPreview">
                            <span style="font-size: 48px;">📸</span>
                            <p>Click to upload photo or video</p>
                            <small style="color: var(--text-muted);">Supports: JPG, PNG, GIF, MP4, MOV</small>
                        </div>
                        <input type="file" id="storyMediaInput" accept="image/*,video/*" style="display: none;" onchange="previewStoryMedia(this)">
                    </div>

                    <label class="modal-label" style="margin-top: 16px;">Caption (optional)</label>
                    <textarea id="storyCaption" class="modal-input" placeholder="Add a caption..." rows="3" maxlength="200"></textarea>
                    <small style="color: var(--text-muted); display: block; margin-top: 4px;">
                        <span id="storyCaptionCount">0</span>/200 characters
                    </small>

                    <div style="background: linear-gradient(135deg, rgba(251, 99, 64, 0.1), rgba(45, 206, 137, 0.1)); border-radius: 12px; padding: 12px; margin-top: 16px;">
                        <p style="font-size: 13px; color: var(--text-secondary);">
                            <strong>Stories disappear after 24 hours</strong><br>
                            Only your contacts can see your stories.
                        </p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="modal-btn modal-btn-primary" onclick="uploadStoryPremium()" style="background: linear-gradient(135deg, #fb6340, #2dce89);">
                        Post Story
                    </button>
                </div>
            </div>
        `;

        const modalRoot = document.getElementById('modalRoot');
        if (modalRoot) {
            modalRoot.appendChild(modal);
        } else {
            document.body.appendChild(modal);
        }

        const captionInput = document.getElementById('storyCaption');
        const captionCount = document.getElementById('storyCaptionCount');
        if (captionInput) {
            captionInput.addEventListener('input', function() {
                captionCount.textContent = this.value.length;
            });
        }
    }

    window.previewStoryMedia = function(input) {
        const file = input.files[0];
        if (!file) return;

        const preview = document.getElementById('storyMediaPreview');
        if (!preview) return;

        const isVideo = file.type.startsWith('video/');

        preview.innerHTML = '';

        if (isVideo) {
            const video = document.createElement('video');
            video.src = URL.createObjectURL(file);
            video.controls = false;
            video.autoplay = true;
            video.loop = true;
            video.muted = true;
            video.style.width = '100%';
            video.style.height = '100%';
            video.style.objectFit = 'cover';
            video.style.borderRadius = '8px';
            preview.appendChild(video);
        } else {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            img.style.borderRadius = '8px';
            preview.appendChild(img);
        }
    };

    window.uploadStoryPremium = async function() {
        const fileInput = document.getElementById('storyMediaInput');
        const caption = document.getElementById('storyCaption')?.value || '';

        if (!fileInput || !fileInput.files[0]) {
            showToastSafe('Please select a photo or video', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('media', fileInput.files[0]);
        formData.append('caption', caption);

        try {
            const response = await fetch('/api/stories/create', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                closeAllModalsSafe();
                showToastSafe('Story posted!', 'success');
                if (typeof window.loadStories === 'function') {
                    window.loadStories();
                }
            } else {
                showToastSafe(data.error || 'Failed to post story', 'error');
            }
        } catch (error) {
            console.error('Error uploading story:', error);
            showToastSafe('Error posting story', 'error');
        }
    };

    // Story Viewer Functions
    function openStoryViewerPremium(userId) {
        const stories = window.currentStories || [];
        const userStory = stories.find(s => s.user_id === userId);
        if (!userStory) return;

        window.currentStoryUser = userStory;
        window.currentStoryIndex = 0;
        window.storyViewerActive = true;

        renderStoryViewerPremium();
        markStoryViewedPremium(userStory.stories[0]?.id);
    }

    function renderStoryViewerPremium() {
        const userStory = window.currentStoryUser;
        if (!userStory) return;

        const story = userStory.stories[window.currentStoryIndex];
        if (!story) return;

        const viewer = document.createElement('div');
        viewer.className = 'story-viewer';
        viewer.id = 'storyViewer';

        viewer.innerHTML = `
            <div class="story-viewer-header">
                <div class="story-progress-container">
                    ${userStory.stories.map((_, i) => `
                        <div class="story-progress-bar-container">
                            <div class="story-progress-bar ${i < window.currentStoryIndex ? 'completed' : ''}"
                                 id="storyProgress${i}" style="background: linear-gradient(90deg, #fb6340, #2dce89);"></div>
                        </div>
                    `).join('')}
                </div>
                <div class="story-viewer-user">
                    <div class="story-viewer-avatar" style="background: linear-gradient(135deg, #fb6340, #2dce89);">
                        ${userStory.avatar_letter || '?'}
                    </div>
                    <div class="story-viewer-info">
                        <span class="story-viewer-name">${escapeHtmlSafe(userStory.display_name)}</span>
                        <span class="story-viewer-time">${formatStoryTimeSafe(story.created_at)}</span>
                    </div>
                </div>
                <button class="story-viewer-close" onclick="closeStoryViewer()">✕</button>
            </div>

            <div class="story-viewer-content" id="storyViewerContent">
                ${story.media_type === 'video' ?
                    `<video src="${story.media_url}" autoplay loop muted playsinline></video>` :
                    `<img src="${story.media_url}" alt="Story">`
                }
                ${story.caption ? `<div class="story-caption">${escapeHtmlSafe(story.caption)}</div>` : ''}
            </div>

            <div class="story-viewer-footer">
                <div class="story-reply-input">
                    <input type="text" placeholder="Send message..." id="storyReplyInput">
                    <button onclick="sendStoryReply()" style="background: linear-gradient(135deg, #fb6340, #2dce89);">➤</button>
                </div>
                <div class="story-actions">
                    <button onclick="likeCurrentStory()" id="storyLikeBtn">
                        ${story.liked ? '❤️' : '🤍'} <span id="storyLikeCount">${story.like_count || 0}</span>
                    </button>
                    <button onclick="deleteCurrentStory()" ${userStory.user_id !== window.currentUserId ? 'style="display:none"' : ''}>
                        🗑️
                    </button>
                </div>
            </div>

            <div class="story-nav">
                <div class="story-nav-left" onclick="previousStory()"></div>
                <div class="story-nav-right" onclick="nextStory()"></div>
            </div>
        `;

        document.body.appendChild(viewer);
        document.body.style.overflow = 'hidden';

        startStoryProgressPremium();
    }

    function startStoryProgressPremium() {
        if (window.storyProgressInterval) {
            clearInterval(window.storyProgressInterval);
        }

        const progressBar = document.getElementById(`storyProgress${window.currentStoryIndex}`);
        if (!progressBar) return;

        let width = 0;
        const duration = 5000;
        const interval = 50;
        const increment = (interval / duration) * 100;

        window.storyProgressInterval = setInterval(() => {
            width += increment;
            progressBar.style.width = `${width}%`;

            if (width >= 100) {
                clearInterval(window.storyProgressInterval);
                nextStoryPremium();
            }
        }, interval);
    }

    function closeStoryViewerPremium() {
        window.storyViewerActive = false;
        if (window.storyProgressInterval) {
            clearInterval(window.storyProgressInterval);
            window.storyProgressInterval = null;
        }

        const viewer = document.getElementById('storyViewer');
        if (viewer) viewer.remove();

        document.body.style.overflow = '';

        if (typeof window.loadStories === 'function') {
            window.loadStories();
        }
    }

    function nextStoryPremium() {
        const userStory = window.currentStoryUser;
        const stories = window.currentStories || [];

        if (window.currentStoryIndex < userStory.stories.length - 1) {
            window.currentStoryIndex++;
            markStoryViewedPremium(userStory.stories[window.currentStoryIndex].id);
            updateStoryViewerContentPremium();
        } else {
            const currentUserIndex = stories.findIndex(s => s.user_id === userStory.user_id);
            if (currentUserIndex < stories.length - 1) {
                window.currentStoryUser = stories[currentUserIndex + 1];
                window.currentStoryIndex = 0;
                markStoryViewedPremium(window.currentStoryUser.stories[0].id);
                updateStoryViewerContentPremium();
            } else {
                closeStoryViewerPremium();
            }
        }
    }

    function previousStoryPremium() {
        if (window.currentStoryIndex > 0) {
            window.currentStoryIndex--;
            updateStoryViewerContentPremium();
        } else {
            const stories = window.currentStories || [];
            const currentUserIndex = stories.findIndex(s => s.user_id === window.currentStoryUser.user_id);
            if (currentUserIndex > 0) {
                window.currentStoryUser = stories[currentUserIndex - 1];
                window.currentStoryIndex = window.currentStoryUser.stories.length - 1;
                updateStoryViewerContentPremium();
            }
        }
    }

    function updateStoryViewerContentPremium() {
        const content = document.getElementById('storyViewerContent');
        const story = window.currentStoryUser.stories[window.currentStoryIndex];
        if (!content || !story) return;

        content.innerHTML = `
            ${story.media_type === 'video' ?
                `<video src="${story.media_url}" autoplay loop muted playsinline></video>` :
                `<img src="${story.media_url}" alt="Story">`
            }
            ${story.caption ? `<div class="story-caption">${escapeHtmlSafe(story.caption)}</div>` : ''}
        `;

        const nameEl = document.querySelector('.story-viewer-name');
        const timeEl = document.querySelector('.story-viewer-time');
        if (nameEl) nameEl.textContent = window.currentStoryUser.display_name;
        if (timeEl) timeEl.textContent = formatStoryTimeSafe(story.created_at);

        const likeBtn = document.getElementById('storyLikeBtn');
        if (likeBtn) {
            likeBtn.innerHTML = `${story.liked ? '❤️' : '🤍'} <span id="storyLikeCount">${story.like_count || 0}</span>`;
        }

        const deleteBtn = document.querySelector('.story-actions button:last-child');
        if (deleteBtn) {
            deleteBtn.style.display = window.currentStoryUser.user_id === window.currentUserId ? 'block' : 'none';
        }

        document.querySelectorAll('.story-progress-bar').forEach((bar, i) => {
            bar.classList.toggle('completed', i < window.currentStoryIndex);
            if (i === window.currentStoryIndex) {
                bar.style.width = '0%';
            }
        });

        startStoryProgressPremium();
    }

    async function markStoryViewedPremium(storyId) {
        if (!storyId) return;

        try {
            await fetch(`/api/stories/${storyId}/view`, { method: 'POST' });
            const story = window.currentStoryUser?.stories?.find(s => s.id === storyId);
            if (story) story.viewed = true;
        } catch (error) {
            console.error('Error marking story viewed:', error);
        }
    }

    async function likeCurrentStoryPremium() {
        const story = window.currentStoryUser?.stories?.[window.currentStoryIndex];
        if (!story) return;

        try {
            const response = await fetch(`/api/stories/${story.id}/like`, { method: 'POST' });
            const data = await response.json();

            if (data.success) {
                story.liked = data.liked;
                story.like_count = data.like_count;

                const likeBtn = document.getElementById('storyLikeBtn');
                if (likeBtn) {
                    likeBtn.innerHTML = `${data.liked ? '❤️' : '🤍'} <span id="storyLikeCount">${data.like_count}</span>`;
                }
            }
        } catch (error) {
            console.error('Error liking story:', error);
        }
    }

    async function deleteCurrentStoryPremium() {
        if (!confirm('Delete this story?')) return;

        const story = window.currentStoryUser?.stories?.[window.currentStoryIndex];
        if (!story) return;

        try {
            const response = await fetch(`/api/stories/${story.id}`, { method: 'DELETE' });
            const data = await response.json();

            if (data.success) {
                window.currentStoryUser.stories.splice(window.currentStoryIndex, 1);

                if (window.currentStoryUser.stories.length === 0) {
                    const stories = window.currentStories || [];
                    const userIndex = stories.findIndex(s => s.user_id === window.currentStoryUser.user_id);
                    if (userIndex > -1) {
                        stories.splice(userIndex, 1);
                        window.currentStories = stories;
                    }
                    closeStoryViewerPremium();
                    if (typeof window.loadStories === 'function') {
                        window.loadStories();
                    }
                } else {
                    if (window.currentStoryIndex >= window.currentStoryUser.stories.length) {
                        window.currentStoryIndex = window.currentStoryUser.stories.length - 1;
                    }
                    updateStoryViewerContentPremium();
                }

                showToastSafe('Story deleted', 'success');
            }
        } catch (error) {
            console.error('Error deleting story:', error);
            showToastSafe('Error deleting story', 'error');
        }
    }

    function sendStoryReplyPremium() {
        const input = document.getElementById('storyReplyInput');
        const message = input?.value?.trim();

        if (!message) return;

        const userId = window.currentStoryUser?.user_id;
        if (userId && typeof window.openChat === 'function') {
            window.openChat('personal', userId);

            setTimeout(() => {
                const messageInput = document.getElementById('messageInput');
                if (messageInput) {
                    messageInput.value = message;
                    const sendBtn = document.getElementById('sendBtn');
                    if (sendBtn) sendBtn.disabled = false;
                }
            }, 500);
        }

        closeStoryViewerPremium();
    }

    // ============ CUSTOMIZATION OVERRIDES ============

    function overrideCustomizationFunctions() {
        window.openChatCustomization = openChatCustomizationPremium;
        window.setChatBubbleColor = setChatBubbleColorPremium;
        window.setWallpaper = setWallpaperPremium;
        window.setTextSize = setTextSizePremium;
        window.applyChatCustomization = applyChatCustomizationPremium;
        window.resetChatCustomization = resetChatCustomizationPremium;
    }

    function openChatCustomizationPremium() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-container" style="max-width: 450px; max-height: 80vh; overflow-y: auto;">
                <div class="modal-header" style="background: linear-gradient(135deg, #fb6340, #2dce89); color: white;">
                    <h3>Chat Customization</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()" style="color: white;">✕</button>
                </div>
                <div class="modal-body">
                    <div class="settings-section">
                        <h3>Chat Bubble Color</h3>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                            ${['#fb6340', '#2dce89', '#5e72e4', '#f5365c', '#8965e0', '#11cdef'].map(color => `
                                <div style="width: 40px; height: 40px; border-radius: 50%; background: ${color}; cursor: pointer; border: 2px solid var(--border-color);"
                                     onclick="setChatBubbleColor('${color}')"></div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="settings-section">
                        <h3>Wallpaper</h3>
                        <div class="wallpaper-options" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;">
                            <div style="aspect-ratio: 1; border-radius: 8px; border: 2px solid var(--border-color); cursor: pointer; background: var(--bg-surface); display: flex; align-items: center; justify-content: center;" onclick="setWallpaper('default')">Default</div>
                            <div style="aspect-ratio: 1; border-radius: 8px; border: 2px solid var(--border-color); cursor: pointer; background: linear-gradient(135deg, #fb6340, #f093fb);" onclick="setWallpaper('gradient1')"></div>
                            <div style="aspect-ratio: 1; border-radius: 8px; border: 2px solid var(--border-color); cursor: pointer; background: linear-gradient(135deg, #2dce89, #4facfe);" onclick="setWallpaper('gradient2')"></div>
                            <div style="aspect-ratio: 1; border-radius: 8px; border: 2px solid var(--border-color); cursor: pointer; background: linear-gradient(135deg, #667eea, #764ba2);" onclick="setWallpaper('gradient3')"></div>
                            <div style="aspect-ratio: 1; border-radius: 8px; border: 2px solid var(--border-color); cursor: pointer; background: linear-gradient(135deg, #f5576c, #f093fb);" onclick="setWallpaper('gradient4')"></div>
                            <div style="aspect-ratio: 1; border-radius: 8px; border: 2px solid var(--border-color); cursor: pointer; background: linear-gradient(135deg, #43e97b, #38f9d7);" onclick="setWallpaper('gradient5')"></div>
                        </div>
                    </div>

                    <div class="settings-section">
                        <h3>Text Size</h3>
                        <div style="display: flex; gap: 8px;">
                            <button class="modal-btn modal-btn-secondary" onclick="setTextSize('small')">Small</button>
                            <button class="modal-btn modal-btn-secondary" onclick="setTextSize('medium')">Medium</button>
                            <button class="modal-btn modal-btn-secondary" onclick="setTextSize('large')">Large</button>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-secondary" onclick="resetChatCustomization()">Reset</button>
                    <button class="modal-btn modal-btn-primary" onclick="this.closest('.modal-overlay').remove()" style="background: linear-gradient(135deg, #fb6340, #2dce89);">Done</button>
                </div>
            </div>
        `;

        const modalRoot = document.getElementById('modalRoot');
        if (modalRoot) {
            modalRoot.appendChild(modal);
        } else {
            document.body.appendChild(modal);
        }
    }

    function setChatBubbleColorPremium(color) {
        if (window.activeChat) {
            const key = `chat_color_${window.activeChat.type}_${window.activeChat.id}`;
            localStorage.setItem(key, color);
        }
        showToastSafe('Bubble color updated', 'success');
    }

    function setWallpaperPremium(wallpaper) {
        if (window.activeChat) {
            const key = `wallpaper_${window.activeChat.type}_${window.activeChat.id}`;
            localStorage.setItem(key, wallpaper);
            applyChatCustomizationPremium();
        }
        showToastSafe('Wallpaper updated', 'success');
    }

    function setTextSizePremium(size) {
        const container = document.getElementById('messagesContainer');
        if (container) {
            container.classList.remove('text-small', 'text-medium', 'text-large');
            container.classList.add(`text-${size}`);
            localStorage.setItem('chat_text_size', size);
        }
        showToastSafe('Text size updated', 'success');
    }

    function applyChatCustomizationPremium() {
        if (!window.activeChat) return;

        const container = document.getElementById('messagesContainer');
        if (!container) return;

        const wallpaperKey = `wallpaper_${window.activeChat.type}_${window.activeChat.id}`;
        const wallpaper = localStorage.getItem(wallpaperKey) || 'default';

        container.classList.remove('wallpaper-gradient1', 'wallpaper-gradient2', 'wallpaper-gradient3',
                               'wallpaper-gradient4', 'wallpaper-gradient5');
        if (wallpaper !== 'default') {
            container.classList.add(`wallpaper-${wallpaper}`);
        }

        const textSize = localStorage.getItem('chat_text_size') || 'medium';
        container.classList.remove('text-small', 'text-medium', 'text-large');
        container.classList.add(`text-${textSize}`);
    }

    function resetChatCustomizationPremium() {
        if (!window.activeChat) return;

        localStorage.removeItem(`chat_color_${window.activeChat.type}_${window.activeChat.id}`);
        localStorage.removeItem(`wallpaper_${window.activeChat.type}_${window.activeChat.id}`);
        localStorage.removeItem('chat_text_size');

        const container = document.getElementById('messagesContainer');
        if (container) {
            container.classList.remove('wallpaper-gradient1', 'wallpaper-gradient2', 'wallpaper-gradient3',
                                       'wallpaper-gradient4', 'wallpaper-gradient5',
                                       'text-small', 'text-medium', 'text-large');
            container.classList.add('text-medium');
        }

        showToastSafe('Customization reset', 'success');
    }

    // ============ SETTINGS OVERRIDES ============

    function overrideSettingsFunctions() {
        // Override setFont to allow all fonts
        const originalSetFont = window.setFont;
        window.setFont = function(element) {
            const fontName = element.querySelector('.font-name')?.textContent?.split(' ')[0];

            // Premium users can use any font
            document.querySelectorAll('.font-option').forEach(opt => opt.classList.remove('active'));
            element.classList.add('active');

            const fontFamily = element.dataset.font;
            document.body.style.setProperty('--font-family', fontFamily);
            localStorage.setItem('kiselgram_font', fontFamily);

            showToastSafe('Font updated', 'success');
        };

        // Override showPremiumModal to do nothing for premium users
        window.showPremiumModal = function(feature) {
            console.log('Premium feature accessed:', feature);
            // Premium users don't see upgrade prompts
        };
    }

    // ============ UTILITY FUNCTIONS ============

    function escapeHtmlSafe(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatStoryTimeSafe(timestamp) {
        if (!timestamp) return '';

        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    }

    function showToastSafe(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
            return;
        }

        // Fallback toast
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'success' ? '#2dce89' : type === 'error' ? '#fb6340' : '#5e72e4'};
            color: white;
            padding: 12px 24px;
            border-radius: 30px;
            font-weight: 500;
            z-index: 9999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    function closeAllModalsSafe() {
        document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
        const profileModal = document.getElementById('profileModal');
        const editProfileModal = document.getElementById('editProfileModal');
        if (profileModal) profileModal.style.display = 'none';
        if (editProfileModal) editProfileModal.style.display = 'none';
    }

    // ============ EXPORT ============

    // Make sure all story functions are globally available
    window.loadStories = window.loadStories || loadStories;
    window.renderStoriesRow = window.renderStoriesRow || renderStoriesRowPremium;
    window.showCreateStoryModal = window.showCreateStoryModal || showCreateStoryModalPremium;
    window.previewStoryMedia = window.previewStoryMedia || previewStoryMedia;
    window.uploadStoryPremium = window.uploadStoryPremium || uploadStoryPremium;
    window.openStoryViewer = window.openStoryViewer || openStoryViewerPremium;
    window.closeStoryViewer = window.closeStoryViewer || closeStoryViewerPremium;
    window.nextStory = window.nextStory || nextStoryPremium;
    window.previousStory = window.previousStory || previousStoryPremium;
    window.likeCurrentStory = window.likeCurrentStory || likeCurrentStoryPremium;
    window.deleteCurrentStory = window.deleteCurrentStory || deleteCurrentStoryPremium;
    window.sendStoryReply = window.sendStoryReply || sendStoryReplyPremium;

    console.log('✨ Kiselgram Premium fully loaded!');

})();