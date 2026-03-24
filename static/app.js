document.addEventListener('DOMContentLoaded', () => {
    const fetchBtn = document.getElementById('fetch-btn');
    const urlInput = document.getElementById('url-input');
    const loader = document.getElementById('loader');
    const workspace = document.getElementById('workspace');

    const videoTitle = document.getElementById('video-title');
    const videoDuration = document.getElementById('video-duration');
    const videoThumbnail = document.getElementById('video-thumbnail');

    const clipSelectorList = document.getElementById('clip-selector-list');
    const segmentCount = document.getElementById('segment-count');

    const fontSelect = document.getElementById('font-select');
    const fontPreview = document.getElementById('font-preview');
    const fontSizeInput = document.getElementById('font-size-input');
    const fontColorInput = document.getElementById('font-color-input');

    const startBtn = document.getElementById('start-btn');
    const terminalSection = document.getElementById('terminal-section');
    const terminalOutput = document.getElementById('terminal-output');

    const previewModal = document.getElementById('preview-modal');
    const closeModalBtn = document.getElementById('close-modal');
    const modalIframe = document.getElementById('modal-iframe');

    let currentVideoUrl = "";

    closeModalBtn.addEventListener('click', () => {
        previewModal.classList.add('hidden');
        modalIframe.src = '';
    });

    fontSelect.addEventListener('change', (e) => {
        fontPreview.style.fontFamily = e.target.value;
    });
    fontSizeInput.addEventListener('input', (e) => {
        fontPreview.style.fontSize = `${e.target.value}px`;
    });
    fontColorInput.addEventListener('input', (e) => {
        fontPreview.style.color = e.target.value;
    });

    function formatTime(secs) {
        const m = Math.floor(secs / 60);
        const s = Math.floor(secs % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }

    fetchBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) return alert("Harap masukkan URL YouTube yang valid.");

        currentVideoUrl = url;
        loader.classList.remove('hidden');
        workspace.classList.add('hidden');
        terminalSection.classList.add('hidden');
        const dashGrid = document.getElementById('dashboard-grid');
        if (dashGrid) dashGrid.classList.remove('has-terminal');

        try {
            const res = await fetch(`/api/analyze?url=${encodeURIComponent(url)}`);
            const data = await res.json();

            if (data.error) throw new Error(data.error);

            videoTitle.textContent = data.title;
            videoDuration.textContent = `Durasi: ${formatTime(data.duration)}`;
            videoThumbnail.src = data.thumbnail;

            clipSelectorList.innerHTML = '';
            let validClips = 0;

            if (data.heatmap && data.heatmap.length > 0) {
                data.heatmap.forEach((point, index) => {
                    if (point.score >= 0.3) {
                        validClips++;
                        const clipItem = document.createElement('div');
                        clipItem.className = 'clip-item selected';

                        const clipHeader = document.createElement('label');
                        clipHeader.className = 'clip-header';

                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.checked = true;
                        checkbox.value = `${Math.floor(point.start)}-${Math.floor(point.start + 60)}`;
                        checkbox.className = 'segment-checkbox';

                        checkbox.addEventListener('change', (e) => {
                            if (checkbox.checked) {
                                clipItem.classList.add('selected');
                            } else {
                                clipItem.classList.remove('selected');
                            }
                        });

                        const detailsBox = document.createElement('div');
                        detailsBox.className = 'clip-details';

                        const timeSpan = document.createElement('span');
                        timeSpan.className = 'clip-time';
                        timeSpan.textContent = `Klip #${validClips} [${formatTime(point.start)} — ${formatTime(point.start + 60)}]`;

                        const scoreSpan = document.createElement('span');
                        scoreSpan.className = 'clip-score';
                        scoreSpan.textContent = `Skor Viral: ${(point.score * 10).toFixed(1)}/10`;

                        const previewBtn = document.createElement('button');
                        previewBtn.className = 'preview-btn';
                        previewBtn.textContent = 'Preview';

                        previewBtn.onclick = (e) => {
                            e.preventDefault();
                            const startSec = Math.floor(point.start);
                            const endSec = Math.floor(point.start + 60);
                            modalIframe.src = `https://www.youtube.com/embed/${data.video_id}?start=${startSec}&end=${endSec}&autoplay=1`;
                            previewModal.classList.remove('hidden');
                        };

                        detailsBox.appendChild(timeSpan);
                        detailsBox.appendChild(scoreSpan);
                        detailsBox.appendChild(previewBtn);

                        clipHeader.appendChild(checkbox);
                        clipHeader.appendChild(detailsBox);

                        clipItem.appendChild(clipHeader);
                        clipSelectorList.appendChild(clipItem);
                    }
                });
            }

            if (validClips === 0) {
                clipSelectorList.innerHTML = '<div style="padding:1rem; text-align:center; color:#8c8c99;">Tidak ada heatmap virality tinggi yang ditemukan. Silakan isi Manual Timestamps di bawah.</div>';
            }
            segmentCount.textContent = `${validClips} KLIP POTENSIAL`;

            loader.classList.add('hidden');
            workspace.classList.remove('hidden');

        } catch (err) {
            alert("Terjadi Kesalahan: " + err.message);
            loader.classList.add('hidden');
        }
    });

    // Start Process
    startBtn.addEventListener('click', async () => {
        if (!currentVideoUrl) return;

        const crop = document.getElementById('crop-select').value;
        const subtitle = document.getElementById('subtitle-select').value;
        const model = document.getElementById('model-select').value;
        const font = document.getElementById('font-select').value;
        const manualInput = document.getElementById('manual-input').value.trim();
        const maxClips = document.getElementById('max-clips-input').value;
        const padding = document.getElementById('padding-input').value;
        const fontSize = document.getElementById('font-size-input').value;
        const fontColor = document.getElementById('font-color-input').value;

        let segmentString = manualInput;

        if (!segmentString) {
            const checkboxes = document.querySelectorAll('.segment-checkbox:checked');
            const selectedRanges = Array.from(checkboxes).map(cb => cb.value);

            if (selectedRanges.length === 0) {
                return alert("Silakan pilih minimal 1 klip atau masukkan Manual Timestamp.");
            }
            segmentString = selectedRanges.join(',');
        }

        const payload = {
            url: currentVideoUrl,
            crop: parseInt(crop),
            subtitle: parseInt(subtitle),
            model: model,
            font: font,
            manual_segments: segmentString,
            max_clips: parseInt(maxClips) || 100,
            padding: parseInt(padding) || 10,
            font_size: parseInt(fontSize) || 13,
            font_color: fontColor
        };

        try {
            startBtn.disabled = true;
            startBtn.textContent = 'MENGINISIASI PROSES [処理中]...';

            const res = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            terminalSection.classList.remove('hidden');
            const dashGrid = document.getElementById('dashboard-grid');
            if (dashGrid) dashGrid.classList.add('has-terminal');
            
            const progressContainer = document.getElementById('progress-container');
            const progressLabel = document.getElementById('progress-label');
            const progressFill = document.getElementById('progress-fill');
            
            progressContainer.classList.remove('hidden');
            progressFill.style.width = '0%';
            progressLabel.textContent = 'Memulai Proses Ekstraksi...';

            terminalOutput.innerHTML = '>> Menghubungkan ke server logging latar belakang...\n';

            const eventSource = new EventSource(`/api/stream/${data.job_id}`);

            eventSource.onmessage = function (e) {
                if (e.data.includes('[PROCESS_DONE]')) {
                    terminalOutput.innerHTML += '\n\n<span style="color:#00ff88;">[OK] EKSTRAKSI SELESAI. Klip disimpan di folder /clips.</span>';
                    progressFill.style.width = '100%';
                    progressLabel.textContent = 'Selesai! Klip tersimpan.';
                    eventSource.close();
                    startBtn.disabled = false;
                    startBtn.textContent = 'MULAI EKSTRAK KLIP [実行]';
                    return;
                }
                if (e.data.includes('[PROCESS_ERROR]')) {
                    terminalOutput.innerHTML += '\n\n<span style="color:#ff3366;">[ERROR] PROSES GAGAL. Silakan periksa log di atas.</span>';
                    progressFill.style.backgroundColor = 'var(--danger)';
                    progressLabel.textContent = 'Proses Gagal!';
                    eventSource.close();
                    startBtn.disabled = false;
                    startBtn.textContent = 'MULAI EKSTRAK KLIP [実行]';
                    return;
                }

                // Parser Progress Bar
                const textData = e.data.replace(/<[^>]*>?/gm, '').trim();
                
                if (textData.includes('[download]') && textData.includes('%')) {
                    const match = textData.match(/(\d+\.?\d*)%/);
                    if (match) {
                        const dlPercent = parseFloat(match[1]);
                        /* Download = 0-80% of bar, post-processing = 80-100% */
                        const barWidth = Math.min(80, dlPercent * 0.8);
                        progressFill.style.width = barWidth + '%';
                        progressLabel.textContent = `Mengunduh Video (${match[1]}%)`;
                    }
                } else if (textData.includes('Clip')) {
                    progressFill.style.width = '35%';
                    progressLabel.textContent = textData;
                } else if (textData.includes('Extracting')) {
                    progressFill.style.width = '45%';
                    progressLabel.textContent = 'Mengekstrak Segmen...';
                } else if (textData.includes('Remux')) {
                    progressFill.style.width = '55%';
                    progressLabel.textContent = 'Optimasi Video (Remux)...';
                } else if (textData.includes('Crop to vertical')) {
                    progressFill.style.width = '65%';
                    progressLabel.textContent = 'Memotong Video (9:16)...';
                } else if (textData.includes('Whisper')) {
                    progressFill.style.width = '75%';
                    progressLabel.textContent = 'Memuat AI Audio...';
                } else if (textData.includes('Transcribing')) {
                    progressFill.style.width = '85%';
                    progressLabel.textContent = 'Mentranskripsi Subtitle...';
                } else if (textData.includes('Burning')) {
                    progressFill.style.width = '95%';
                    progressLabel.textContent = 'Membakar Subtitle (Hardsub)...';
                } else if (textData.includes('frame=')) {
                    progressLabel.textContent = 'Memproses Video... (Cek Terminal)';
                    const timeMatch = textData.match(/time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})/);
                    if (timeMatch) {
                        const h = parseInt(timeMatch[1]);
                        const m = parseInt(timeMatch[2]);
                        const s = parseInt(timeMatch[3]);
                        const totalSecs = h * 3600 + m * 60 + s;
                        /* Assuming active phase starts at 50% and max clip length is ~60s */
                        const currentP = parseFloat(progressFill.style.width) || 50;
                        const newP = Math.min(95, 50 + (totalSecs / 60) * 45);
                        if (newP > currentP) {
                            progressFill.style.width = newP + '%';
                        }
                    }
                }

                terminalOutput.innerHTML += e.data + '\n';
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            };

            eventSource.onerror = function () {
                terminalOutput.innerHTML += '\n<span style="color:#ffcc00;">[WARN] Terputus dari aliran log server.</span>';
                eventSource.close();
                startBtn.disabled = false;
                startBtn.textContent = 'MULAI EKSTRAK KLIP [実行]';
            };

        } catch (err) {
            alert("Terjadi Kesalahan: " + err.message);
            startBtn.disabled = false;
            startBtn.textContent = 'MULAI EKSTRAK KLIP [実行]';
        }
    });
});
