const chatBox = document.getElementById('chat-box');
const input = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');
const welcomeScreen = document.getElementById('welcome-screen');
const historyList = document.getElementById('history-list');

let isGenerating = false;

// Auto Resize Textarea
function autoResize(textarea) {
    textarea.style.height = 'auto'; // Reset
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'; // Max 200px
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
        // Reset and reload history list
        input.value = '';
        updateSendButtonState();

        loadSidebarHistory(); // Refresh sidebar to show archived chat
    } catch (e) {
        console.error("New chat error", e);
    }
}

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
    // 2. Show Thinking/Loading
    const loadingId = "loader-" + Date.now();
    showLoading(loadingId);
    isGenerating = true;

    // Check for image generation to start polling
    if (text.toLowerCase().includes("çiz") || text.toLowerCase().includes("oluştur")) {
        startProgressPolling(loadingId);
    }

    // 3. API Call
    try {
        const formData = new FormData();
        formData.append('mesaj', text);
        formData.append('mod', 'sohbet'); // Default mode

        const response = await fetch('/chat', { method: 'POST', body: formData });
        const data = await response.json();

        // Remove Loading
        stopProgressPolling();
        removeLoading(loadingId);

        // Check if data is valid
        if (!data || !data.cevap) {
            throw new Error("Boş cevap alındı");
        }

        // 4. Stream/Typewriter Effect for AI Response
        addMessage(data.cevap, 'ai');

        // Add to history (visual only)
        addToHistory(text);

    } catch (error) {
        stopProgressPolling();
        removeLoading(loadingId);
        console.error("Bağlantı Hatası:", error);
        // addMessage("⚠️ Bağlantı kurulamadı efendim. Lütfen sistemi kontrol edin.", 'ai error'); // HIDDEN AS REQUESTED
        isGenerating = false;
        return;
    }
    isGenerating = false;
}

// Theme Management
function changeTheme() {
    const themeSelector = document.getElementById('theme-selector'); // We will add an ID to the select
    const selectedTheme = themeSelector ? themeSelector.value : 'System';
    const body = document.body;

    if (selectedTheme === 'Açık') {
        body.classList.add('light-mode');
    } else if (selectedTheme === 'Koyu') {
        body.classList.remove('light-mode');
    } else {
        // System
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            body.classList.add('light-mode');
        } else {
            body.classList.remove('light-mode');
        }
    }
}

// Initial Theme Check
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

        // Clear existing items (keep label)
        // historyList has a label at index 0 (or class). 
        // Let's rebuilding cleaner:
        historyList.innerHTML = '<div class="history-active-label">Geçmiş Sohbetler</div>';

        archives.forEach(chat => {
            const item = document.createElement('div');
            item.className = 'history-item';
            // Filename format: chat_TIMESTAMP_Title.json
            // Clean display title
            let display = chat.filename.replace("chat_", "").replace(".json", "");
            // Remove timestamp prefix 20260211_220000_
            const parts = display.split("_");
            if (parts.length > 2) {
                display = parts.slice(2).join(" ");
            }

            item.innerText = display || "Adsız Sohbet";
            item.onclick = () => loadOldChat(chat.filename);
            historyList.appendChild(item);
        });
    } catch (e) {
        console.error("Sidebar load failed", e);
    }
}

async function loadOldChat(filename) {
    const formData = new FormData();
    formData.append('filename', filename);
    await fetch('/load_chat', { method: 'POST', body: formData });

    // Reload messages
    chatBox.innerHTML = '';
    loadHistory(); // Re-fetch active history
    loadSidebarHistory(); // Refresh list (maybe order changed)
}

// Old DOMContentLoaded listener removed to avoid duplication
// document.addEventListener('DOMContentLoaded', () => { ... });

function addMessage(text, role) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const content = document.createElement('div');
    content.className = 'message-content';

    const avatar = document.createElement('div');
    avatar.className = `avatar ${role}`;
    avatar.innerText = role === 'user' ? 'S' : '🧠'; // Use 'S' for Seyit
    if (role === 'ai') avatar.innerHTML = '<svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="18" width="18" xmlns="http://www.w3.org/2000/svg" style="color:#000"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path></svg>';

    const textDiv = document.createElement('div');
    textDiv.className = 'text-content';

    let formatted = text.replace(/\n/g, '<br>');

    // Markdown Image Renderer with Download Button
    formatted = formatted.replace(
        /!\[(.*?)\]\((.*?)\)/g,
        '<div class="generated-image-container">' +
        '<a href="$2" target="_blank"><img src="$2" alt="$1" style="max-width:100%; border-radius:10px; margin-top:10px;"></a>' +
        '<button class="download-btn" onclick="downloadImage(\'$2\')">⬇️ İndir</button>' +
        '</div><br>'
    );

    if (formatted.includes("```")) {
        formatted = formatted.replace(/```(.*?)```/gs, '<pre style="background:var(--input-bg); padding:10px; border-radius:5px; overflow-x:auto;"><code>$1</code></pre>');
    }

    textDiv.innerHTML = formatted;

    content.appendChild(avatar);
    content.appendChild(textDiv);
    row.appendChild(content);

    chatBox.appendChild(row);

    // Scroll Logic - Wait for animation slightly or scroll immediately to bottom
    setTimeout(() => {
        window.scrollTo({ left: 0, top: document.body.scrollHeight, behavior: "smooth" });
        const scrollContainer = document.querySelector('.chat-area');
        scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: "smooth" });
    }, 50);
}

