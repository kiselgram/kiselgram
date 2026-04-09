/* static/js/app.js */

// ============ MENU FUNCTIONALITY ============
function initMenu() {
    const menuBtn = document.getElementById('menuBtn');
    const popoutMenu = document.getElementById('popoutMenu');
    const closePopoutBtn = document.getElementById('closePopoutBtn');
    const body = document.body;

    function openPopout() {
        body.classList.add('popout-open');
        menuBtn.classList.add('active');
    }

    function closePopout() {
        body.classList.remove('popout-open');
        menuBtn.classList.remove('active');
    }

    function togglePopout() {
        if (body.classList.contains('popout-open')) {
            closePopout();
        } else {
            openPopout();
        }
    }

    if (menuBtn) {
        menuBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            togglePopout();
        });
    }

    if (closePopoutBtn) {
        closePopoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closePopout();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && body.classList.contains('popout-open')) {
            closePopout();
            e.preventDefault();
        }
    });

    document.addEventListener('click', (event) => {
        if (!body.classList.contains('popout-open')) return;
        if (popoutMenu && popoutMenu.contains(event.target)) return;
        if (menuBtn && menuBtn.contains(event.target)) return;
        closePopout();
    });

    // Highlight current page
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.getAttribute('href') === currentPath) {
            item.style.background = '#eef2ff';
            item.style.color = '#5e72e4';
        }
    });

    // Logout button
    const logoutBtn = document.getElementById('logoutBtnSidebar');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            showConfirmModal('Sign Out', 'Are you sure you want to sign out?', () => {
                window.location.href = '/logout';
            });
        });
    }
}

// ============ PANEL MANAGEMENT ============
function closeAllPanels() {
    closeSettingsPanel();
    closePrivacyPanel();
    closeProfileModal();
    closeEditProfileModal();
}

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

// ============ PROFILE MODAL ============
function openProfileModal() {
    loadUserProfile();
    document.getElementById('profileModal').style.display = 'flex';
}

function closeProfileModal() {
    document.getElementById('profileModal').style.display = 'none';
}

function closeEditProfileModal() {
    document.getElementById('editProfileModal').style.display = 'none';
}

function loadUserProfile() {
    fetch('/api/spa/profile')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const user = data.user;

                // Update avatar
                const avatarContainer = document.getElementById('profileAvatar');
                if (user.avatar_url) {
                    avatarContainer.innerHTML = `<img src="${user.avatar_url}" class="profile-avatar" alt="${user.display_name}">`;
                } else {
                    avatarContainer.innerHTML = `<div class="profile-avatar-placeholder">${(user.display_name || user.username).charAt(0).toUpperCase()}</div>`;
                }

                // Update text fields
                document.getElementById('profileDisplayName').textContent = user.display_name || user.username;
                document.getElementById('profileUsername').textContent = '@' + user.username;
                document.getElementById('profileBio').textContent = user.bio || 'No bio yet';
                document.getElementById('profileDisplayNameValue').textContent = user.display_name || user.username;
                document.getElementById('profileUsernameValue').textContent = user.username;
                document.getElementById('profileBioValue').textContent = user.bio || 'Not set';

                // Update stats
                document.getElementById('followersCount').textContent = user.followers_count || 0;
                document.getElementById('followingCount').textContent = user.following_count || 0;
                document.getElementById('groupsCount').textContent = user.groups_count || 0;
            }
        })
        .catch(error => console.error('Error loading profile:', error));
}

function editProfile() {
    closeProfileModal();

    fetch('/api/spa/profile')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const user = data.user;
                document.getElementById('editDisplayName').value = user.display_name || '';
                document.getElementById('editUsername').value = user.username || '';
                document.getElementById('editBio').value = user.bio || '';
                document.getElementById('bioCharCount').textContent = (user.bio || '').length;
                document.getElementById('editProfileModal').style.display = 'flex';
            }
        });

    // Bio character counter
    document.getElementById('editBio').addEventListener('input', function() {
        document.getElementById('bioCharCount').textContent = this.value.length;
    });
}

