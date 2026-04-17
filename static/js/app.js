// static/js/app.js
// Kiselgram Application Router
// Loads free.js or prem.js based on user status

(function() {
    'use strict';

    const CONFIG = window.KISELGRAM_CONFIG || {};
    const isPremium = CONFIG.isPremium || false;

    const scriptFile = isPremium ? 'prem.js' : 'free.js';

    console.log(`📦 Loading Kiselgram ${isPremium ? 'Premium' : 'Free'}...`);

    const script = document.createElement('script');
    script.src = `/static/js/${scriptFile}?v=${CONFIG.version || '4.0.0'}`;
    script.onload = () => console.log(`✅ ${scriptFile} loaded`);
    script.onerror = () => {
        console.error(`❌ Failed to load ${scriptFile}`);
        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif"><div style="text-align:center"><h1>⚠️ Failed to load</h1><button onclick="location.reload()">Retry</button></div></div>';
    };

    document.body.appendChild(script);
})();