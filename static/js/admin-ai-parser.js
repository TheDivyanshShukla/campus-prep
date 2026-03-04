(function () {
    'use strict';

    var fileInput = document.getElementById('dropzone-file');
    var fileNameDisplay = document.getElementById('file-name-display');
    var form = document.getElementById('ai-parser-form');
    var parseBtn = document.getElementById('parse-btn');
    var publishBtn = document.getElementById('publish-btn');
    var jsonEditor = document.getElementById('json-editor');
    var statusBadge = document.getElementById('status-badge');
    var progressContainer = document.getElementById('progress-container');
    var progressBar = document.getElementById('progress-bar');
    var progressPercent = document.getElementById('progress-percent');
    var progressLabel = document.getElementById('progress-label');

    var pollingInterval = null;
    var currentDocumentId = null;

    // Update file name display
    fileInput.addEventListener('change', function (e) {
        if (e.target.files.length > 0) {
            if (e.target.files.length === 1) {
                fileNameDisplay.textContent = e.target.files[0].name;
            } else {
                fileNameDisplay.textContent = e.target.files.length + ' files selected';
            }
        }
    });

    function getCSRFToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function updateProgress(percent, label) {
        progressBar.style.width = percent + '%';
        progressPercent.textContent = Math.round(percent) + '%';
        if (label) progressLabel.textContent = label;
    }

    function stopPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    function startPolling(docId) {
        if (pollingInterval) clearInterval(pollingInterval);

        pollingInterval = setInterval(async function () {
            try {
                var res = await fetch('/api/document/' + docId + '/parsing-status/');
                var data = await res.json();

                if (data.status === 'PROCESSING' || data.status === 'PENDING') {
                    statusBadge.textContent = data.status === 'PENDING' ? 'Queued...' : 'Parsing via Gemini...';

                    var progress = 0;
                    if (data.total_steps > 0) {
                        progress += (data.completed_steps / data.total_steps) * 70;
                    }
                    if (data.recreation_total > 0) {
                        progress += (data.recreation_completed / data.recreation_total) * 30;
                    }

                    updateProgress(progress, data.status === 'PENDING' ? 'Waiting for worker...' : 'Processing Content... (' + data.completed_steps + '/' + data.total_steps + ')');
                } else if (data.status === 'COMPLETED') {
                    stopPolling();
                    updateProgress(100, 'All tasks finished!');
                    statusBadge.className = 'px-2.5 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800 border border-green-200';
                    statusBadge.textContent = 'Extraction Complete';

                    jsonEditor.value = JSON.stringify(data.structured_data, null, 4);
                    publishBtn.disabled = false;
                    parseBtn.disabled = false;
                    parseBtn.innerHTML = 'Extract & Structure with AI';
                } else if (data.status === 'FAILED') {
                    stopPolling();
                    statusBadge.className = 'px-2.5 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800 border border-red-200';
                    statusBadge.textContent = 'Parsing Failed';
                    alert('AI Parsing failed. Please check the document format.');
                    parseBtn.disabled = false;
                    parseBtn.innerHTML = 'Extract & Structure with AI';
                }
            } catch (e) {
                console.error('Polling error:', e);
            }
        }, 2000);
    }

    // Handle extraction form submit
    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (fileInput.files.length === 0) {
            alert('Please select a file to parse.');
            return;
        }

        var formData = new FormData(form);

        // UI Loading State
        parseBtn.innerHTML = '<svg class="animate-spin -ml-1 mr-3 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Starting...';
        parseBtn.disabled = true;
        statusBadge.className = 'px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 border border-blue-200 animate-pulse';
        statusBadge.textContent = 'Uploading to Server...';

        progressContainer.classList.remove('hidden');
        updateProgress(0, 'Initializing...');

        try {
            var response = await fetch('/api/parse-document/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCSRFToken()
                }
            });

            var result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Server error');

            currentDocumentId = result.document_id;
            startPolling(currentDocumentId);
        } catch (error) {
            jsonEditor.value = 'Error: ' + error.message;
            statusBadge.className = 'px-2.5 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800 border border-red-200';
            statusBadge.textContent = 'Failed to start';
            parseBtn.disabled = false;
            parseBtn.innerHTML = 'Extract & Structure with AI';
        }
    });

    // Handle publishing
    publishBtn.addEventListener('click', async function () {
        publishBtn.innerHTML = 'Publishing...';
        publishBtn.disabled = true;

        try {
            var structuredData = JSON.parse(jsonEditor.value);

            var payload = {
                document_id: currentDocumentId,
                structured_data: structuredData
            };

            var response = await fetch('/api/publish-document/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify(payload)
            });

            var result = await response.json();

            if (!response.ok) throw new Error(result.error);

            statusBadge.className = 'px-2.5 py-1 text-xs font-semibold rounded-full bg-green-500 text-white border border-green-600';
            statusBadge.textContent = 'Published to Database!';
            alert('Successfully saved and published to the database!');
        } catch (error) {
            alert('Failed to publish. Ensure JSON is valid. Error: ' + error.message);
            publishBtn.disabled = false;
            publishBtn.innerHTML = 'Publish to Database';
        }
    });
})();
