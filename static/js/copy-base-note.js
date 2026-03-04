(function () {
    'use strict';

    var dataEl = document.getElementById('notes-config');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);

    window.copyBaseNote = async function (baseNoteId) {
        if (!confirm('This will copy the template into your notes. Continue?')) return;
        try {
            var resp = await fetch(config.copyBaseNoteUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken
                },
                body: JSON.stringify({ base_note_id: baseNoteId }),
            });
            var data = await resp.json();
            if (data.success) location.reload();
            else alert(data.error || 'Failed to copy template');
        } catch (e) {
            alert('Network error');
        }
    };
})();
