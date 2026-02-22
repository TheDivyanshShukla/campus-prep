// Registered Service Worker for Web Push
self.addEventListener('push', function (event) {
    let data = { title: 'New Notification', body: 'You have a new alert on RGPV Live.' };

    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: '/static/img/logo.png', // Fallback icon
        badge: '/static/img/badge.png', // Fallback badge
        requireInteraction: true, // Keep notification visible until user clicks
        vibrate: [100, 50, 100],
        data: {
            url: data.link || '/notifications/'
        }
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});