async function downloadImage(url) {
    showToast("İndirme Penceresi Açılıyor...");
    const formData = new FormData();
    formData.append('image_url', url);

    try {
        const res = await fetch('/save_generated_image', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.status === "ok") {
            showToast("Resim Kaydedildi: " + data.path);
        } else if (data.status === "cancelled") {
            showToast("İptal Edildi");
        } else {
            showToast("Hata: " + data.message);
        }
    } catch (e) {
        showToast("Bağlantı Hatası");
    }
}

// Loading Indicator
function showLoading(id) {
    const chatBox = document.getElementById('chat-box');
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

    // Scroll to bottom
    const scrollContainer = document.querySelector('.chat-area');
    if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight;

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

    // Wait for element to exist
    setTimeout(() => {
        const loaderDiv = document.getElementById(elementId);
        if (!loaderDiv) return;

        // Find text content div to inject progress bar
        const textContent = loaderDiv.querySelector('.text-content');
        if (!textContent) return;

        // Create progress bar if not exists
        if (!textContent.querySelector(".progress-container")) {
            const pCont = document.createElement('div');
            pCont.className = 'progress-container';
            pCont.style.marginTop = '10px';
            pCont.style.width = '100%';
            pCont.innerHTML = `
                <div style="font-size:12px; margin-bottom:5px; color:#aaa;" id="${elementId}-status">Hazırlanıyor...</div>
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
                    if (stat) stat.innerText = data.message || `Oluşturuluyor... %${data.percent}`;
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

// Listeners
input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Gallery Mode
function showGallery() {
    let modal = document.getElementById("gallery-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "gallery-modal";
        modal.className = "modal-overlay";
        modal.innerHTML = `
        <div class="modal-content" style="max-width:800px; width:90%; max-height:80vh;">
            <div class="modal-header"><h3>JARVIS Galeri</h3><button class="btn-close" onclick="closeGallery()">✕</button></div>
            <div class="modal-body" id="gallery-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; overflow-y: auto;">
                <p>Görseller yükleniyor...</p>
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
    grid.innerHTML = "<p>Görseller şu an için sohbet geçmişinde 'Yapay Zeka Görseli' olarak kayıtlıdır. Yakında tam galeri desteği eklenecek.</p>";
}

// Image Gen Start
// Image Gen Start -> Now System Test
async function startImageMode() {
    showToast("Sistem Sağlık Kontrolü Başlatılıyor...");

    addMessage("🔄 **Sistem Analizi Başlatıldı...**\nTüm yerel modeller kontrol ediliyor. Lütfen bekleyin.", 'ai');

    try {
        const res = await fetch('/system/test_agents');
        const data = await res.json();

        if (data.status === "error") {
            addMessage(`❌ **Hata:** ${data.msg}`, 'ai error');
            return;
        }

        let report = "### 🛡️ JARVIS Sistem Raporu\n\n";
        data.forEach(item => {
            const icon = item.status === "OK" ? "✅" : "❌";
            report += `**${item.agent}** (${item.model})\n- Durum: ${icon} ${item.status}\n`;
            if (item.time) report += `- Süre: ${item.time}\n`;
            if (item.response) report += `- Yanıt: ${item.response}\n`;
            report += "\n";
        });

        addMessage(report, 'ai');

    } catch (e) {
        addMessage(`❌ Sistem Testi Başarısız: ${e}`, 'ai error');
    }
}

let currentModeState = "cloud"; // default
async function toggleModelMode() {
    currentModeState = currentModeState === "cloud" ? "local" : "cloud";

    const formData = new FormData();
    formData.append('mod', currentModeState);

    try {
        const res = await fetch('/set_model', { method: 'POST', body: formData });
        const data = await res.json();

        const display = document.getElementById('model-display');
        display.innerHTML = data.current + ' <span style="opacity:0.5; font-size:10px; margin-left:5px">▼</span>';

        showToast(`Mod Değiştirildi: ${data.current} `);
    } catch (e) {
        console.error("Mode toggle failed", e);
    }
}

// Delete Chat Override
async function deleteChat(filename, event) {
    if (event) event.stopPropagation();
    if (!confirm("Bu sohbeti silmek istediğinize emin misiniz?")) return;

    const formData = new FormData();
    formData.append('filename', filename);
    const res = await fetch('/delete_chat', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.status === "deleted") {
        loadSidebarHistory(); // Refresh
    }
}

// Update History Item Builder to include Delete
const oldLoadSidebar = loadSidebarHistory;
loadSidebarHistory = async function () {
    await oldLoadSidebar();
    try {
        const res = await fetch('/get_archives');
        const archives = await res.json();

        historyList.innerHTML = '<div class="history-active-label">Geçmiş Sohbetler</div>';

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
            textSpan.innerText = display || "Adsız Sohbet";
            textSpan.style.overflow = "hidden";
            textSpan.style.textOverflow = "ellipsis";
            textSpan.style.whiteSpace = "nowrap";
            textSpan.onclick = () => loadOldChat(chat.filename);

            const delBtn = document.createElement("span");
            delBtn.innerText = "🗑️";
            delBtn.style.cursor = "pointer";
            delBtn.style.fontSize = "12px";
            delBtn.style.opacity = "0.5";
            delBtn.style.padding = "0 5px";
            delBtn.onmouseover = () => delBtn.style.opacity = "1";
            delBtn.onmouseout = () => delBtn.style.opacity = "0.5";
            delBtn.onclick = (e) => deleteChat(chat.filename, e);

            item.appendChild(textSpan);
            item.appendChild(delBtn);
            historyList.appendChild(item);
        });
    } catch (e) {
        console.error("Sidebar load failed", e);
    }
}

async function restartApp() {
    if (!confirm("Uygulama tamamen yeniden başlatılacak. Emin misiniz?")) return;

    showToast("Uygulama Kapatılıyor ve Yenileniyor...");
    try {
        await fetch('/system/restart', { method: 'POST' });
        setTimeout(() => {
            window.close();
        }, 1000);
    } catch (e) {
        console.error("Restart failed", e);
    }
}

// Helper to specific Presets
const VOICE_PRESETS = [
    "8eSMFxjAUgbRqmAkLPBt",
    "FvxJI7vwUDkTkEOO7nd7", // Pelin
    "o9DOmAyPjfFu8AfoFAnM",
    "c1An0BcfdBgMtEqajijL",
    "OaQfGOEvUip9NEh44CYG",
    "VU4rWgX2OfLkqUsPis02", // Mahdi
    "Gfpl8Yo74Is0W6cPUWWT", // Max
    "uYXf8XasLslADfZ2MB4u", // Hope
    ""
];

// Toggle Custom Input Visibility
function toggleCustomVoiceInput() {
    const preset = document.getElementById('voice-preset');
    const customContainer = document.getElementById('custom-voice-container');
    if (preset && preset.value === 'custom') {
        if (customContainer) customContainer.style.display = 'block';
    } else {
        if (customContainer) customContainer.style.display = 'none';
        // Optional: clear input or sync 
    }
}

// Settings Logic
async function loadConfig() {
    try {
        const res = await fetch('/get_settings');
        const config = await res.json();

        // Theme
        const themeSel = document.getElementById('theme-selector');
        if (themeSel) {
            if (config.theme === "Açık" || config.theme === "Light") themeSel.value = "Açık";
            else if (config.theme === "Koyu" || config.theme === "Dark") themeSel.value = "Koyu";
            else themeSel.value = "Sistem";
        }

        // Model
        const modelSel = document.getElementById('model-selector');
        if (modelSel) modelSel.value = config.engine_mode || "api";

        // Voice
        const voiceToggle = document.getElementById('voice-toggle');
        if (voiceToggle) voiceToggle.checked = config.audio_enabled || false;

        // Voice ID & Preset Logic
        const savedId = config.elevenlabs_voice_id || "";
        const presetSel = document.getElementById('voice-preset');
        const customInput = document.getElementById('voice-id-input');

        if (presetSel && customInput) {
            // Check if savedId is in presets OR is empty (default Rachel)
            if (VOICE_PRESETS.includes(savedId)) {
                presetSel.value = savedId;
                customInput.value = "";
            } else {
                presetSel.value = "custom";
                customInput.value = savedId;
            }
            toggleCustomVoiceInput();
        }

        // Apply visual theme immediately
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

    // Voice ID Login
    let voiceId = "";
    if (presetSel && presetSel.value === "custom") {
        voiceId = customInput ? customInput.value.trim() : "";
    } else if (presetSel) {
        voiceId = presetSel.value;
    }

    const formData = new FormData();
    formData.append('theme', theme);
    formData.append('language', 'tr'); // Default for now
    formData.append('model', model);
    formData.append('voice', voice);
    formData.append('voice_id', voiceId);

    try {
        const res = await fetch('/save_settings', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.status === "saved") {
            showToast("Ayarlar Kaydedildi");
            document.getElementById('settings-modal').style.display = 'none';

            // Visual Updates if needed
            changeTheme();

            // Update Model Display Name
            const display = document.getElementById('model-display');
            if (display) {
                display.innerHTML = (model === 'cloud' || model === 'api' ? 'JARVIS PRO 1.0' : 'YEREL BEYİN') + ' <span style="opacity:0.5; font-size:10px; margin-left:5px">▼</span>';
            }
        }
    } catch (e) {
        showToast("Ayarlar Kaydedilemedi: " + e);
    }
}

// Call on load
document.addEventListener("DOMContentLoaded", () => {
    loadConfig();
    // Existing setup
    changeTheme();
    loadHistory();
    loadSidebarHistory();
});
