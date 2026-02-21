const chatBox = document.getElementById('chat-box');
const input = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');
const welcomeScreen = document.getElementById('welcome-screen');
const historyList = document.getElementById('history-list');
const sidebarSearch = document.getElementById('sidebar-search');

let isGenerating = false;

// =============================================
//  FEATURE 1: STREAMING (SSE Typewriter Effect)
// =============================================

async function sendMessage() {
    if (isGenerating) return;

    const text = input.value.trim();
    if (!text) return;

    // Hide Welcome Screen
    if (welcomeScreen) welcomeScreen.style.display = 'none';

    // 1. Add User Message
    addMessage(text, 'user');

    // Clear Input
    input.value = '';
    input.style.height = 'auto';
    updateSendButtonState();

    // 2. Show Thinking/Loading
    const loadingId = "loader-" + Date.now();
    showLoading(loadingId);
    isGenerating = true;

    // Check for image generation to start polling
    if (text.toLowerCase().includes("çiz") || text.toLowerCase().includes("oluştur")) {
        startProgressPolling(loadingId);
    }

    // 3. API Call — Try streaming first, fallback to regular
    try {
        const formData = new FormData();
        formData.append('mesaj', text);
        formData.append('mod', 'sohbet');

        // Use streaming endpoint
        const response = await fetch('/chat_stream', { method: 'POST', body: formData });

        // Remove loading indicator
        stopProgressPolling();
        removeLoading(loadingId);

        if (!response.ok) throw new Error("Stream failed");

        // Create AI message bubble for streaming
        const { row, textDiv, rawText } = createStreamingMessage();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';

        // Add cursor
        const cursor = document.createElement('span');
        cursor.className = 'streaming-cursor';
        textDiv.appendChild(cursor);

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        if (data.done) {
                            // Remove cursor when done
                            cursor.remove();
                        } else {
                            fullText += data.text;
                            // Remove cursor temporarily, update text, re-add cursor
                            cursor.remove();
                            textDiv.innerHTML = formatMessage(fullText);
                            textDiv.appendChild(cursor);
                            scrollToBottom();
                        }
                    } catch (e) { /* skip bad JSON */ }
                }
            }
        }

        // Final render without cursor + add copy button
        cursor.remove();
        textDiv.innerHTML = formatMessage(fullText);
        addCopyButton(row, textDiv, fullText);

        // Add to sidebar history
        addToHistory(text);

    } catch (error) {
        // Fallback to regular /chat endpoint
        stopProgressPolling();
        removeLoading(loadingId);
        console.warn("Stream failed, fallback:", error);

        try {
            const formData2 = new FormData();
            formData2.append('mesaj', text);
            formData2.append('mod', 'sohbet');

            const res = await fetch('/chat', { method: 'POST', body: formData2 });
            const data = await res.json();

            if (!data || !data.cevap) throw new Error("Bos cevap");

            addMessage(data.cevap, 'ai');
            addToHistory(text);
        } catch (e2) {
            console.error("Chat error:", e2);
        }
    }

    isGenerating = false;
}

function createStreamingMessage() {
    const row = document.createElement('div');
    row.className = 'message-row ai';

    const content = document.createElement('div');
    content.className = 'message-content';

    const avatar = document.createElement('div');
    avatar.className = 'avatar ai';
    avatar.innerHTML = '<svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="18" width="18" xmlns="http://www.w3.org/2000/svg" style="color:#000"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path></svg>';

    const textDiv = document.createElement('div');
    textDiv.className = 'text-content';

    content.appendChild(avatar);
    content.appendChild(textDiv);
    row.appendChild(content);
    chatBox.appendChild(row);

    scrollToBottom();
    return { row, textDiv, rawText: '' };
}

// =============================================
//  FEATURE 2: COPY BUTTON
// =============================================

function addCopyButton(messageRow, textDiv, rawText) {
    const actions = document.createElement('div');
    actions.className = 'message-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Kopyala`;

    copyBtn.onclick = async () => {
        try {
            await navigator.clipboard.writeText(rawText);
            copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Kopyalandi!`;
            copyBtn.classList.add('copied');
            setTimeout(() => {
                copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Kopyala`;
                copyBtn.classList.remove('copied');
            }, 2000);
        } catch (e) {
            showToast("Kopyalama basarisiz");
        }
    };

    actions.appendChild(copyBtn);

    // Insert actions after the text content inside message-content
    const msgContent = messageRow.querySelector('.message-content');
    if (msgContent) {
        // Add actions below the text div
        const wrapper = msgContent.querySelector('.text-content');
        if (wrapper) wrapper.appendChild(actions);
    }
}

