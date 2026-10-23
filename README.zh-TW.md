# JARVIS 中文版：像鋼鐵人一樣用說的操控電腦

> 這是 [ethanplusai/jarvis](https://github.com/ethanplusai/jarvis) 的分支（fork），
> 加上了**中文對話**、**免費語音**和**一鍵安裝／啟動**。原版的英文說明在
> [README.md](README.md)。

你對著電腦說話，JARVIS 用聲音回答你。他的「大腦」是你已經在用的 **Claude Code**
（跑在你的 Claude 訂閱上，不需要 API 金鑰），所以他不只會聊天，還會真的動手做事：

- **幫你寫程式**：跟你一問一答把需求討論清楚，把設計寫成文件，再開一個真正的
  Claude Code 工作去規劃、檢查、實作、測試。
- **盯著你所有的 Claude Code 對話**：哪個在等你按權限、哪個做完了，他會直接說出來。
- **幫你按鍵、傳話**：替 Terminal 裡的對話按 Enter／Esc／選項，或把你的指示傳給它。
- **開網頁、開終端機、看你的螢幕、上網查資料、記住你的習慣**。
- **儀表板**：所有工作、對話、記憶、用量一目了然。

> 「好的，先生。」

---

## 這個版本多了什麼

| | 原版 | 這個版本 |
|---|---|---|
| 對話語言 | 只有英文 | **繁體中文（台灣）**，也能切回英文 |
| 聲音 | 一定要付費的 Fish Audio 金鑰，沒有就完全無聲 | **沒有金鑰也能說話**：改用 Chrome 內建語音（免費）；有金鑰就用電影版 JARVIS 聲音 |
| 安裝 | 照著說明一步步打指令 | `./scripts/setup.sh` 一次裝好，`./scripts/start.sh` 一次啟動 |
| 設定頁 | 英文 | 中文介面，可直接切換語言與語音 |

---

## 你需要準備

| 項目 | 說明 |
|---|---|
| **Mac（macOS）** | 控制終端機、截圖、系統通知都靠 AppleScript，只有 Mac 才有 |
| **Google Chrome** | 麥克風語音辨識只能在 Chrome 用（Safari、Firefox 都不行） |
| **Claude 訂閱（Pro 或 Max）** | JARVIS 的大腦用的是你的訂閱額度，不另外收費 |
| **Claude Code 2.1.224 以上** | 安裝方式見下方 |
| **Python 3.11 以上、Node.js 18 以上** | 用 Homebrew 安裝最簡單 |
| Fish Audio API 金鑰（**選配**） | 想要電影裡那個 JARVIS 聲音才需要（付費，[fish.audio](https://fish.audio)） |

---

## 安裝（第一次，大約 10 分鐘）

打開 Mac 的「終端機」（Terminal），依序貼上：

**1. 安裝 Homebrew、Python、Node.js**（已經有的可以跳過）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.12 node
```

**2. 安裝並登入 Claude Code**

```bash
npm install -g @anthropic-ai/claude-code
claude
```

第一次執行 `claude` 會帶你登入 Claude 帳號，登入完輸入 `/exit` 離開即可。

**3. 下載這個專案**

```bash
git clone https://github.com/shiannji/Jarvis.git jarvis
cd jarvis
```

**4. 一鍵安裝**

```bash
./scripts/setup.sh
```

它會檢查工具版本、安裝所有套件、產生本機憑證，並問你三個問題：

1. 對話語言（直接按 Enter＝繁體中文）
2. 你的名字（可略過）
3. Fish Audio 金鑰（**直接按 Enter 略過＝使用免費的瀏覽器語音**）

最後會跑一次環境檢查，告訴你還有什麼要處理。這個指令可以重複執行，已經做好的會跳過。

---

## 啟動

```bash
./scripts/start.sh
```

或是在 Finder 裡**按兩下 `JARVIS.command`**（第一次會先自動安裝）。

它會同時啟動後端與前端，並用 Chrome 打開 **http://localhost:5173**。接著：

1. Chrome 問你是否允許使用麥克風 → **允許**
2. **在畫面上點一下**（Chrome 規定要先點過頁面才能出聲）
3. 聽到「早安，先生。」就可以開口說話了

要關掉時，在終端機按 **Ctrl + C**。儀表板在 http://localhost:5173/dashboard.html 。

---

## 第一次使用：macOS 權限

某些功能需要你在「系統設定 → 隱私權與安全性」裡授權給**終端機（Terminal）**
（是啟動 JARVIS 的那個 App，不是 python）：

| 權限 | 用途 | 沒開會怎樣 |
|---|---|---|
| **輔助使用** | 替 Terminal 裡的 Claude Code 對話按 Enter／Esc／選項 | 他會說沒有權限，其他功能不受影響 |
| **螢幕與系統錄音** | 「看我的螢幕」 | 他看不到你的畫面 |

授權後要**重新啟動 JARVIS** 才會生效。

另外，如果你想讓 JARVIS 把訊息直接傳進其他 Claude Code 對話（而不是每次都要你核准），
他第一次傳話時會問你要不要開啟——說「好」就行。

---

## 跟 JARVIS 說什麼？

直接用平常說話的方式就可以，下面是一些例子：

**看看大家在忙什麼**
- 「現在有哪些對話在等我？」
- 「hammer 那個對話做到哪裡了？」
- 「我有哪些專案？」

**指揮其他 Claude Code 對話**
- 「跟 hammer 說：資料庫用 Postgres 就好。」
- 「幫 hammer 按 Enter。」／「幫它選第一個。」

**開新工作、做專案**
- 「幫我建立一個叫 todo-app 的新專案。」
- 「在 todo-app 裡做一個待辦清單網頁，用 React。」
- 「我想做一個記帳 App，我們先討論一下。」（他會一題一題問你，討論完寫成設計文件，再開始建置）
- 「建置進度到哪了？」／「把那個工作停掉。」

**看、查、開**
- 「打開 todo-app 的網頁。」／「在終端機打開 todo-app。」
- 「todo-app 的登入是寫在哪裡？」（直接讀程式碼回答，不必另開工作）
- 「我螢幕上現在開著什麼？」
- 「幫我查一下 Vite 最新版本是多少。」

**記憶與用量**
- 「記住：我寫程式習慣用 TypeScript。」
- 「我還剩多少用量？」
- 「你現在連接了哪些服務？」

**控制對話本身**

| 你說 | 效果 |
|---|---|
| 「再說一次」「你剛剛說什麼」「蛤？」 | 重播他上一句話（不花用量） |
| 「重新開始」「清空對話」 | 丟掉目前的對話內容，從頭來過 |
| 「等一下」「停」「取消」 | 打斷他，或在他複誦指令時取消 |
| 按鍵盤 **Esc** 或畫面上的「停止」 | 立刻讓他閉嘴（最可靠） |

他有時會把專案名稱、模型名稱（Opus、Sonnet）保留英文，這是正常的。

---

## 聲音設定

在畫面右上角「⋮ → 設定 → 語言與聲音」可以切換（改完要「重新啟動伺服器」）：

| 語音引擎 | 說明 |
|---|---|
| **自動（建議）** | 有 Fish Audio 金鑰就用電影版聲音，沒有就用瀏覽器語音；Fish 偶爾失敗的句子也會改用瀏覽器語音補上 |
| 只用 Fish Audio | 原版做法：沒有金鑰或連線失敗時只顯示文字 |
| 只用瀏覽器語音 | 完全免費，永遠不呼叫 Fish Audio |

**讓免費語音更好聽**：macOS 內建的中文語音可以下載高品質版本。
到「系統設定 → 輔助使用 → 朗讀內容 → 系統語音 → 管理語音…」，在「中文（台灣）」
下載「美佳」的加強／高品質版本等語音，重新整理 JARVIS 的網頁即可。想指定某個語音，在設定頁
「瀏覽器語音名稱」填入名稱的一部分（例如 `Meijia`），或在 `.env` 設定
`JARVIS_BROWSER_VOICE=Meijia`，按「試聽」確認效果。

**使用 Fish Audio（電影版聲音）**：到 [fish.audio](https://fish.audio) 註冊並建立 API
金鑰，在設定頁「API 金鑰」貼上並儲存，再重新啟動伺服器。預設的聲音模型是英文的
JARVIS，讓它說中文時音色相同但口音會比較「外國人」；喜歡的話也可以在 Fish Audio
上找一個中文聲音模型，把它的 ID 填到「Fish Voice ID」。

---

## 常見問題

**麥克風沒反應**
1. 確認用的是 **Google Chrome**。
2. 確認網址是 **http://localhost:5173**——Chrome 的麥克風權限連「連接埠」一起記，
   換成 5174 就等於沒授權，而且不會再問你。
3. 到 `chrome://settings/content/microphone` 確認 `http://localhost:5173` 是「允許」。
4. 畫面左下角的細線會隨聲音跳動：有跳就代表麥克風有收到聲音。

**他說「語言系統停擺了」**
通常是 Claude Code 的登入過期了。在終端機執行 `claude` 重新登入，再重新啟動 JARVIS。
詳細原因在 `data/server.log`。也可以跑 `.venv/bin/python scripts/doctor.py` 做檢查。

**沒有聲音**
先在畫面上點一下（Chrome 規定）；再到設定頁按「試聽」；也確認系統音量沒有關。

**他一直被自己的聲音打斷**
用耳機最有效；或在 `.env` 加上 `JARVIS_MUTE_MIC_DURING_SPEECH=true`（他說話時暫停收音）。

**「8340／5173 埠已被占用」**
JARVIS 可能已經在跑了；先把舊的視窗按 Ctrl + C 關掉再啟動。

**想改回英文**
設定頁 → 對話語言 → English → 儲存 → 重新啟動伺服器。或在 `.env` 改成
`JARVIS_LANGUAGE=en`。

**要花多少錢？**
大腦用的是你的 Claude 訂閱（會用掉訂閱的 5 小時／7 天額度，可以在儀表板的 Usage
看剩多少），不會另外收 API 費用。Fish Audio 是選配。

---

## 安全須知（請先讀）

JARVIS 是你本機上一個權力很大的程式，原作者刻意做了這些取捨：

- 他開的每個 Claude Code 工作都帶著 `--dangerously-skip-permissions`（因為語音介面
  沒辦法替它按權限），等於能在你指定的資料夾做任何你能做的事。
- 伺服器預設只聽本機（127.0.0.1），不要隨便改成 `0.0.0.0` 對外開放。
- 他從網頁、檔案、其他對話讀到的內容一律視為「不可信」：讀過這些內容的那一輪，
  他不會執行任何動作，要你重新用自己的話下指令。

詳細說明見 [README.md 的 What this trusts, and why](README.md#what-this-trusts-and-why)。

---

## 進階

- **設定檔**：`.env`（從 `.env.example` 複製而來，裡面每個設定都有中英文註解）。
- **他的個性**：`data/jarvis/CLAUDE.md`（第一次啟動時從 `jarvis_home/CLAUDE.md` 複製）。
- **連接其他服務**（Notion、Linear…）：把 MCP 伺服器設定貼進
  `data/jarvis/connections.json`，重新啟動後問他「你現在連接了哪些服務？」。
- **專案放在哪**：新專案預設建在 `~/Projects`，他也會看 `~/Desktop` 裡的資料夾。
- **跑測試**：`.venv/bin/pytest`（不會用到網路，也不會真的啟動 `claude`）。
- **同步原作者的更新**：
  ```bash
  git remote add upstream https://github.com/ethanplusai/jarvis.git
  git fetch upstream
  git merge upstream/main
  ```

---

## 授權

原作者 Ethan Rogers 的授權條款（見 [LICENSE](LICENSE)）：**個人、非商業使用免費**；
任何商業用途（販售、付費服務、SaaS 等）都需要另外取得授權。

> 這是獨立的粉絲專案，與 Marvel、迪士尼無關。JARVIS 名稱與角色屬於 Marvel Entertainment。
