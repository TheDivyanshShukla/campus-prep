/**
 * Gamification study telemetry engine.
 * Tracks active reading time and pings server heartbeat.
 * Reads documentId and subjectId from <script id="reader-data">.
 */
(function () {
    'use strict';

    var dataEl = document.getElementById('reader-data');
    if (!dataEl) return;
    var RD = JSON.parse(dataEl.textContent);

    var activeSeconds = 0;
    var idleSeconds = 0;
    var isTracking = true;
    var IDLE_TIMEOUT_SECONDS = 180;
    var PING_INTERVAL_MS = 60000;

    var documentId = parseInt(RD.document_id);
    var subjectId = parseInt(RD.subject_id);

    function resetIdle() {
        idleSeconds = 0;
        if (!isTracking) {
            isTracking = true;
            console.log('[Telemetry] Idle broken. Resuming XP tracking.');
        }
    }

    window.addEventListener('mousemove', resetIdle);
    window.addEventListener('keypress', resetIdle);
    window.addEventListener('scroll', resetIdle);
    window.addEventListener('touchstart', resetIdle);
    window.addEventListener('click', resetIdle);

    setInterval(function () {
        if (isTracking) {
            idleSeconds++;
            activeSeconds++;
            if (idleSeconds >= IDLE_TIMEOUT_SECONDS) {
                isTracking = false;
                console.log('[Telemetry] User AFK. Tracking paused to prevent XP farming.');
            }
        }
    }, 1000);

    setInterval(function () {
        if (activeSeconds > 0 && isTracking) {
            var payload = {
                document_id: documentId,
                subject_id: subjectId,
                active_seconds: activeSeconds
            };
            fetch('/api/gamification/heartbeat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(payload)
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        activeSeconds = 0;
                    }
                })
                .catch(function (err) { console.error('[Telemetry] Failed to sync study time:', err); });
        }
    }, PING_INTERVAL_MS);

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
})();