// =============================================
//  FEATURE 3: SIDEBAR SEARCH
// =============================================

function initSidebarSearch() {
    if (!sidebarSearch) return;

    sidebarSearch.addEventListener('input', () => {
        const query = sidebarSearch.value.trim().toLowerCase();
        const items = historyList.querySelectorAll('.history-item');
        let visibleCount = 0;

        // Remove old no-results message
        const oldNoResults = historyList.querySelector('.no-results');
        if (oldNoResults) oldNoResults.remove();

        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (!query || text.includes(query)) {
                item.style.display = '';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });

        // Show no results message
        if (query && visibleCount === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'no-results';
            noResults.textContent = 'Sonuc bulunamadi';
            historyList.appendChild(noResults);
        }
    });
}

// =============================================
//  FEATURE 4: KEYBOARD SHORTCUTS
// =============================================

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+K → Focus search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            if (sidebarSearch) {
                sidebarSearch.focus();
                // On mobile, open sidebar first
                const sidebar = document.getElementById('sidebar');
                if (sidebar && !sidebar.classList.contains('open')) {
                    sidebar.classList.add('open');
                }
            }
        }

        // Ctrl+N → New chat
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            newChat();
        }

        // Escape → Close modals / clear search
        if (e.key === 'Escape') {
            // Close settings modal
            const settingsModal = document.getElementById('settings-modal');
            if (settingsModal && settingsModal.style.display !== 'none') {
                settingsModal.style.display = 'none';
                return;
            }

            // Close gallery modal
            const galleryModal = document.getElementById('gallery-modal');
            if (galleryModal && galleryModal.style.display !== 'none') {
                galleryModal.style.display = 'none';
                return;
            }

            // Clear search
            if (sidebarSearch && sidebarSearch.value) {
                sidebarSearch.value = '';
                sidebarSearch.dispatchEvent(new Event('input'));
                sidebarSearch.blur();
            }
        }
    });
}

// =============================================
//  EXISTING FUNCTIONALITY (preserved)
// =============================================

// Auto Resize Textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    updateSendButtonState();
}

function updateSendButtonState() {
    if (input.value.trim().length > 0) {
        sendBtn.removeAttribute('disabled');
        sendBtn.style.opacity = '1';
        sendBtn.style.cursor = 'pointer';
    } else {
        sendBtn.setAttribute('disabled', 'true');
        sendBtn.style.opacity = '0.5';
        sendBtn.style.cursor = 'default';
    }
}

function quickFill(text) {
    input.value = text;
    sendMessage();
}

async function newChat() {
    try {
        await fetch('/new_chat', { method: 'POST' });
        chatBox.innerHTML = '';
        welcomeScreen.style.display = 'flex';
        input.value = '';
        updateSendButtonState();
        loadSidebarHistory();
    } catch (e) {
        console.error("New chat error", e);
    }
}

// Format message text with markdown-like rendering
function formatMessage(text) {
    let formatted = text.replace(/\n/g, '<br>');

    // Markdown Image Renderer with Download Button
    formatted = formatted.replace(
        /!\[(.*?)\]\((.*?)\)/g,
        '<div class="generated-image-container">' +
        '<a href="$2" target="_blank"><img src="$2" alt="$1" style="max-width:100%; border-radius:10px; margin-top:10px;"></a>' +
        '<button class="download-btn" onclick="downloadImage(\'$2\')">Indir</button>' +
        '</div><br>'
    );

    if (formatted.includes("```")) {
        formatted = formatted.replace(/```(.*?)```/gs, '<pre style="background:var(--input-bg); padding:10px; border-radius:5px; overflow-x:auto;"><code>$1</code></pre>');
    }

    return formatted;
}

function addMessage(text, role) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const content = document.createElement('div');
    content.className = 'message-content';

    const avatar = document.createElement('div');
    avatar.className = `avatar ${role}`;
    avatar.innerText = role === 'user' ? 'S' : '';
    if (role === 'ai') avatar.innerHTML = '<svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="18" width="18" xmlns="http://www.w3.org/2000/svg" style="color:#000"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path></svg>';

    const textDiv = document.createElement('div');
    textDiv.className = 'text-content';
    textDiv.innerHTML = formatMessage(text);

    content.appendChild(avatar);
    content.appendChild(textDiv);
    row.appendChild(content);
    chatBox.appendChild(row);

    // Add copy button for AI messages
    if (role === 'ai') {
        addCopyButton(row, textDiv, text);
    }

    scrollToBottom();
}

