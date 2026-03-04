/**
 * Web Push notification registration and subscription.
 * Reads CSRF token from <meta name="csrf-token"> tag in base.html.
 */
(function () {
    'use strict';

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    async function subscribeToPush() {
        const permission = await Notification.requestPermission();

        if (permission !== 'granted') {
            alert('We need permission to show alerts. Please check your browser settings! 🔔');
            return;
        }

        try {
            const registration = await navigator.serviceWorker.ready;
            let subscription = await registration.pushManager.getSubscription();

            // Clear stale subscription to ensure fresh registration
            if (subscription) {
                console.log('Existing subscription found, clearing it to ensure fresh registration...');
                await subscription.unsubscribe();
            }

            const response = await fetch('/webpush/vapid/');
            const config = await response.json();

            const convertedVapidKey = urlBase64ToUint8Array(config.publicKey);

            const newSubscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: convertedVapidKey
            });

            const responseSave = await fetch('/webpush/save_information', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    subscription: newSubscription.toJSON(),
                    browser: navigator.userAgent.includes('Chrome') ? 'Chrome' : 'Browser',
                    user_agent: navigator.userAgent,
                    group: 'default',
                    status_type: 'subscribe'
                })
            });

            if (!responseSave.ok) {
                const errorText = await responseSave.text();
                throw new Error('Server responded with ' + responseSave.status + ': ' + errorText);
            }

            alert('Notifications enabled! 🔔');
            location.reload();
        } catch (error) {
            console.error('Subscription failed:', error);
            alert('Failed to enable alerts: ' + error.message + ' 🛠️');
        }
    }

    // Expose subscribeToPush globally for button onclick handlers
    window.subscribeToPush = subscribeToPush;

    // Service worker registration + auto-prompt
    if ('serviceWorker' in navigator && 'PushManager' in window) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js')
                .then(reg => {
                    console.log('SW Registered', reg);

                    // Auto-prompt if permission not yet asked
                    if (Notification.permission === 'default') {
                        console.log('User logged in and permission not yet asked. Prompting in 2 seconds...');
                        setTimeout(() => {
                            subscribeToPush();
                        }, 2000);
                    }
                })
                .catch(err => console.error('SW Registration failed', err));
        });
    }
})();
