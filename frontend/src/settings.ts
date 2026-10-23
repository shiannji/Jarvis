/**
 * JARVIS — Settings Panel
 *
 * Overlay panel for API keys, connection status, preferences, and system info.
 * Slides in from the right with glass-morphism styling.
 *
 * Every label is a constant of this file, in the language the page was told
 * (i18n.ts) — the template below is static markup, never anything a server
 * or a user wrote.
 */

import { isZh } from "./i18n";

/** English or Mandarin, side by side at the point of use. */
function L(en: string, zh: string): string {
  return isZh() ? zh : en;
}

let sampleVoice: ((text: string) => void) | null = null;

/** The page's own voice, for the "test the voice" button. */
export function setSampleVoice(fn: (text: string) => void) {
  sampleVoice = fn;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StatusResponse {
  claude_code_installed: boolean;
  server_port: number;
  uptime_seconds: number;
  language?: string;
  voice?: string;      // the voice actually in use: "fish" | "browser"
  tts_mode?: string;   // what was asked for: "auto" | "fish" | "browser"
  env_keys_set: {
    fish_audio: boolean;
    fish_voice_id: boolean;
    user_name: string;
  };
}

interface PreferencesResponse {
  user_name: string;
  honorific: string;
  language?: string;
  voice?: string;
  browser_voice?: string;
}

/** Only a server with no voice at all needs the first-run wizard: Fish
 *  Audio or nothing, and no key. Every other install can already speak. */
function needsSetup(status: StatusResponse): boolean {
  const mode = status.tts_mode ?? "fish"; // an older server: Fish was the only voice
  return mode === "fish" && !status.env_keys_set.fish_audio;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let panelEl: HTMLElement | null = null;
let isOpen = false;
let isFirstTimeSetup = false;
let setupStep = 0; // 0=fish, 1=name, 2=done

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url);
  return res.json();
}

async function apiPost<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Panel HTML
// ---------------------------------------------------------------------------

