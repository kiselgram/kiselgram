// static/js/mobile-prem.js
// Mobile-specific behavior for Kiselgram Premium

(function() {
    'use strict';

    if (window.innerWidth > 768) return;

    console.log('✨ Kiselgram Premium Mobile active');

    function adjustPanelBottom() {
        const navHeight = 60;
        ['contactsView', 'createGroupView', 'createChannelView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.bottom = navHeight + 'px';
        });
        const settingsPanel = document.getElementById('settingsPanel');
        if (settingsPanel) settingsPanel.style.bottom = navHeight + 'px';
        const privacyPanel = document.getElementById('privacyPanel');
        if (privacyPanel) privacyPanel.style.bottom = navHeight + 'px';
        const overlay = document.getElementById('panelOverlay');
        if (overlay) overlay.style.bottom = navHeight + 'px';
    }

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

    const navItems = document.querySelectorAll('.bottom-nav-item');

    window.setActiveTab = function(viewId) {
        navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewId);
        });

        ['contactsView', 'createGroupView', 'createChannelView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });

        const emptyChat = document.getElementById('emptyChat');
        const chatView = document.getElementById('chatView');
        const contactsView = document.getElementById('contactsView');
        const searchContainer = document.querySelector('.global-search-container');
        const storiesRow = document.getElementById('storiesRow');

        // Always close chat view when switching tabs
        if (chatView) chatView.style.display = 'none';

        if (viewId === 'contacts') {
            if (contactsView) contactsView.style.display = 'flex';
            if (emptyChat) emptyChat.style.display = 'none';
            if (searchContainer) searchContainer.style.display = 'none';
            if (storiesRow) storiesRow.style.display = 'none';
        } else if (viewId === 'chats') {
            if (emptyChat) emptyChat.style.display = 'flex';
            if (contactsView) contactsView.style.display = 'none';
            if (searchContainer) searchContainer.style.display = 'block';
            if (storiesRow) storiesRow.style.display = 'flex';
            if (typeof window.loadChatList === 'function') window.loadChatList();
        } else if (viewId === 'settings') {
            if (typeof window.openSettingsPanel === 'function') window.openSettingsPanel();
        } else if (viewId === 'search') {
            if (emptyChat) emptyChat.style.display = 'flex';
            if (contactsView) contactsView.style.display = 'none';
            if (searchContainer) searchContainer.style.display = 'block';
            if (storiesRow) storiesRow.style.display = 'flex';
            const searchInput = document.getElementById('globalSearchInput');
            if (searchInput) {
                searchInput.focus();
                searchInput.dispatchEvent(new Event('focus'));
            }
        }
        adjustPanelBottom();
    };

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
    window.openChat = async function(type, id) {
        if (originalOpenChat) await originalOpenChat.call(this, type, id);
        const emptyChat = document.getElementById('emptyChat');
        const chatView = document.getElementById('chatView');
        const contactsView = document.getElementById('contactsView');
        const searchContainer = document.querySelector('.global-search-container');
        const storiesRow = document.getElementById('storiesRow');

        if (emptyChat) emptyChat.style.display = 'none';
        if (contactsView) contactsView.style.display = 'none';
        if (searchContainer) searchContainer.style.display = 'none';
        if (storiesRow) storiesRow.style.display = 'none';

        if (chatView) {
            chatView.style.display = 'flex';
            chatView.style.position = 'fixed';
            chatView.style.top = '0';
            chatView.style.left = '0';
            chatView.style.right = '0';
            chatView.style.bottom = '0';
            chatView.style.zIndex = '1000';
        }

        addChatBackButton();

        const msgContainer = document.getElementById('messagesContainer');
        if (msgContainer) {
            setTimeout(() => {
                if (msgContainer.querySelector('.loading-spinner')) {
                    if (typeof window.loadMessages === 'function') window.loadMessages(type, id);
                }
            }, 1000);
        }

        setActiveTab('chats');
    };

    const originalHideContacts = window.hideContactsView;
    window.hideContactsView = function() {
        if (originalHideContacts) originalHideContacts.call(this);
        setActiveTab('chats');
    };

    function syncMobileChatList() {
        const realList = document.getElementById('chatList');
        const mobileList = document.getElementById('mobileChatList');
        if (realList && mobileList) mobileList.innerHTML = realList.innerHTML;
    }

    const originalLoadChatList = window.loadChatList;
    if (originalLoadChatList) {
        window.loadChatList = async function() {
            await originalLoadChatList();
            syncMobileChatList();
        };
    }

    function addChatBackButton() {
        const chatHeaderLeft = document.querySelector('.chat-header-left');
        if (chatHeaderLeft && !document.getElementById('mobileBackBtn')) {
            const backBtn = document.createElement('button');
            backBtn.id = 'mobileBackBtn';
            backBtn.innerHTML = '←';
            backBtn.onclick = () => {
                const chatView = document.getElementById('chatView');
                if (chatView) chatView.style.display = 'none';
                setActiveTab('chats');
            };
            chatHeaderLeft.prepend(backBtn);
        }
    }

    function addProfileToSettings() {
        const settingsContent = document.querySelector('.settings-content');
        if (settingsContent && !document.getElementById('mobileProfileBtn')) {
            const section = document.createElement('div');
            section.className = 'settings-section';
            section.innerHTML = `<h3>Account</h3><button id="mobileProfileBtn" class="profile-action-btn" style="width:100%;justify-content:center;"><span>👤</span><span>View / Edit Profile</span></button>`;
            settingsContent.appendChild(section);
            document.getElementById('mobileProfileBtn').addEventListener('click', () => {
                if (typeof window.openProfileModal === 'function') window.openProfileModal();
                if (typeof window.closeSettingsPanel === 'function') window.closeSettingsPanel();
            });
        }
    }

    function addCreateButtonsToContactsHeader() {
        const contactsHeader = document.querySelector('#contactsView .panel-header');
        if (contactsHeader && !document.getElementById('mobileCreateGroupBtn')) {
            const btnContainer = document.createElement('div');
            btnContainer.style.display = 'flex';
            btnContainer.style.gap = '8px';
            const groupBtn = document.createElement('button');
            groupBtn.id = 'mobileCreateGroupBtn';
            groupBtn.className = 'header-action-btn';
            groupBtn.innerHTML = '👥+';
            groupBtn.title = 'Create Group';
            groupBtn.onclick = () => { if (typeof window.showCreateGroupView === 'function') window.showCreateGroupView(); };
            const channelBtn = document.createElement('button');
            channelBtn.id = 'mobileCreateChannelBtn';
            channelBtn.className = 'header-action-btn';
            channelBtn.innerHTML = '📢+';
            channelBtn.title = 'Create Channel';
            channelBtn.onclick = () => { if (typeof window.showCreateChannelView === 'function') window.showCreateChannelView(); };
            btnContainer.appendChild(groupBtn);
            btnContainer.appendChild(channelBtn);
            const existingAddBtn = contactsHeader.querySelector('.header-action-btn');
            if (existingAddBtn) existingAddBtn.insertAdjacentElement('afterend', btnContainer);
            else contactsHeader.appendChild(btnContainer);
        }
    }

    const observer = new MutationObserver(() => {
        const chatView = document.getElementById('chatView');
        if (chatView && chatView.style.display === 'flex') {
            addChatBackButton();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    document.addEventListener('DOMContentLoaded', () => {
        ['contactsView', 'createGroupView', 'createChannelView', 'chatView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        const emptyChat = document.getElementById('emptyChat');
        if (emptyChat) emptyChat.style.display = 'flex';

        moveSearchToMain();
        adjustPanelBottom();
        addProfileToSettings();
        addCreateButtonsToContactsHeader();

        setTimeout(() => {
            const chatView = document.getElementById('chatView');
            if (chatView && chatView.style.display === 'flex') {
                chatView.style.display = 'none';
                const emptyChat = document.getElementById('emptyChat');
                if (emptyChat) emptyChat.style.display = 'flex';
                setActiveTab('chats');
            }
        }, 200);

        setTimeout(syncMobileChatList, 500);
        setActiveTab('chats');
    });

    window.addEventListener('resize', adjustPanelBottom);
    window.togglePopoutMenu = () => {};
    window.closePopout = () => {};

    // Premium story viewer integration
    const originalOpenStoryViewer = window.openStoryViewer;
    if (originalOpenStoryViewer) {
        window.openStoryViewer = function(uid) {
            originalOpenStoryViewer.call(this, uid);
            document.body.classList.add('story-viewer-open');
            const bottomNav = document.querySelector('.mobile-bottom-nav');
            if (bottomNav) bottomNav.style.display = 'none';
        };
    }

    const originalCloseStoryViewer = window.closeStoryViewer;
    if (originalCloseStoryViewer) {
        window.closeStoryViewer = function() {
            originalCloseStoryViewer.call(this);
            document.body.classList.remove('story-viewer-open');
            const bottomNav = document.querySelector('.mobile-bottom-nav');
            if (bottomNav) bottomNav.style.display = 'flex';
        };
    }

    const originalNextStory = window.nextStory;
    if (originalNextStory) {
        window.nextStory = function() {
            originalNextStory.call(this);
            if (!document.getElementById('storyViewer')) document.body.classList.remove('story-viewer-open');
        };
    }

    const originalPreviousStory = window.previousStory;
    if (originalPreviousStory) {
        window.previousStory = function() {
            originalPreviousStory.call(this);
            if (!document.getElementById('storyViewer')) document.body.classList.remove('story-viewer-open');
        };
    }
})();