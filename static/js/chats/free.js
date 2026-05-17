// static/js/chats/free.js
// Free tier – no global redeclarations, only premium locks & overrides

(function() {
    // ============ PREMIUM LOCK ============
    // These functions are defined in common.js as stubs or empty.
    // Here we override them to show an upgrade prompt.

    window.loadStories = function() {
        const row = document.getElementById('storiesRow');
        if (row) {
            row.innerHTML = `
                <div class="story-circle locked" onclick="showPremiumModal()">
                    <div class="add-story-btn"><i class="fas fa-lock"></i></div>
                    <span class="story-username">Premium</span>
                </div>`;
        }
    };

    window.openStoryViewer = function() { showPremiumModal(); };
    window.showCreateStoryModal = function() { showPremiumModal(); };
    window.openChatCustomization = function() { showPremiumModal(); };

    // Any other locked features
    window.openImageViewer = function(url) {
        // Still allowed in free tier – opens in new tab
        window.open(url, '_blank');
    };

    // ============ PREMIUM UPGRADE MODAL ============
    window.showPremiumModal = function(feature) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content" style="max-width:400px;">
                <div class="modal-header" style="background:linear-gradient(135deg,#f59e0b,#eab308);color:#000;">
                    <h3><i class="fas fa-crown"></i> Upgrade to Premium</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()"><i class="fas fa-times"></i></button>
                </div>
                <div class="modal-body" style="text-align:center;padding:24px;">
                    <i class="fas fa-crown" style="font-size:48px;color:#f59e0b;"></i>
                    <p style="margin-top:16px;">Unlock Stories, Wallpapers, and 9 extra fonts!</p>
                    <button class="modal-btn modal-btn-primary" onclick="window.location.href='/premium'"
                            style="background:linear-gradient(135deg,#f59e0b,#eab308);color:#000;">
                        Upgrade Now
                    </button>
                </div>
            </div>`;
        document.body.appendChild(modal);
    };

    // ============ INIT ============
    // Ensure the locked story row is rendered when the page loads.
    // loadStories() will be called by common.js after loadCurrentUser() if needed,
    // but we also trigger it here just in case.
    if (document.readyState === 'complete') {
        window.loadStories();
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            window.loadStories();
        });
    }
})();