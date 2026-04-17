// static/js/mobile-spec.js
// Mobile-specific behavior – works alongside free.js without modifying it.

(function() {
    'use strict';

    if (window.innerWidth > 768) return; // Only run on mobile

    console.log('📱 Mobile optimizations active');

    // ========== Helper: Adjust panel views to leave room for bottom nav ==========
    function adjustPanelBottom() {
        const navHeight = 60;
        const panels = ['contactsView', 'createGroupView', 'createChannelView', 'chatView'];
        panels.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.style.bottom = navHeight + 'px';
            }
        });
        const settingsPanel = document.getElementById('settingsPanel');
        if (settingsPanel) {
            settingsPanel.style.bottom = navHeight + 'px';
        }
        const privacyPanel = document.getElementById('privacyPanel');
        if (privacyPanel) {
            privacyPanel.style.bottom = navHeight + 'px';
        }
        const overlay = document.getElementById('panelOverlay');
        if (overlay) {
            overlay.style.bottom = navHeight + 'px';
        }
    }

    // ========== Move search to main area ==========
    function moveSearchToMain() {
        const searchContainer = document.querySelector('.global-search-container');
        const chatArea = document.getElementById('chatArea');
        const storiesRow = document.getElementById('storiesRow');

        if (searchContainer && chatArea) {
            const parent = searchContainer.parentNode;
            if (parent) parent.removeChild(searchContainer);
            chatArea.insertBefore(searchContainer, chatArea.firstChild);

            if (storiesRow) {
                const storiesParent = storiesRow.parentNode;
                if (storiesParent) storiesParent.removeChild(storiesRow);
                searchContainer.insertAdjacentElement('afterend', storiesRow);
            }
        }
    }

    // ========== Bottom navigation ==========
    const navItems = document.querySelectorAll('.bottom-nav-item');

    function setActiveTab(viewId) {
        navItems.forEach(item => {
            const isActive = item.dataset.view === viewId;
            item.classList.toggle('active', isActive);
        });

        // Hide all panel views
        ['contactsView', 'createGroupView', 'createChannelView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });

        const emptyChat = document.getElementById('emptyChat');
        const chatView = document.getElementById('chatView');
        const contactsView = document.getElementById('contactsView');
        const searchContainer = document.querySelector('.global-search-container');
        const storiesRow = document.getElementById('storiesRow');

        if (viewId === 'contacts') {
            if (contactsView) contactsView.style.display = 'flex';
            if (emptyChat) emptyChat.style.display = 'none';
            if (chatView) chatView.style.display = 'none';
            if (searchContainer) searchContainer.style.display = 'none';
            if (storiesRow) storiesRow.style.display = 'none';
        } else if (viewId === 'chats') {
            if (emptyChat) emptyChat.style.display = 'flex';
            if (contactsView) contactsView.style.display = 'none';
            if (chatView) chatView.style.display = 'none';
            if (searchContainer) searchContainer.style.display = 'block';
            if (storiesRow) storiesRow.style.display = 'flex';
            if (typeof window.loadChatList === 'function') {
                window.loadChatList();
            }
        } else if (viewId === 'settings') {
            if (typeof window.openSettingsPanel === 'function') {
                window.openSettingsPanel();
            }
        } else if (viewId === 'search') {
            // Focus global search
            if (emptyChat) emptyChat.style.display = 'flex';
            if (contactsView) contactsView.style.display = 'none';
            if (chatView) chatView.style.display = 'none';
            if (searchContainer) searchContainer.style.display = 'block';
            if (storiesRow) storiesRow.style.display = 'flex';
            const searchInput = document.getElementById('globalSearchInput');
            if (searchInput) {
                searchInput.focus();
                // Trigger search results dropdown
                searchInput.dispatchEvent(new Event('focus'));
            }
        }

        adjustPanelBottom();
    }

    // ========== Override existing functions ==========
    const originalShowContacts = window.showContactsView;
    window.showContactsView = function() {
        if (originalShowContacts) originalShowContacts.call(this);
        setActiveTab('contacts');
    };

    const originalShowChats = window.showChatsView;
    window.showChatsView = function() {
        if (originalShowChats) originalShowChats.call(this);
        setActiveTab('chats');
    };

    const originalOpenSettings = window.openSettingsPanel;
    window.openSettingsPanel = function() {
        if (originalOpenSettings) originalOpenSettings.call(this);
        setActiveTab('settings');
    };

    const originalOpenChat = window.openChat;
    window.openChat = function(type, id) {
        if (originalOpenChat) originalOpenChat.call(this, type, id);
        const emptyChat = document.getElementById('emptyChat');
        const chatView = document.getElementById('chatView');
        const searchContainer = document.querySelector('.global-search-container');
        const storiesRow = document.getElementById('storiesRow');
        if (emptyChat) emptyChat.style.display = 'none';
        if (chatView) chatView.style.display = 'flex';
        if (searchContainer) searchContainer.style.display = 'none';
        if (storiesRow) storiesRow.style.display = 'none';
        setActiveTab('chats');
        adjustPanelBottom();
    };

    const originalHideContacts = window.hideContactsView;
    window.hideContactsView = function() {
        if (originalHideContacts) originalHideContacts.call(this);
        setActiveTab('chats');
        const emptyChat = document.getElementById('emptyChat');
        if (emptyChat) emptyChat.style.display = 'flex';
        const searchContainer = document.querySelector('.global-search-container');
        const storiesRow = document.getElementById('storiesRow');
        if (searchContainer) searchContainer.style.display = 'block';
        if (storiesRow) storiesRow.style.display = 'flex';
    };

    // ========== Sync mobile chat list ==========
    function syncMobileChatList() {
        const realList = document.getElementById('chatList');
        const mobileList = document.getElementById('mobileChatList');
        if (realList && mobileList) {
            mobileList.innerHTML = realList.innerHTML;
        }
    }

    const originalLoadChatList = window.loadChatList;
    if (originalLoadChatList) {
        window.loadChatList = async function() {
            await originalLoadChatList();
            syncMobileChatList();
        };
    }

    // ========== Add back button to chat header ==========
    function addChatBackButton() {
        const chatHeaderLeft = document.querySelector('.chat-header-left');
        if (chatHeaderLeft && !document.getElementById('mobileBackBtn')) {
            const backBtn = document.createElement('button');
            backBtn.id = 'mobileBackBtn';
            backBtn.innerHTML = '←';
            backBtn.onclick = function() {
                window.showChatsView();
            };
            chatHeaderLeft.prepend(backBtn);
        }
    }

    // ========== Add Profile button to Settings panel ==========
    function addProfileToSettings() {
        const settingsContent = document.querySelector('.settings-content');
        if (settingsContent && !document.getElementById('mobileProfileBtn')) {
            const section = document.createElement('div');
            section.className = 'settings-section';
            section.innerHTML = `
                <h3>Account</h3>
                <button id="mobileProfileBtn" class="profile-action-btn" style="width:100%;justify-content:center;">
                    <span>👤</span><span>View / Edit Profile</span>
                </button>
            `;
            settingsContent.appendChild(section);
            document.getElementById('mobileProfileBtn').addEventListener('click', function() {
                if (typeof window.openProfileModal === 'function') {
                    window.openProfileModal();
                }
                // Close settings panel
                if (typeof window.closeSettingsPanel === 'function') {
                    window.closeSettingsPanel();
                }
            });
        }
    }

    // ========== Observer for chat view ==========
    const observer = new MutationObserver(() => {
        if (document.getElementById('chatView')?.style.display === 'flex') {
            addChatBackButton();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // ========== Initial setup ==========
    document.addEventListener('DOMContentLoaded', () => {
        moveSearchToMain();
        adjustPanelBottom();
        addProfileToSettings();
        setTimeout(syncMobileChatList, 500);
        setActiveTab('chats');
    });

    // Also adjust on resize
    window.addEventListener('resize', adjustPanelBottom);

    // Prevent popout menu on mobile
    window.togglePopoutMenu = function() {};
    window.closePopout = function() {};
})();