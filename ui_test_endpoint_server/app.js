/**
 * Agent Studio - Live Endpoint Tester (Frontend Logic)
 * =====================================================
 * Menguji endpoint live agent yang sudah dipublish dengan interface bubble chat.
 */

document.addEventListener("DOMContentLoaded", () => {
  // --- DOM Elements ---
  const endpointInput = document.getElementById("endpointInput");
  const tokenInput = document.getElementById("tokenInput");
  const sessionIdInput = document.getElementById("sessionIdInput");
  const currentSessionDisplay = document.getElementById("currentSessionDisplay");
  
  const btnToggleSettings = document.getElementById("btnToggleSettings");
  const settingsToggleLabel = document.getElementById("settingsToggleLabel");
  const configPanel = document.getElementById("configPanel");
  
  const btnToggleTokenVisibility = document.getElementById("btnToggleTokenVisibility");
  const btnGenerateSession = document.getElementById("btnGenerateSession");
  const btnQuickLocal = document.getElementById("btnQuickLocal");
  const btnQuickEC2 = document.getElementById("btnQuickEC2");
  
  const statusIndicator = document.getElementById("statusIndicator");
  const statusText = document.getElementById("statusText");
  
  const chatMessages = document.getElementById("chatMessages");
  const welcomeCard = document.getElementById("welcomeCard");
  const chatForm = document.getElementById("chatForm");
  const messageInput = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const btnClearChat = document.getElementById("btnClearChat");

  // Inspector Elements
  const btnRawInspector = document.getElementById("btnRawInspector");
  const inspectorModal = document.getElementById("inspectorModal");
  const btnCloseInspector = document.getElementById("btnCloseInspector");
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const rawReqDisplay = document.getElementById("rawReqDisplay");
  const rawResDisplay = document.getElementById("rawResDisplay");
  const rawCurlDisplay = document.getElementById("rawCurlDisplay");
  const resStatusTag = document.getElementById("resStatusTag");
  const btnCopyReq = document.getElementById("btnCopyReq");
  const btnCopyRes = document.getElementById("btnCopyRes");
  const btnCopyCurl = document.getElementById("btnCopyCurl");

  // State
  let lastRequestData = null;
  let lastResponseData = null;
  let lastCurlCommand = "";
  let isSending = false;

  // --- 1. Inisialisasi & Persistence LocalStorage ---
  const DEFAULT_EC2_ENDPOINT = "http://13.250.191.160:8080/agents/pandu-bpjs-sehattt/invoke";
  const DEFAULT_LOCAL_ENDPOINT = "http://localhost:8080/agents/pandu-bpjs-sehattt/invoke";
  const DEFAULT_TOKEN = "agy_live_7f0e5c8c0fd8daac6d720fab";

  function loadSavedConfig() {
    const savedEndpoint = localStorage.getItem("agy_tester_endpoint") || DEFAULT_EC2_ENDPOINT;
    const savedToken = localStorage.getItem("agy_tester_token") || DEFAULT_TOKEN;
    const savedSession = localStorage.getItem("agy_tester_session") || generateNewSessionId();

    endpointInput.value = savedEndpoint;
    tokenInput.value = savedToken;
    sessionIdInput.value = savedSession;
    updateSessionDisplay(savedSession);
  }

  function saveConfig() {
    localStorage.setItem("agy_tester_endpoint", endpointInput.value.trim());
    localStorage.setItem("agy_tester_token", tokenInput.value.trim());
    localStorage.setItem("agy_tester_session", sessionIdInput.value.trim());
    updateSessionDisplay(sessionIdInput.value.trim());
  }

  function generateNewSessionId() {
    const randomHex = Math.random().toString(36).substring(2, 8);
    return `sesi-tester-${randomHex}`;
  }

  function updateSessionDisplay(id) {
    currentSessionDisplay.textContent = `Sesi: ${id || "default"}`;
  }

  // Listener simpan konfigurasi saat input berubah
  endpointInput.addEventListener("input", saveConfig);
  tokenInput.addEventListener("input", saveConfig);
  sessionIdInput.addEventListener("input", saveConfig);

  btnGenerateSession.addEventListener("click", () => {
    const newId = generateNewSessionId();
    sessionIdInput.value = newId;
    saveConfig();
    showToast(`Session ID baru: ${newId}`);
  });

  btnToggleTokenVisibility.addEventListener("click", () => {
    if (tokenInput.type === "password") {
      tokenInput.type = "text";
      btnToggleTokenVisibility.textContent = "🔒";
    } else {
      tokenInput.type = "password";
      btnToggleTokenVisibility.textContent = "👁️";
    }
  });

  btnQuickLocal.addEventListener("click", () => {
    endpointInput.value = DEFAULT_LOCAL_ENDPOINT;
    saveConfig();
  });

  btnQuickEC2.addEventListener("click", () => {
    endpointInput.value = DEFAULT_EC2_ENDPOINT;
    saveConfig();
  });

  btnToggleSettings.addEventListener("click", () => {
    configPanel.classList.toggle("collapsed");
    const isCollapsed = configPanel.classList.contains("collapsed");
    settingsToggleLabel.textContent = isCollapsed ? "Buka Konfigurasi" : "Sembunyikan Konfigurasi";
  });

  // --- 2. Auto-expand Textarea & Send Shortcuts ---
  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 140)}px`;
  });

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Quick prompt chips
  document.querySelectorAll(".prompt-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      messageInput.value = prompt;
      messageInput.focus();
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  // Clear chat
  btnClearChat.addEventListener("click", () => {
    if (confirm("Apakah Anda yakin ingin menghapus riwayat chat saat ini?")) {
      chatMessages.innerHTML = "";
      chatMessages.appendChild(welcomeCard);
      welcomeCard.style.display = "block";
    }
  });

  // --- 3. Chat Form Submit & HTTP POST Handler ---
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || isSending) return;

    const endpoint = endpointInput.value.trim();
    const token = tokenInput.value.trim();
    const sessionId = sessionIdInput.value.trim() || generateNewSessionId();

    if (!endpoint) {
      alert("Silakan masukkan Endpoint URL terlebih dahulu!");
      endpointInput.focus();
      return;
    }

    // Sembunyikan welcome card saat ada pesan pertama
    if (welcomeCard) {
      welcomeCard.style.display = "none";
    }

    // 1. Tampilkan bubble pesan dari User
    appendUserBubble(text);
    messageInput.value = "";
    messageInput.style.height = "auto";

    // 2. Tampilkan typing indicator agent
    const typingIndicator = appendTypingIndicator();
    setSendingStatus(true);

    const startTime = performance.now();

    // Siapkan Request Payload & Header
    const payload = {
      session_id: sessionId,
      message: text,
    };

    const headers = {
      "Content-Type": "application/json",
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
      headers["x-api-key"] = token;
    }

    // Simpan data untuk raw inspector & generate cURL
    lastRequestData = {
      url: endpoint,
      method: "POST",
      headers,
      body: payload,
    };
    lastCurlCommand = generateCurlCommand(endpoint, headers, payload);
    updateInspectorContent();

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const latencyMs = Math.round(performance.now() - startTime);
      const latencySec = (latencyMs / 1000).toFixed(2);

      let responseData = null;
      const textBody = await response.text();

      try {
        responseData = JSON.parse(textBody);
      } catch (err) {
        responseData = { raw_body: textBody };
      }

      lastResponseData = {
        status: response.status,
        statusText: response.statusText,
        data: responseData,
        latency: `${latencySec}s`,
      };
      updateInspectorContent();

      // Hapus typing indicator
      typingIndicator.remove();

      if (response.ok) {
        // Ambil pesan balasan dari agen
        const replyText = responseData.response || JSON.stringify(responseData, null, 2);
        appendAgentBubble(replyText, {
          latency: `${latencySec}s`,
          turnCount: responseData.turn_count || 1,
          toolCalls: responseData.tool_calls || [],
          agentSlug: responseData.agent_slug || "agent",
        });
        setStatusReady();
      } else {
        // HTTP Error (401 Unauthorized, 404 Not Found, 500, dll)
        appendErrorBubble(
          `Error ${response.status} (${response.statusText}):\n\n` +
          `${typeof responseData === 'object' ? JSON.stringify(responseData, null, 2) : responseData}`,
          response.status
        );
        setStatusError(`HTTP ${response.status}`);
      }
    } catch (err) {
      typingIndicator.remove();
      const latencyMs = Math.round(performance.now() - startTime);
      lastResponseData = {
        status: 0,
        statusText: "Network / CORS Error",
        error: err.message,
      };
      updateInspectorContent();

      appendErrorBubble(
        `Gagal terhubung ke endpoint:\n${err.message}\n\n` +
        `• Pastikan server di ${endpoint} sedang berjalan.\n` +
        `• Jika menggunakan IP EC2, pastikan Security Group AWS mengizinkan inbound port 8080.\n` +
        `• Buka tab "Raw JSON" untuk menyalin cURL dan mengujinya langsung di terminal/Postman.`,
        0
      );
      setStatusError("Koneksi Gagal");
    } finally {
      setSendingStatus(false);
      scrollChatToBottom();
    }
  });

  // --- 4. Render Message Bubbles ---
  function appendUserBubble(text) {
    const row = document.createElement("div");
    row.className = "message-row user";

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    row.innerHTML = `
      <div class="avatar user-avatar">U</div>
      <div class="message-content-wrapper">
        <div class="message-meta">
          <span>Anda</span> &bull; <span>${now}</span>
        </div>
        <div class="message-bubble">${escapeHtml(text)}</div>
      </div>
    `;

    chatMessages.appendChild(row);
    scrollChatToBottom();
  }

  function appendAgentBubble(markdownContent, meta) {
    const row = document.createElement("div");
    row.className = "message-row agent";

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Render Markdown dengan marked jika tersedia, fallback teks biasa
    let parsedHtml = "";
    if (window.marked && typeof window.marked.parse === "function") {
      parsedHtml = window.marked.parse(markdownContent);
    } else {
      parsedHtml = `<p>${escapeHtml(markdownContent).replace(/\n/g, "<br>")}</p>`;
    }

    // Buat blok Tool Calls jika agen mengeksekusi tool/API
    let toolCallsHtml = "";
    if (meta.toolCalls && meta.toolCalls.length > 0) {
      const toolItems = meta.toolCalls.map(tc => {
        const name = tc.name || tc.tool || "tool";
        const args = tc.arguments ? JSON.stringify(tc.arguments) : "";
        return `<div class="tool-item">⚡ <strong>${escapeHtml(name)}</strong> ${args ? `<code>${escapeHtml(args)}</code>` : ""}</div>`;
      }).join("");

      toolCallsHtml = `
        <div class="tool-calls-container">
          <div class="tool-calls-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <span>🛠️ Tool Calls (${meta.toolCalls.length})</span>
            <span style="font-size: 10px; color: #3b82f6;">Detail &or;</span>
          </div>
          <div class="tool-calls-list hidden">
            ${toolItems}
          </div>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="avatar agent-avatar">AI</div>
      <div class="message-content-wrapper">
        <div class="message-meta">
          <span>${escapeHtml(meta.agentSlug)}</span> &bull; <span>${now}</span>
        </div>
        <div class="message-bubble">
          ${parsedHtml}
          ${toolCallsHtml}
          <div class="bubble-footer">
            <span>⚡ ${meta.latency}</span>
            <span>&bull;</span>
            <span>Turn: ${meta.turnCount}</span>
          </div>
        </div>
      </div>
    `;

    chatMessages.appendChild(row);
    scrollChatToBottom();
  }

  function appendErrorBubble(errorMessage, statusCode) {
    const row = document.createElement("div");
    row.className = "message-row agent";

    row.innerHTML = `
      <div class="avatar" style="background: #ef4444; color: #fff;">!</div>
      <div class="message-content-wrapper">
        <div class="message-meta">
          <span style="color: #ef4444;">Server Error ${statusCode ? `(Code ${statusCode})` : ""}</span>
        </div>
        <div class="message-bubble" style="background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; font-family: var(--font-mono); font-size: 12px; white-space: pre-wrap;">${escapeHtml(errorMessage)}</div>
      </div>
    `;

    chatMessages.appendChild(row);
    scrollChatToBottom();
  }

  function appendTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row agent";
    row.id = "typingIndicator";

    row.innerHTML = `
      <div class="avatar agent-avatar">AI</div>
      <div class="message-content-wrapper">
        <div class="message-bubble typing-bubble">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;

    chatMessages.appendChild(row);
    scrollChatToBottom();
    return row;
  }

  function scrollChatToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // --- 5. Status Helper ---
  function setSendingStatus(sending) {
    isSending = sending;
    btnSend.disabled = sending;
    if (sending) {
      statusIndicator.className = "status-indicator loading";
      statusText.textContent = "Memproses...";
    }
  }

  function setStatusReady() {
    statusIndicator.className = "status-indicator";
    statusText.textContent = "Tersambung (200 OK)";
  }

  function setStatusError(text) {
    statusIndicator.className = "status-indicator error";
    statusText.textContent = text || "Error";
  }

  // --- 6. Inspector & cURL Generator ---
  function generateCurlCommand(url, headers, body) {
    const headerFlags = Object.entries(headers)
      .map(([k, v]) => `-H "${k}: ${v}"`)
      .join(" \\\n  ");
    const jsonBody = JSON.stringify(body, null, 2).replace(/"/g, '\\"');

    return `curl -X POST "${url}" \\\n  ${headerFlags} \\\n  -d '${JSON.stringify(body)}'`;
  }

  function updateInspectorContent() {
    if (lastRequestData) {
      rawReqDisplay.textContent = JSON.stringify(lastRequestData, null, 2);
    }
    if (lastResponseData) {
      resStatusTag.textContent = `Status: ${lastResponseData.status} ${lastResponseData.statusText || ""}`;
      rawResDisplay.textContent = JSON.stringify(lastResponseData, null, 2);
    }
    if (lastCurlCommand) {
      rawCurlDisplay.textContent = lastCurlCommand;
    }
  }

  btnRawInspector.addEventListener("click", () => {
    inspectorModal.classList.add("open");
  });

  btnCloseInspector.addEventListener("click", () => {
    inspectorModal.classList.remove("open");
  });

  inspectorModal.addEventListener("click", (e) => {
    if (e.target === inspectorModal) {
      inspectorModal.classList.remove("open");
    }
  });

  // Tab switching inside modal
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.add("hidden"));

      btn.classList.add("active");
      const targetTab = document.getElementById(btn.getAttribute("data-tab"));
      if (targetTab) {
        targetTab.classList.remove("hidden");
      }
    });
  });

  // Copy buttons
  btnCopyReq.addEventListener("click", () => copyToClipboard(rawReqDisplay.textContent, btnCopyReq));
  btnCopyRes.addEventListener("click", () => copyToClipboard(rawResDisplay.textContent, btnCopyRes));
  btnCopyCurl.addEventListener("click", () => copyToClipboard(rawCurlDisplay.textContent, btnCopyCurl));

  function copyToClipboard(text, btnElement) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = btnElement.textContent;
      btnElement.textContent = "Disalin! ✓";
      setTimeout(() => {
        btnElement.textContent = orig;
      }, 1500);
    });
  }

  function showToast(msg) {
    // Simple temporary indicator
    const current = statusText.textContent;
    statusText.textContent = msg;
    setTimeout(() => {
      statusText.textContent = current;
    }, 2000);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initial Load
  loadSavedConfig();
});