function scrollToBottom() {
    setTimeout(() => {
        const scrollContainer = document.querySelector('.chat-area');
        if (scrollContainer) scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: "smooth" });
    }, 50);
}

// Theme Management
function changeTheme() {
    const themeSelector = document.getElementById('theme-selector');
    const selectedTheme = themeSelector ? themeSelector.value : 'System';
    const body = document.body;

    if (selectedTheme === 'Açık') {
        body.classList.add('light-mode');
    } else if (selectedTheme === 'Koyu') {
        body.classList.remove('light-mode');
    } else {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            body.classList.add('light-mode');
        } else {
            body.classList.remove('light-mode');
        }
    }
}

// Load History
async function loadHistory() {
    try {
        const res = await fetch('/get_history');
        const history = await res.json();

        if (history && history.length > 0) {
            welcomeScreen.style.display = 'none';
            history.forEach(msg => {
                addMessage(msg.text, msg.role);
            });
        }
    } catch (e) {
        console.error("History load failed", e);
    }
}

// Load Archived Chats for Sidebar
async function loadSidebarHistory() {
    try {
        const res = await fetch('/get_archives');
        const archives = await res.json();

        historyList.innerHTML = '<div class="history-active-label">Gecmis Sohbetler</div>';

        archives.forEach(chat => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.style.display = 'flex';
            item.style.justifyContent = 'space-between';
            item.style.alignItems = 'center';

            let display = chat.filename.replace("chat_", "").replace(".json", "");
            const parts = display.split("_");
            if (parts.length > 2) {
                display = parts.slice(2).join(" ");
            }

            const textSpan = document.createElement("span");
            textSpan.innerText = display || "Adsiz Sohbet";
            textSpan.style.overflow = "hidden";
            textSpan.style.textOverflow = "ellipsis";
            textSpan.style.whiteSpace = "nowrap";
            textSpan.onclick = () => loadOldChat(chat.filename);

            const delBtn = document.createElement("span");
            delBtn.innerText = "X";
            delBtn.style.cursor = "pointer";
            delBtn.style.fontSize = "12px";
            delBtn.style.opacity = "0.5";
            delBtn.style.padding = "0 5px";
            delBtn.style.color = "#ff4757";
            delBtn.onmouseover = () => delBtn.style.opacity = "1";
            delBtn.onmouseout = () => delBtn.style.opacity = "0.5";
            delBtn.onclick = (e) => deleteChat(chat.filename, e);

            item.appendChild(textSpan);
            item.appendChild(delBtn);
            historyList.appendChild(item);
        });

        // Re-apply search filter if active
        if (sidebarSearch && sidebarSearch.value.trim()) {
            sidebarSearch.dispatchEvent(new Event('input'));
        }
    } catch (e) {
        console.error("Sidebar load failed", e);
    }
}

async function loadOldChat(filename) {
    const formData = new FormData();
    formData.append('filename', filename);
    await fetch('/load_chat', { method: 'POST', body: formData });
    chatBox.innerHTML = '';
    loadHistory();
    loadSidebarHistory();
}

function addToHistory(text) {
    // Visual only — actual persistence is server-side
}

async function downloadImage(url) {
    showToast("Indirme Penceresi Aciliyor...");
    const formData = new FormData();
    formData.append('image_url', url);

    try {
        const res = await fetch('/save_generated_image', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.status === "ok") {
            showToast("Resim Kaydedildi: " + data.path);
        } else if (data.status === "cancelled") {
            showToast("Iptal Edildi");
        } else {
            showToast("Hata: " + data.message);
        }
    } catch (e) {
        showToast("Baglanti Hatasi");
    }
}

