# Stock AI 專案

這個專案會從 Yahoo Finance 抓取股票數據並存儲到你的資料庫中。

## 部署到 Zeabur

這個專案可以輕易地部署到 [Zeabur](https://zeabur.com) 上。

### 1. 準備你的專案

首先，確保你已經將你的專案推送到一個 GitHub repo。

### 2. 在 Zeabur 上建立專案

1.  登入你的 Zeabur 帳號。
2.  點擊 "Deploy New Service"，然後選擇 "Deploy from GitHub"。
3.  選擇你的 repo。Zeabur 會自動偵測到 `Dockerfile`。

### 3. 設定環境變數

你的 `get_data/get_data.py` 腳本需要資料庫的連線資訊。你需要在 Zeabur 的服務設定中設定這些環境變數：

- `SQL_USERNAME`: 你的資料庫使用者名稱
- `SQL_PASSWORD`: 你的資料庫密碼
- `SQL_HOST`: 你的資料庫主機
- `SQL_PORT`: 你的資料庫連接埠
- `SQL_DATABASE`: 你的資料庫名稱

如果你還沒有資料庫，你可以在 Zeabur 上建立一個 MySQL 服務，然後將連線資訊填入這裡。

### 4. 設定 Cron Job (定時任務)

Zeabur 讓你能夠為服務設定定時執行。要設定每 12 小時執行一次，請按照以下步驟：

1.  在你的服務頁面，找到 "Settings" 分頁。
2.  找到 "Cron Job" 的設定區塊。
3.  在輸入框中，填入 Cron 表達式。要每 12 小時執行一次，你可以使用 `0 */12 * * *`。
4.  儲存設定。

這樣設定之後，Zeabur 就會根據你設定的 Cron 表達式，每 12 小時建立一個新的容器來執行你的 `get_data/get_data.py` 腳本。

---

### Cron 表達式說明

`0 */12 * * *` 的意思是：

- `0`: 在每小時的第 0 分鐘。
- `*/12`: 每 12 小時。
- `*`: 每天。
- `*`: 每月。
- `*`: 每周的每一天。

這會讓你的腳本在 `00:00` 和 `12:00` (UTC 時間) 執行。
