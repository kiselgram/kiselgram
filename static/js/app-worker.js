// static/app-worker.js
// Kiselgram Service Worker - Device Detection & Redirect

const CACHE_NAME = 'kiselgram-v1';
const MOBILE_BREAKPOINT = 768;

const CACHE_URLS = [
    '/static/css/desktop.css',
    '/static/css/mobile.css',
    '/static/css/chats.css',
    '/static/css/animations.css',
    '/static/js/free.js',
    '/static/js/prem.js'
];

// Detect device type
function isMobile() {
    const sessionMobile = sessionStorage.getItem('kiselgram_is_mobile');
    if (sessionMobile !== null) {
        return sessionMobile === 'true';
    }

    const isMobileScreen = window.innerWidth <= MOBILE_BREAKPOINT;
    const ua = navigator.userAgent;
    const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);

    return isMobileScreen || isMobileUA;
}

// Redirect to appropriate version
function redirectToVersion() {
    const currentPath = window.location.pathname;
    const isPremium = document.cookie.includes('is_premium=true') ||
                      sessionStorage.getItem('kiselgram_is_premium') === 'true';

    if (currentPath.includes('/static/') ||
        currentPath.includes('/api/') ||
        currentPath.includes('/auth/') ||
        currentPath.includes('/files/') ||
        currentPath.includes('/login') ||
        currentPath.includes('/register')) {
        return;
    }

    const mobile = isMobile();
    const version = isPremium ? 'prem' : 'free';
    const device = mobile ? 'mob' : 'desk';

    sessionStorage.setItem('kiselgram_is_mobile', mobile);

    const targetPath = `/${version}-${device}`;

    if (!currentPath.includes(`/${version}-${device}`) && currentPath !== '/') {
        window.location.href = targetPath;
    }
}

// Install event - cache assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(CACHE_URLS);
        })
    );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        })
    );
});

// Fetch event - serve from cache
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request).catch(() => {
                if (event.request.mode === 'navigate') {
                    return caches.match('/');
                }
            });
        })
    );
});

// Message event - handle commands
self.addEventListener('message', (event) => {
    if (event.data.type === 'SET_MOBILE') {
        sessionStorage.setItem('kiselgram_is_mobile', event.data.value);
    }
    if (event.data.type === 'SET_PREMIUM') {
        sessionStorage.setItem('kiselgram_is_premium', event.data.value);
    }
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Client-side redirect
if (typeof window !== 'undefined') {
    redirectToWindow();
}

function redirectToWindow() {
    if (window.location.pathname === '/' || window.location.pathname === '/chat_list') {
        const mobile = isMobile();
        const isPremium = document.cookie.includes('is_premium=true');
        const version = isPremium ? 'prem' : 'free';
        const device = mobile ? 'mob' : 'desk';

        window.location.replace(`/${version}-${device}`);
    }
}