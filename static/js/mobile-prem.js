// static/js/mobile-prem.js
(function() {
    'use strict';
    if (window.innerWidth > 768) return;

    console.log('✨ Premium Mobile active');

    function adjustPanels() {
        const navHeight = 60;
        ['contactsView', 'createGroupView', 'createChannelView', 'chatView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.bottom = navHeight + 'px';
        });
    }

    function moveSearch() {
        const search = document.querySelector('.global-search-container');
        const chatArea = document.getElementById('chatArea');
        if (search && chatArea) {
            chatArea.insertBefore(search, chatArea.firstChild);
            const stories = document.getElementById('storiesRow');
            if (stories) search.insertAdjacentElement('afterend', stories);
        }
    }

    const navItems = document.querySelectorAll('.bottom-nav-item');
    window.setActiveTab = function(viewId) {
        navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewId);
        });

        ['contactsView', 'createGroupView', 'createChannelView', 'chatView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });

        const emptyChat = document.getElementById('emptyChat');
        const contactsView = document.getElementById('contactsView');
        const searchContainer = document.querySelector('.global-search-container');
        const storiesRow = document.getElementById('storiesRow');

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
            document.getElementById('globalSearchInput')?.focus();
        }
        adjustPanels();
    };

    const origShowContacts = window.showContactsView;
    window.showContactsView = function() {
        if (origShowContacts) origShowContacts.call(this);
        setActiveTab('contacts');
    };

    const origShowChats = window.showChatsView;
    window.showChatsView = function() {
        if (origShowChats) origShowChats.call(this);
        setActiveTab('chats');
    };

    const origOpenSettings = window.openSettingsPanel;
    window.openSettingsPanel = function() {
        if (origOpenSettings) origOpenSettings.call(this);
        setActiveTab('settings');
    };

    const origOpenChat = window.openChat;
    window.openChat = async function(type, id) {
        if (origOpenChat) await origOpenChat.call(this, type, id);
        document.getElementById('emptyChat').style.display = 'none';
        document.getElementById('contactsView').style.display = 'none';
        document.querySelector('.global-search-container').style.display = 'none';
        document.getElementById('storiesRow').style.display = 'none';
        const chatView = document.getElementById('chatView');
        chatView.style.display = 'flex';
        addBackButton();
        adjustPanels();
        setActiveTab('chats');
    };

    const origHideContacts = window.hideContactsView;
    window.hideContactsView = function() {
        if (origHideContacts) origHideContacts.call(this);
        setActiveTab('chats');
    };

    function syncChatList() {
        const real = document.getElementById('chatList');
        const mobile = document.getElementById('mobileChatList');
        if (real && mobile) mobile.innerHTML = real.innerHTML;
    }

    const origLoadChatList = window.loadChatList;
    if (origLoadChatList) {
        window.loadChatList = async function() {
            await origLoadChatList();
            syncChatList();
        };
    }

    function addBackButton() {
        const left = document.querySelector('.chat-header-left');
        if (left && !document.getElementById('mobileBackBtn')) {
            const btn = document.createElement('button');
            btn.id = 'mobileBackBtn';
            btn.innerHTML = '←';
            btn.onclick = () => {
                document.getElementById('chatView').style.display = 'none';
                setActiveTab('chats');
            };
            left.prepend(btn);
        }
    }

    function addProfileButton() {
        const content = document.querySelector('.settings-content');
        if (content && !document.getElementById('mobileProfileBtn')) {
            const section = document.createElement('div');
            section.className = 'settings-section';
            section.innerHTML = '<h3>Account</h3><button id="mobileProfileBtn" class="profile-action-btn" style="width:100%;justify-content:center;"><span>👤</span><span>View / Edit Profile</span></button>';
            content.appendChild(section);
            document.getElementById('mobileProfileBtn').onclick = () => {
                if (typeof window.openProfileModal === 'function') window.openProfileModal();
                if (typeof window.closeSettingsPanel === 'function') window.closeSettingsPanel();
            };
        }
    }

    function addCreateButtons() {
        const header = document.querySelector('#contactsView .panel-header');
        if (header && !document.getElementById('mobileCreateGroupBtn')) {
            const div = document.createElement('div');
            div.style.display = 'flex';
            div.style.gap = '8px';
            div.innerHTML = `
                <button id="mobileCreateGroupBtn" class="header-action-btn" title="Create Group">👥+</button>
                <button id="mobileCreateChannelBtn" class="header-action-btn" title="Create Channel">📢+</button>
            `;
            const existing = header.querySelector('.header-action-btn');
            if (existing) existing.insertAdjacentElement('afterend', div);
            else header.appendChild(div);
            document.getElementById('mobileCreateGroupBtn').onclick = () => window.showCreateGroupView?.();
            document.getElementById('mobileCreateChannelBtn').onclick = () => window.showCreateChannelView?.();
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        ['contactsView', 'createGroupView', 'createChannelView', 'chatView'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        document.getElementById('emptyChat').style.display = 'flex';

        moveSearch();
        adjustPanels();
        addProfileButton();
        addCreateButtons();
        setActiveTab('chats');

        setTimeout(() => {
            const chatView = document.getElementById('chatView');
            if (chatView && chatView.style.display === 'flex') {
                chatView.style.display = 'none';
                document.getElementById('emptyChat').style.display = 'flex';
            }
        }, 100);

        setTimeout(syncChatList, 300);
    });

    new MutationObserver(() => {
        if (document.getElementById('chatView')?.style.display === 'flex') addBackButton();
    }).observe(document.body, { childList: true, subtree: true });

    window.addEventListener('resize', adjustPanels);
    window.togglePopoutMenu = window.closePopout = () => {};

    // Story viewer integration
    const origOpenStory = window.openStoryViewer;
    if (origOpenStory) {
        window.openStoryViewer = function(uid) {
            origOpenStory.call(this, uid);
            document.body.classList.add('story-viewer-open');
            document.querySelector('.mobile-bottom-nav').style.display = 'none';
        };
    }
    const origCloseStory = window.closeStoryViewer;
    if (origCloseStory) {
        window.closeStoryViewer = function() {
            origCloseStory.call(this);
            document.body.classList.remove('story-viewer-open');
            document.querySelector('.mobile-bottom-nav').style.display = 'flex';
        };
    }
})();