function buildPanelHTML(): string {
  return `
    <div class="settings-backdrop" id="settings-backdrop"></div>
    <div class="settings-panel" id="settings-panel-inner">
      <div class="settings-header">
        <h2>${L("Settings", "設定")}</h2>
        <button class="settings-close" id="settings-close">&times;</button>
      </div>

      <div class="settings-welcome" id="settings-welcome" style="display:none">
        <p>${L("Welcome to JARVIS. Let's get you set up.", "歡迎使用 JARVIS，我們先完成設定。")}</p>
      </div>

      <div class="settings-body">

        <!-- Language & Voice -->
        <section class="settings-section" id="section-voice">
          <h3>${L("Language &amp; Voice", "語言與聲音")}</h3>

          <div class="settings-field">
            <label>${L("Language", "對話語言")}</label>
            <select id="input-language">
              <option value="zh-TW">繁體中文（台灣）</option>
              <option value="en">English</option>
            </select>
          </div>

          <div class="settings-field">
            <label>${L("Voice", "語音引擎")}</label>
            <select id="input-voice">
              <option value="auto">${L("Automatic — Fish Audio if there is a key, otherwise the browser's voice",
                                        "自動——有 Fish Audio 金鑰就用電影版聲音，沒有就用瀏覽器語音")}</option>
              <option value="fish">${L("Fish Audio only (the JARVIS voice, paid key)",
                                       "只用 Fish Audio（電影版 JARVIS 聲音，需付費金鑰）")}</option>
              <option value="browser">${L("Browser's built-in voice only (free)",
                                          "只用瀏覽器內建語音（免費）")}</option>
            </select>
          </div>

          <div class="settings-field">
            <label>${L("Browser voice name (optional)", "瀏覽器語音名稱（可留空）")}</label>
            <div class="settings-input-row">
              <input type="text" id="input-browser-voice" placeholder="${L("e.g. Daniel", "例如 Meijia 或 Google 國語")}" />
              <button class="settings-btn" id="btn-test-voice">${L("Test", "試聽")}</button>
            </div>
          </div>

          <p class="settings-restart-notice" id="voice-current"></p>
        </section>

        <!-- API Keys -->
        <section class="settings-section" id="section-api-keys">
          <h3>${L("API Keys", "API 金鑰")}</h3>

          <div class="settings-field">
            <label>${L("Fish Audio API Key (optional)", "Fish Audio API 金鑰（選填）")}</label>
            <div class="settings-input-row">
              <input type="password" id="input-fish-key" placeholder="${L("Fish Audio key...", "Fish Audio 金鑰…")}" />
              <button class="settings-btn" id="btn-test-fish">${L("Test", "測試")}</button>
              <span class="status-dot" id="status-fish"></span>
            </div>
          </div>

          <div class="settings-field">
            <label>Fish Voice ID</label>
            <div class="settings-input-row">
              <input type="text" id="input-fish-voice-id" placeholder="612b878b113047d9a770c069c8b4fdfe" />
              <button class="settings-btn" id="btn-save-voice-id">${L("Save", "儲存")}</button>
            </div>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-keys">${L("Save Keys", "儲存金鑰")}</button>
          </div>
          <p class="settings-restart-notice" id="keys-restart-notice" style="display:none">
            ${L("Saved. Restart the server (menu &rarr; Restart Server) for this to take effect.",
                "已儲存。請重新啟動伺服器（選單 &rarr; 重新啟動伺服器）才會生效。")}
          </p>
        </section>

        <!-- Connection Status -->
        <section class="settings-section" id="section-status">
          <h3>${L("Connection Status", "連線狀態")}</h3>
          <div class="status-grid">
            <div class="status-row"><span class="status-dot" id="status-claude-cli"></span><span>Claude Code CLI</span></div>
            <div class="status-row"><span class="status-dot" id="status-server"></span><span>${L("Server", "伺服器")}</span><span class="status-detail" id="status-server-detail"></span></div>
          </div>
        </section>

        <!-- User Preferences -->
        <section class="settings-section" id="section-preferences">
          <h3>${L("User Preferences", "個人偏好")}</h3>

          <div class="settings-field">
            <label>${L("Your Name", "你的名字")}</label>
            <input type="text" id="input-user-name" placeholder="${L("Your name", "你的名字")}" />
          </div>

          <div class="settings-field">
            <label>${L("Honorific", "稱謂")}</label>
            <select id="input-honorific">
              <option value="sir">${L("Sir", "Sir（先生）")}</option>
              <option value="ma'am">${L("Ma'am", "Ma'am（女士）")}</option>
              <option value="none">${L("None", "不用稱謂")}</option>
            </select>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-prefs">${L("Save Preferences", "儲存偏好")}</button>
          </div>
          <p class="settings-restart-notice" id="prefs-restart-notice" style="display:none">
            ${L("Saved. Language and voice take effect after a restart (menu &rarr; Restart Server).",
                "已儲存。語言與聲音要重新啟動伺服器後才會生效（選單 &rarr; 重新啟動伺服器）。")}
          </p>
        </section>

        <!-- System Info -->
        <section class="settings-section" id="section-sysinfo">
          <h3>${L("System Info", "系統資訊")}</h3>
          <div class="sysinfo-grid">
            <div class="sysinfo-row"><span class="sysinfo-label">${L("Server port", "伺服器連接埠")}</span><span id="sysinfo-port">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">${L("Uptime", "已運行")}</span><span id="sysinfo-uptime">--</span></div>
          </div>
        </section>

        <!-- Setup Navigation (first-time only) -->
        <div class="setup-nav" id="setup-nav" style="display:none">
          <button class="settings-btn primary" id="btn-setup-next">${L("Next", "下一步")}</button>
        </div>

      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Panel lifecycle
// ---------------------------------------------------------------------------

function createPanel(): HTMLElement {
  const container = document.createElement("div");
  container.id = "settings-container";
  container.innerHTML = buildPanelHTML();
  document.body.appendChild(container);
  return container;
}

function setDotStatus(id: string, status: "green" | "red" | "yellow" | "off") {
  const dot = document.getElementById(id);
  if (!dot) return;
  dot.className = "status-dot";
  if (status !== "off") dot.classList.add(`status-${status}`);
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

async function loadStatus() {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");

    setDotStatus("status-claude-cli", status.claude_code_installed ? "green" : "red");
    setDotStatus("status-server", "green");

    const serverDetail = document.getElementById("status-server-detail");
    if (serverDetail) serverDetail.textContent = L(
      `port ${status.server_port} | up ${formatUptime(status.uptime_seconds)}`,
      `連接埠 ${status.server_port}｜已運行 ${formatUptime(status.uptime_seconds)}`);

    // Which voice is speaking right now — what the server booted with, which
    // a saved but not yet restarted choice may not match.
    const current = document.getElementById("voice-current");
    if (current) {
      const voice = status.voice === "browser"
        ? L("the browser's built-in voice", "瀏覽器內建語音")
        : "Fish Audio";
      current.textContent = L(`Speaking now with ${voice}.`, `目前使用：${voice}。`);
    }

    // API key status dots
    setDotStatus("status-fish", status.env_keys_set.fish_audio ? "green" : "red");

    // System info
    const portEl = document.getElementById("sysinfo-port");
    if (portEl) portEl.textContent = String(status.server_port);
    const upEl = document.getElementById("sysinfo-uptime");
    if (upEl) upEl.textContent = formatUptime(status.uptime_seconds);

    return status;
  } catch (e) {
    console.error("[settings] failed to load status:", e);
    // EVERY dot, not just the server's. The CLI and Fish dots are drawn from
    // fields of the answer that never arrived, so leaving them green states
    // as fact something this call failed to find out. "off" is the absence
    // of a reading, which is what we have.
    setDotStatus("status-server", "red");
    setDotStatus("status-claude-cli", "off");
    setDotStatus("status-fish", "off");
    const serverDetail = document.getElementById("status-server-detail");
    if (serverDetail) serverDetail.textContent = L("no answer from the server", "伺服器沒有回應");
    for (const id of ["sysinfo-port", "sysinfo-uptime"]) {
      const node = document.getElementById(id);
      if (node) node.textContent = "—";
    }
    return null;
  }
}

async function loadPreferences() {
  try {
    const prefs = await apiGet<PreferencesResponse>("/api/settings/preferences");
    const nameEl = document.getElementById("input-user-name") as HTMLInputElement;
    const honEl = document.getElementById("input-honorific") as HTMLSelectElement;
    if (nameEl) nameEl.value = prefs.user_name || "";
    if (honEl) honEl.value = prefs.honorific || "sir";
    const langEl = document.getElementById("input-language") as HTMLSelectElement;
    const voiceEl = document.getElementById("input-voice") as HTMLSelectElement;
    const bvEl = document.getElementById("input-browser-voice") as HTMLInputElement;
    if (langEl) langEl.value = prefs.language === "zh-TW" ? "zh-TW" : "en";
    if (voiceEl) voiceEl.value = ["auto", "fish", "browser"].includes(prefs.voice || "") ? prefs.voice! : "auto";
    if (bvEl) bvEl.value = prefs.browser_voice || "";
  } catch (e) {
    console.error("[settings] failed to load preferences:", e);
  }
}

function wireEvents() {
  // Close
  document.getElementById("settings-close")?.addEventListener("click", closeSettings);
  document.getElementById("settings-backdrop")?.addEventListener("click", closeSettings);

  // Save keys
  document.getElementById("btn-save-keys")?.addEventListener("click", async () => {
    const fishKey = (document.getElementById("input-fish-key") as HTMLInputElement).value.trim();

    let savedAny = false;
    if (fishKey) {
      await apiPost("/api/settings/keys", { key_name: "FISH_API_KEY", key_value: fishKey });
      savedAny = true;
    }
    await loadStatus();

    const notice = document.getElementById("keys-restart-notice");
    if (notice) notice.style.display = savedAny ? "block" : "none";
  });

  // Save voice ID
  document.getElementById("btn-save-voice-id")?.addEventListener("click", async () => {
    const voiceId = (document.getElementById("input-fish-voice-id") as HTMLInputElement).value.trim();
    if (voiceId) {
      await apiPost("/api/settings/keys", { key_name: "FISH_VOICE_ID", key_value: voiceId });
    }
  });

  // Test Fish
  document.getElementById("btn-test-fish")?.addEventListener("click", async () => {
    setDotStatus("status-fish", "yellow");
    const key = (document.getElementById("input-fish-key") as HTMLInputElement).value.trim();
    try {
      const result = await apiPost<{ valid: boolean; error?: string }>("/api/settings/test-fish", { key_value: key || undefined });
      setDotStatus("status-fish", result.valid ? "green" : "red");
    } catch {
      setDotStatus("status-fish", "red");
    }
  });

  // Save preferences — the name and the language/voice choices together, so
  // saving one never blanks the other.
  document.getElementById("btn-save-prefs")?.addEventListener("click", async () => {
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement).value.trim();
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement).value;
    const language = (document.getElementById("input-language") as HTMLSelectElement).value;
    const voice = (document.getElementById("input-voice") as HTMLSelectElement).value;
    const browser_voice = (document.getElementById("input-browser-voice") as HTMLInputElement).value.trim();
    const result = await apiPost<{ success: boolean; error?: string }>(
      "/api/settings/preferences", { user_name, honorific, language, voice, browser_voice });
    const notice = document.getElementById("prefs-restart-notice");
    if (notice) {
      notice.style.display = "block";
      if (!result.success) notice.textContent = result.error || L("Could not save.", "儲存失敗。");
    }
    await loadStatus();
  });

  // Hear the browser's voice without waiting for JARVIS to say something.
  document.getElementById("btn-test-voice")?.addEventListener("click", () => {
    sampleVoice?.(L("Good evening, sir. All systems are online.", "晚上好，先生。所有系統都已上線。"));
  });

  // Setup next button
  document.getElementById("btn-setup-next")?.addEventListener("click", advanceSetup);
}

// ---------------------------------------------------------------------------
// First-time setup wizard
// ---------------------------------------------------------------------------

function enterSetupMode() {
  isFirstTimeSetup = true;
  setupStep = 0;

  const welcome = document.getElementById("settings-welcome");
  if (welcome) welcome.style.display = "block";

  const nav = document.getElementById("setup-nav");
  if (nav) nav.style.display = "flex";

  // Hide sections except API keys
  showSetupStep(0);
}

function showSetupStep(step: number) {
  const sections = ["section-api-keys", "section-preferences"];
  const voiceSection = document.getElementById("section-voice");
  if (voiceSection) voiceSection.style.display = step === 0 ? "" : "none";
  sections.forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (step === 0 && i === 0) el.style.display = "";
    else if (step === 1 && i === 1) el.style.display = "";
    else el.style.display = "none";
  });

  const nextBtn = document.getElementById("btn-setup-next");
  if (nextBtn) {
    if (step === 0) nextBtn.textContent = L("Next: Set Your Name", "下一步：設定名字");
    else if (step === 1) nextBtn.textContent = L("Finish Setup", "完成設定");
    else nextBtn.style.display = "none";
  }
}

async function advanceSetup() {
  setupStep++;
  if (setupStep >= 2) {
    // Done — save everything and close
    isFirstTimeSetup = false;
    const welcome = document.getElementById("settings-welcome");
    if (welcome) welcome.style.display = "none";
    const nav = document.getElementById("setup-nav");
    if (nav) nav.style.display = "none";

    // Show all sections
    ["section-voice", "section-api-keys", "section-status", "section-preferences", "section-sysinfo"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.style.display = "";
    });

    closeSettings();
    return;
  }
  showSetupStep(setupStep);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function openSettings() {
  if (isOpen) return;
  isOpen = true;

  if (!panelEl) {
    panelEl = createPanel();
    wireEvents();
  }

  panelEl.style.display = "block";

  // Trigger animation
  requestAnimationFrame(() => {
    panelEl!.classList.add("open");
  });

  // Load data
  const status = await loadStatus();
  await loadPreferences();

  // Check for first-time setup
  if (status && needsSetup(status)) {
    enterSetupMode();
  }
}

export function closeSettings() {
  if (!panelEl || !isOpen) return;
  isOpen = false;
  panelEl.classList.remove("open");
  setTimeout(() => {
    if (panelEl) panelEl.style.display = "none";
  }, 300);
}

export function isSettingsOpen(): boolean {
  return isOpen;
}

/**
 * Check if first-time setup is needed and auto-open.
 */
export async function checkFirstTimeSetup(): Promise<boolean> {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");
    if (needsSetup(status)) {
      openSettings();
      return true;
    }
  } catch {
    // Server not ready yet, skip
  }
  return false;
}