// Loading Indicator
function showLoading(id) {
    const loadDiv = document.createElement('div');
    loadDiv.className = 'message-row';
    loadDiv.id = id;
    loadDiv.innerHTML = `
        <div class="message-content">
            <div class="avatar ai">J</div>
            <div class="text-content">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatBox.appendChild(loadDiv);
    scrollToBottom();
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// Global polling interval
let progressInterval = null;

function startProgressPolling(elementId) {
    if (progressInterval) clearInterval(progressInterval);

    setTimeout(() => {
        const loaderDiv = document.getElementById(elementId);
        if (!loaderDiv) return;

        const textContent = loaderDiv.querySelector('.text-content');
        if (!textContent) return;

        if (!textContent.querySelector(".progress-container")) {
            const pCont = document.createElement('div');
            pCont.className = 'progress-container';
            pCont.style.marginTop = '10px';
            pCont.style.width = '100%';
            pCont.innerHTML = `
                <div style="font-size:12px; margin-bottom:5px; color:#aaa;" id="${elementId}-status">Hazirlaniyor...</div>
                <div style="width:100%; height:8px; background:#444; border-radius:4px; overflow:hidden;">
                    <div id="${elementId}-bar" class="progress-bar" style="width:0%; height:100%; background:cyan; transition:width 0.5s;"></div>
                </div>
            `;
            textContent.appendChild(pCont);
        }

        progressInterval = setInterval(async () => {
            try {
                const res = await fetch('/get_progress');
                const data = await res.json();

                if (data.status === "generating") {
                    const bar = document.getElementById(`${elementId}-bar`);
                    const stat = document.getElementById(`${elementId}-status`);
                    if (bar) bar.style.width = data.percent + "%";
                    if (stat) stat.innerText = data.message || `Olusturuluyor... %${data.percent}`;
                }
            } catch (e) { }
        }, 1000);
    }, 100);
}

function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

// Toast Notification
function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast-message";
    toast.innerText = message;
    toast.style.cssText = "position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 10px 20px; border-radius: 5px; z-index: 1000; animation: fadeIn 0.5s; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #555;";
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Enter to send
input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Gallery
function showGallery() {
    let modal = document.getElementById("gallery-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "gallery-modal";
        modal.className = "modal-overlay";
        modal.innerHTML = `
        <div class="modal-content" style="max-width:800px; width:90%; max-height:80vh;">
            <div class="modal-header"><h3>JARVIS Galeri</h3><button class="btn-close" onclick="closeGallery()">X</button></div>
            <div class="modal-body" id="gallery-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; overflow-y: auto;">
                <p>Gorseller yukleniyor...</p>
            </div>
        </div>`;
        document.body.appendChild(modal);
    }
    modal.style.display = "flex";
    loadGalleryImages();
}

function closeGallery() {
    document.getElementById("gallery-modal").style.display = "none";
}

async function loadGalleryImages() {
    const grid = document.getElementById("gallery-grid");
    grid.innerHTML = "<p>Gorseller su an icin sohbet gecmisinde kayitlidir. Yakinda tam galeri destegi eklenecek.</p>";
}

// Image Gen / System Test
async function startImageMode() {
    showToast("Sistem Saglik Kontrolu Baslatiliyor...");

    addMessage("**Sistem Analizi Baslatildi...**\nTum yerel modeller kontrol ediliyor. Lutfen bekleyin.", 'ai');

    try {
        const res = await fetch('/system/test_agents');
        const data = await res.json();

        if (data.status === "error") {
            addMessage(`**Hata:** ${data.msg}`, 'ai error');
            return;
        }

        let report = "### JARVIS Sistem Raporu\n\n";
        data.forEach(item => {
            const icon = item.status === "OK" ? "[OK]" : "[FAIL]";
            report += `**${item.agent}** (${item.model})\n- Durum: ${icon} ${item.status}\n`;
            if (item.time) report += `- Sure: ${item.time}\n`;
            if (item.response) report += `- Yanit: ${item.response}\n`;
            report += "\n";
        });

        addMessage(report, 'ai');
    } catch (e) {
        addMessage(`Sistem Testi Basarisiz: ${e}`, 'ai error');
    }
}

let currentModeState = "cloud";
async function toggleModelMode() {
    currentModeState = currentModeState === "cloud" ? "local" : "cloud";

    const formData = new FormData();
    formData.append('mod', currentModeState);

    try {
        const res = await fetch('/set_model', { method: 'POST', body: formData });
        const data = await res.json();
        const display = document.getElementById('model-display');
        display.innerHTML = data.current + ' <span style="opacity:0.5; font-size:10px; margin-left:5px">▼</span>';
        showToast(`Mod Degistirildi: ${data.current}`);
    } catch (e) {
        console.error("Mode toggle failed", e);
    }
}

async function deleteChat(filename, event) {
    if (event) event.stopPropagation();
    if (!confirm("Bu sohbeti silmek istediginize emin misiniz?")) return;

    const formData = new FormData();
    formData.append('filename', filename);
    const res = await fetch('/delete_chat', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.status === "deleted") {
        loadSidebarHistory();
    }
}

async function restartApp() {
    if (!confirm("Uygulama tamamen yeniden baslatilacak. Emin misiniz?")) return;

    showToast("Uygulama Kapatiliyor ve Yenileniyor...");
    try {
        await fetch('/system/restart', { method: 'POST' });
        setTimeout(() => { window.close(); }, 1000);
    } catch (e) {
        console.error("Restart failed", e);
    }
}

// Voice Presets
const VOICE_PRESETS = [
    "8eSMFxjAUgbRqmAkLPBt",
    "FvxJI7vwUDkTkEOO7nd7",
    "o9DOmAyPjfFu8AfoFAnM",
    "c1An0BcfdBgMtEqajijL",
    "OaQfGOEvUip9NEh44CYG",
    "VU4rWgX2OfLkqUsPis02",
    "Gfpl8Yo74Is0W6cPUWWT",
    "uYXf8XasLslADfZ2MB4u",
    ""
];

function toggleCustomVoiceInput() {
    const preset = document.getElementById('voice-preset');
    const customContainer = document.getElementById('custom-voice-container');
    if (preset && preset.value === 'custom') {
        if (customContainer) customContainer.style.display = 'block';
    } else {
        if (customContainer) customContainer.style.display = 'none';
    }
}

// Settings
async function loadConfig() {
    try {
        const res = await fetch('/get_settings');
        const config = await res.json();

        const themeSel = document.getElementById('theme-selector');
        if (themeSel) {
            if (config.theme === "Açık" || config.theme === "Light") themeSel.value = "Açık";
            else if (config.theme === "Koyu" || config.theme === "Dark") themeSel.value = "Koyu";
            else themeSel.value = "Sistem";
        }

        const modelSel = document.getElementById('model-selector');
        if (modelSel) modelSel.value = config.engine_mode || "api";

        const voiceToggle = document.getElementById('voice-toggle');
        if (voiceToggle) voiceToggle.checked = config.audio_enabled || false;

        const savedId = config.elevenlabs_voice_id || "";
        const presetSel = document.getElementById('voice-preset');
        const customInput = document.getElementById('voice-id-input');

        if (presetSel && customInput) {
            if (VOICE_PRESETS.includes(savedId)) {
                presetSel.value = savedId;
                customInput.value = "";
            } else {
                presetSel.value = "custom";
                customInput.value = savedId;
            }
            toggleCustomVoiceInput();
        }

        changeTheme();
    } catch (e) {
        console.error("Config load failed", e);
    }
}

async function saveConfig() {
    const themeSel = document.getElementById('theme-selector');
    const modelSel = document.getElementById('model-selector');
    const voiceToggle = document.getElementById('voice-toggle');
    const presetSel = document.getElementById('voice-preset');
    const customInput = document.getElementById('voice-id-input');

    const theme = themeSel ? themeSel.value : "Sistem";
    const model = modelSel ? modelSel.value : "api";
    const voice = voiceToggle ? voiceToggle.checked : false;

    let voiceId = "";
    if (presetSel && presetSel.value === "custom") {
        voiceId = customInput ? customInput.value.trim() : "";
    } else if (presetSel) {
        voiceId = presetSel.value;
    }

    const formData = new FormData();
    formData.append('theme', theme);
    formData.append('language', 'tr');
    formData.append('model', model);
    formData.append('voice', voice);
    formData.append('voice_id', voiceId);

    try {
        const res = await fetch('/save_settings', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.status === "saved") {
            showToast("Ayarlar Kaydedildi");
            document.getElementById('settings-modal').style.display = 'none';
            changeTheme();

            const display = document.getElementById('model-display');
            if (display) {
                display.innerHTML = (model === 'cloud' || model === 'api' ? 'JARVIS PRO 1.0' : 'YEREL BEYIN') + ' <span style="opacity:0.5; font-size:10px; margin-left:5px">▼</span>';
            }
        }
    } catch (e) {
        showToast("Ayarlar Kaydedilemedi: " + e);
    }
}

// =============================================
//  INITIALIZATION
// =============================================

document.addEventListener("DOMContentLoaded", () => {
    loadConfig();
    changeTheme();
    loadHistory();
    loadSidebarHistory();
    initSidebarSearch();    // Feature 3
    initKeyboardShortcuts(); // Feature 4
});