function saveProfile() {
    const data = {
        display_name: document.getElementById('editDisplayName').value.trim(),
        username: document.getElementById('editUsername').value.trim(),
        bio: document.getElementById('editBio').value.trim()
    };

    fetch('/api/spa/profile/update', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Profile updated successfully!', 'success');
            closeEditProfileModal();
            openProfileModal();
        } else {
            showToast(data.error || 'Failed to update profile', 'error');
        }
    })
    .catch(error => {
        showToast('Error updating profile', 'error');
    });
}

// ============ AVATAR UPLOAD ============
function triggerAvatarUpload() {
    document.getElementById('avatarInput').click();
}

function uploadAvatar(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];

        // Check file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            showToast('File too large. Maximum size is 5MB', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('avatar', file);

        fetch('/files/upload_avatar', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Avatar updated successfully!', 'success');
                loadUserProfile();
            } else {
                showToast(data.error || 'Failed to upload avatar', 'error');
            }
        })
        .catch(error => {
            showToast('Error uploading avatar', 'error');
        });
    }
}

// ============ SETTINGS FUNCTIONS ============
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
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }

    showToast(`Theme set to ${theme}`, 'success');
}

function savePrivacySettings() {
    const visibility = document.getElementById('profileVisibility').value;
    localStorage.setItem('profileVisibility', visibility);
    showToast('Privacy settings saved', 'success');
    closePrivacyPanel();
}

// ============ ACCOUNT ACTIONS ============
function clearAllChats() {
    showConfirmModal('Clear All Chats', 'Are you sure you want to delete all your messages? This cannot be undone.', () => {
        fetch('/api/clear_all_chats', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast('All chats cleared', 'success');
                }
            });
    });
}

function deleteAccount() {
    showConfirmModal('Delete Account', 'This action cannot be undone. All your data will be permanently deleted.', () => {
        fetch('/api/delete_account', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast('Account deleted', 'success');
                    setTimeout(() => window.location.href = '/login', 1500);
                }
            });
    });
}

function exportData() {
    window.location.href = '/api/export_data';
}

function logout() {
    showConfirmModal('Sign Out', 'Are you sure you want to sign out?', () => {
        fetch('/api/spa/auth/logout', { method: 'POST' })
            .then(() => window.location.href = '/login');
    });
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

// ============ SERVICE WORKER ============
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(err => console.log('SW failed:', err));
}

// ============ MODAL SYSTEM ============
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
            <div class="modal-body">
                ${bodyHtml}
            </div>
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

    confirmBtn.onclick = () => {
        if (onConfirm) onConfirm(modal);
        closeModal();
    };
    cancelBtn.onclick = () => {
        if (onCancel) onCancel();
        closeModal();
    };
    closeBtn.onclick = closeModal;

    modal.onclick = (e) => {
        if (e.target === modal) closeModal();
    };

    return modal;
}

function showPromptModal(title, placeholder, onConfirm, defaultValue = '') {
    const bodyHtml = `
        <input type="text" id="modalInput" class="modal-input" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(defaultValue)}">
    `;
    showModal(title, bodyHtml, (modal) => {
        const input = modal.querySelector('#modalInput');
        if (input.value.trim()) {
            onConfirm(input.value.trim());
        }
    }, null, 'Submit', 'Cancel');
}

function showConfirmModal(title, message, onConfirm) {
    const bodyHtml = `<p>${escapeHtml(message)}</p>`;
    showModal(title, bodyHtml, onConfirm, null, 'Yes', 'No', true);
}

