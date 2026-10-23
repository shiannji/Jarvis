/**
 * The words on the voice page, in the language JARVIS is speaking.
 *
 * The server decides the language (`JARVIS_LANGUAGE`, see i18n.py) and says
 * so in the `/ws/voice` config frame; until that frame arrives the page uses
 * whatever it was told last time, so a reload does not flash English first.
 */

export type Lang = "en-US" | "zh-TW";

const STORAGE_KEY = "jarvis.lang";

function remembered(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "zh-TW" ? "zh-TW" : "en-US";
  } catch {
    return "en-US"; // storage blocked: English until the server says otherwise
  }
}

let current: Lang = remembered();

export function lang(): Lang {
  return current;
}

export function isZh(): boolean {
  return current === "zh-TW";
}

/** Adopt the server's language. Returns true when it changed. */
export function setLang(next: string): boolean {
  const value: Lang = next === "zh-TW" ? "zh-TW" : "en-US";
  if (value === current) return false;
  current = value;
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // a per-viewer convenience only; nothing depends on it
  }
  return true;
}

const STRINGS = {
  listening: ["listening...", "聆聽中…"],
  thinking: ["thinking...", "思考中…"],
  stop: ["Stop", "停止"],
  stopTitle: ["Stop speaking (Esc)", "停止說話（Esc）"],
  enableAudio: ["Click anywhere to enable audio", "請點一下畫面以啟用聲音"],
  settings: ["Settings", "設定"],
  restart: ["Restart Server", "重新啟動伺服器"],
  fixSelf: ["Fix Yourself", "自我修復"],
  restarting: ["restarting...", "重新啟動中…"],
  restartFailed: ["restart failed", "重新啟動失敗"],
  fixUnavailable: ["fix-yourself is not available in this build", "這個版本還不支援自我修復"],
  muteTitle: ["Mute/Unmute", "靜音／取消靜音"],
  menuTitle: ["Menu", "選單"],
  micLevel: ["microphone input", "麥克風音量"],
  micBlocked: ["Microphone blocked — retrying. Check this origin's mic permission.",
               "麥克風被封鎖——重試中。請檢查這個網址（含連接埠）的麥克風權限。"],
  micTaken: ["Another app has taken the microphone — quit it, then reload.",
             "麥克風被其他應用程式占用——請關掉它，再重新整理頁面。"],
  srNetwork: ["Speech recognition lost its connection — that sentence was dropped.",
              "語音辨識連線中斷——剛才那句沒有收到。"],
  srError: ["Speech recognition error: ", "語音辨識錯誤："],
  micStalled: ["Microphone stalled — restarting it.", "麥克風停住了——正在重新啟動。"],
  srUnsupported: ["Speech recognition not supported in this browser",
                  "這個瀏覽器不支援語音辨識，請改用 Google Chrome"],
  noBrowserVoice: ["This browser has no built-in voice — showing text instead.",
                   "這個瀏覽器沒有內建語音——改用文字顯示。"],
} as const;

export type StringKey = keyof typeof STRINGS;

export function t(key: StringKey): string {
  const pair = STRINGS[key];
  return isZh() ? pair[1] : pair[0];
}
