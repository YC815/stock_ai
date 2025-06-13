# Stock AI 專案

這個專案是一個由 Webhook 觸發的服務，會從 Yahoo Finance 抓取股票數據並存儲到您的資料庫中。

## 部署到 Zeabur

這個專案可以輕易地部署到 [Zeabur](https://zeabur.com) 上。

### 1. 準備你的專案

首先，確保您已經將您的專案推送到一個 GitHub repo。

### 2. 在 Zeabur 上建立專案

1.  登入您的 Zeabur 帳號。
2.  點擊 "Deploy New Service"，然後選擇 "Deploy from GitHub"。
3.  選擇您的 repo。Zeabur 會自動偵測到 `Dockerfile` 並將其部署為一個 Web 服務。

### 3. 設定環境變數

您的專案需要以下環境變數：

#### 資料庫連線

- `SQL_USERNAME`: 您的資料庫使用者名稱
- `SQL_PASSWORD`: 您的資料庫密碼
- `SQL_HOST`: 您的資料庫主機
- `SQL_PORT`: 您的資料庫連接埠
- `SQL_DATABASE`: 您的資料庫名稱

> 如果您還沒有資料庫，您可以在 Zeabur 上一鍵建立一個 MySQL 服務，然後將連線資訊填入這裡。

#### Webhook 安全驗證

- `WEBHOOK_TOKEN`: 一個您自訂的秘密 token，用於保護您的 Webhook 端點不被濫用。請設定一個複雜且不易猜測的字串。

### 4. 觸發資料抓取任務

部署完成後，您的服務會有一個公開的 URL，例如 `https://stock-ai.zeabur.internal`。

要觸發資料抓取任務，您需要向該服務的 `/webhook` 端點發送一個 `POST` 請求，並在 `Authorization` header 中帶上您的 token。

您可以使用 `curl` 或任何其他工具來發送此請求。

#### 使用 `curl` 的範例

請將 `<YOUR_SERVICE_URL>` 換成您在 Zeabur 上的服務 URL (例如 `https://stock-ai.zeabur.internal`)，並將 `<YOUR_WEBHOOK_TOKEN>` 換成您在環境變數中設定的 `WEBHOOK_TOKEN`。

```bash
curl -X POST <YOUR_SERVICE_URL>/webhook \
     -H "Authorization: Bearer <YOUR_WEBHOOK_TOKEN>"
```

**成功的回應 (202 Accepted):**

如果 token 正確且沒有其他任務正在執行，服務會立即回傳成功訊息，表示任務已在背景開始執行。

```json
{
  "status": "success",
  "message": "Task accepted and is running in the background."
}
```

**失敗的回應:**

- **401 Unauthorized**: 如果您的 token 錯誤或未提供。
- **429 Too Many Requests**: 如果前一個任務尚未完成，您就再次觸發。