function showReactionPickerModal(messageId) {
    const reactions = ['👍', '❤️', '😂', '😮', '😢', '👏'];
    const bodyHtml = `
        <div class="reaction-picker-modal">
            ${reactions.map(r => `<button class="reaction-option" data-reaction="${r}">${r}</button>`).join('')}
        </div>
    `;
    showModal('Add Reaction', bodyHtml, (modal) => {}, null, 'Close', 'Cancel');

    setTimeout(() => {
        document.querySelectorAll('.reaction-option').forEach(btn => {
            btn.onclick = () => {
                const reaction = btn.dataset.reaction;
                addReaction(messageId, reaction);
                document.querySelector('.modal-overlay')?.remove();
            };
        });
    }, 100);
}

function showForwardModal(messageId, messageContent) {
    const bodyHtml = `
        <div class="radio-group" id="forwardTypeGroup">
            <div class="radio-option" data-type="user">
                <input type="radio" name="forwardType" value="user" checked>
                <div class="radio-label">
                    <div>💬 User</div>
                    <div class="radio-desc">Forward to a personal chat</div>
                </div>
            </div>
            <div class="radio-option" data-type="group">
                <input type="radio" name="forwardType" value="group">
                <div class="radio-label">
                    <div>👥 Group</div>
                    <div class="radio-desc">Forward to a group chat</div>
                </div>
            </div>
            <div class="radio-option" data-type="channel">
                <input type="radio" name="forwardType" value="channel">
                <div class="radio-label">
                    <div>📢 Channel</div>
                    <div class="radio-desc">Forward to a channel</div>
                </div>
            </div>
        </div>
        <input type="text" id="targetIdInput" class="modal-input" placeholder="Enter ID (e.g., 123)" autocomplete="off">
        <small style="color: var(--text-muted); font-size: 12px;">You can find the ID in the URL when viewing a chat</small>
    `;

    showModal('Forward Message', bodyHtml, (modal) => {
        const selectedType = modal.querySelector('input[name="forwardType"]:checked').value;
        const targetId = modal.querySelector('#targetIdInput').value.trim();
        if (!targetId) {
            showToast('Please enter a target ID', 'error');
            return;
        }

        fetch('/api/spa/messages/forward', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message_id: messageId,
                target_type: selectedType,
                target_id: targetId
            })
        }).then(response => response.json())
          .then(data => {
              if (data.success) {
                  showToast('Message forwarded successfully!', 'success');
              } else {
                  showToast('Failed to forward message', 'error');
              }
          });
    }, null, 'Forward', 'Cancel');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'error' ? '#f5365c' : type === 'success' ? '#2dce89' : '#5e72e4'};
        color: white;
        padding: 12px 24px;
        border-radius: 50px;
        font-size: 14px;
        z-index: 3000;
        animation: fadeIn 0.3s ease-out;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
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

// ============ REACTIONS ============
window.addReaction = async function(messageId, reactionType) {
    try {
        const response = await fetch('/api/spa/reactions/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_id: messageId, reaction_type: reactionType })
        });
        const data = await response.json();
        if (data.success) {
            updateMessageReactions(messageId, data.reactions);
            showToast('Reaction added!', 'success');
        }
    } catch (error) {
        console.error('Error adding reaction:', error);
    }
};

window.updateMessageReactions = function(messageId, reactions) {
    const reactionsContainer = document.querySelector(`#message-${messageId} .message-reactions`);
    if (!reactionsContainer) return;
    if (!reactions || reactions.length === 0) {
        reactionsContainer.innerHTML = '';
        return;
    }
    reactionsContainer.innerHTML = reactions.map(r => `
        <div class="reaction-badge" onclick="event.stopPropagation(); addReaction(${messageId}, '${r.type}')">
            <span class="reaction-emoji-small">${r.type}</span>
            <span class="reaction-count">${r.count}</span>
        </div>
    `).join('');
};

window.loadMessageReactions = async function(messageId) {
    try {
        const response = await fetch(`/api/spa/reactions/${messageId}`);
        const data = await response.json();
        if (data.success && data.reactions) {
            updateMessageReactions(messageId, data.reactions);
        }
    } catch (error) {
        console.error('Error loading reactions:', error);
    }
};