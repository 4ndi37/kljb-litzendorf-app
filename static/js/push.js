const VAPID_PUBLIC_KEY = document.querySelector('meta[name="vapid-public-key"]')?.content;

function urlB64ToUint8(b64) {
    const pad = '='.repeat((4 - b64.length % 4) % 4);
    const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return new Uint8Array([...raw].map(c => c.charCodeAt(0)));
}

async function subscribeUser(reg) {
    try {
        const sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlB64ToUint8(VAPID_PUBLIC_KEY)
        });
        await fetch('/push/subscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
            },
            body: JSON.stringify(sub.toJSON())
        });
    } catch (err) {
        console.warn('Push-Subscription fehlgeschlagen:', err);
    }
}

async function initPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !VAPID_PUBLIC_KEY) return;

    let reg;
    try {
        reg = await navigator.serviceWorker.ready;
    } catch {
        return;
    }

    if (Notification.permission === 'granted') {
        await subscribeUser(reg);
        return;
    }

    if (Notification.permission === 'denied' || localStorage.getItem('push_dismissed')) return;

    const banner = document.getElementById('push-banner');
    if (banner) banner.style.display = 'flex';

    document.getElementById('push-enable-btn')?.addEventListener('click', async () => {
        if (banner) banner.style.display = 'none';
        const perm = await Notification.requestPermission();
        if (perm === 'granted') await subscribeUser(reg);
    });

    document.getElementById('push-dismiss-btn')?.addEventListener('click', () => {
        localStorage.setItem('push_dismissed', '1');
        if (banner) banner.style.display = 'none';
    });
}

document.addEventListener('DOMContentLoaded', initPush);
