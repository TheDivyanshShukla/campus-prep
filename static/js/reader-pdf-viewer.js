/**
 * PDF.js rendering core for the reader.
 * Reads config from <script id="reader-data"> JSON tag.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        if (window.__drm_tripped) return;

        var dataEl = document.getElementById('reader-data');
        if (!dataEl) return;
        var RD = JSON.parse(dataEl.textContent);

        var pageScrollTimer;

        function updateCurrentPage() {
            var canvases = document.querySelectorAll('#pdf-container canvas[id^="page-canvas-"]');
            if (!canvases.length) return;

            var closestNum = 1;
            var minDistance = Infinity;
            var viewportHalfHeight = window.innerHeight / 2;

            canvases.forEach(function (canvas) {
                var rect = canvas.getBoundingClientRect();
                var canvasCenter = rect.top + (rect.height / 2);
                var distance = Math.abs(viewportHalfHeight - canvasCenter);
                if (distance < minDistance) {
                    minDistance = distance;
                    closestNum = canvas.id.split('-')[2];
                }
            });

            var inp = document.getElementById('pageNavInput');
            if (inp && inp.value != closestNum) {
                var docId = inp.dataset.docid;
                inp.value = closestNum;
                if (docId) localStorage.setItem('pdf_page_' + docId, closestNum);
            }
        }

        var url = RD.api_secure_pdf_url;
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

        var loadingTask = pdfjsLib.getDocument({
            url: url,
            httpHeaders: { 'X-PDF-Token': RD.pdf_token },
            disableRange: true,
            disableStream: true
        });

        loadingTask.promise.then(function (pdf) {
            window.pdfDocGlobal = pdf;
            window.dispatchEvent(new Event('readerPdfReady'));
            document.getElementById('pageNavTotal').innerText = '/ ' + pdf.numPages;
            document.getElementById('pageNavInput').max = pdf.numPages;

            var container = document.getElementById('pdf-container');
            var spinner = document.getElementById('pdf-loading-spinner');
            var scale = window.devicePixelRatio > 1 ? 2.0 : 1.5;

            var docId = String(RD.document_id);
            var savedPageStr = localStorage.getItem('pdf_page_' + docId);
            var targetPage = savedPageStr ? parseInt(savedPageStr) : 1;
            if (targetPage > pdf.numPages) targetPage = pdf.numPages;
            if (targetPage < 1) targetPage = 1;

            var teleported = false;
            var teleportCancelled = false;

            var showTeleportBadge = function () {
                if (targetPage <= 1) return;
                var badge = document.getElementById('last-read-badge');
                var text = document.getElementById('last-read-text');
                var restoreBtn = document.getElementById('restore-teleport');
                var dismissBtn = document.getElementById('dismiss-teleport');

                if (badge && text && restoreBtn && dismissBtn) {
                    text.innerText = 'RESUME AT PAGE ' + targetPage + '?';
                    badge.classList.remove('opacity-0', 'translate-y-10');
                    badge.classList.add('opacity-100', 'translate-y-0');

                    restoreBtn.onclick = function () {
                        text.innerText = 'TELEPORTING...';
                        restoreBtn.parentElement.classList.add('hidden');
                        checkAndExecuteTeleport(true);
                    };

                    dismissBtn.onclick = function () {
                        badge.classList.remove('opacity-100', 'translate-y-0');
                        badge.classList.add('opacity-0', 'translate-y-10');
                        teleportCancelled = true;
                    };
                }
            };

            var checkAndExecuteTeleport = function (manualTrigger) {
                if (teleported || teleportCancelled) return;
                var targetCanvas = document.getElementById('page-canvas-' + targetPage);
                if (targetCanvas && manualTrigger) {
                    teleported = true;
                    var badge = document.getElementById('last-read-badge');
                    var text = document.getElementById('last-read-text');

                    targetCanvas.scrollIntoView({ behavior: 'smooth', block: 'start' });

                    setTimeout(function () {
                        if (text) text.innerText = 'VIEW RESTORED';
                        setTimeout(function () {
                            if (badge) {
                                badge.classList.remove('opacity-100', 'translate-y-0');
                                badge.classList.add('opacity-0', 'translate-y-10');
                            }
                        }, 2000);
                    }, 1000);
                }
            };

            var currPage = 1;
            function renderNextPage() {
                if (currPage > pdf.numPages) return;
                pdf.getPage(currPage).then(function (page) {
                    var viewport = page.getViewport({ scale: scale });
                    var canvas = document.createElement('canvas');
                    canvas.id = 'page-canvas-' + currPage;
                    canvas.className = 'w-full bg-white shadow-2xl rounded-sm object-contain pointer-events-none';
                    var context = canvas.getContext('2d');
                    canvas.height = viewport.height;
                    canvas.width = viewport.width;
                    context.fillStyle = 'white';
                    context.fillRect(0, 0, canvas.width, canvas.height);
                    container.appendChild(canvas);
                    if (window.currentZoom && window.currentZoom !== 100) canvas.style.width = window.currentZoom + '%';

                    var renderTask = page.render({ canvasContext: context, viewport: viewport, background: 'white' });
                    renderTask.promise.then(function () {
                        if (currPage === 1) {
                            spinner.style.opacity = '0';
                            setTimeout(function () {
                                spinner.remove();
                                showTeleportBadge();
                            }, 500);
                        }

                        if (currPage === targetPage) checkAndExecuteTeleport();

                        currPage++;
                        renderNextPage();
                    });
                });
            }

            renderNextPage();

            var topBtn = document.getElementById('backToTopBtn');
            var scrollHandler = function () {
                var scrollY = window.pageYOffset || document.documentElement.scrollTop;
                if (scrollY > 500) topBtn.classList.remove('translate-y-20', 'opacity-0');
                else topBtn.classList.add('translate-y-20', 'opacity-0');
                clearTimeout(pageScrollTimer);
                pageScrollTimer = setTimeout(updateCurrentPage, 50);
            };

            window.addEventListener('scroll', scrollHandler, { passive: true });
            document.addEventListener('scroll', scrollHandler, { passive: true });
            updateCurrentPage();

        }, function (reason) {
            console.error('PDF Failed to Load:', reason);
            document.getElementById('pdf-loading-spinner').innerHTML =
                '<p class="text-red-500 font-bold p-6 text-center">Document secure decoupling failed:<br><span class="text-sm opacity-75">' + reason + '</span></p>';
        });
    });
})();
