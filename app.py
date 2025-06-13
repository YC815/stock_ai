import logging
import os
import threading
from functools import wraps

from flask import Flask, jsonify, request
from get_data.get_data import run_data_collection

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration ---
# 從環境變數獲取 Webhook Token，如果未設定則使用一個預設值（建議在生產環境中設定）
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "default-secret-token")

# --- Logging Setup ---
# 讓日誌輸出到 console，方便在 Zeabur 後台查看
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")


# --- Decorators for Authentication ---
def require_token(f):
    """一個 decorator，用於驗證請求的 Authorization header 中是否有正確的 token。"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 從 Authorization header 獲取 token，格式應為 "Bearer <token>"
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logging.warning("Webhook: 缺少 Authorization header。")
            return jsonify({"error": "Missing authorization token"}), 401

        try:
            auth_type, token = auth_header.split()
            if auth_type.lower() != "bearer" or token != WEBHOOK_TOKEN:
                logging.warning("Webhook: 無效的 Token。")
                return jsonify({"error": "Invalid token"}), 401
        except ValueError:
            logging.warning("Webhook: Authorization header 格式錯誤。")
            return jsonify({"error": "Invalid authorization header format"}), 401

        return f(*args, **kwargs)

    return decorated_function


# --- Webhook Task Management ---
# 使用一個全域變數來追蹤任務是否正在執行，防止重複觸發
task_running = False
task_lock = threading.Lock()


def run_task_in_background():
    """在背景執行資料收集任務，並在完成後重設 flag。"""
    global task_running
    try:
        logging.info("開始執行背景資料抓取任務...")
        run_data_collection()
        logging.info("背景資料抓取任務完成。")
    except Exception as e:
        logging.error(f"背景任務執行失敗: {e}")
    finally:
        with task_lock:
            task_running = False


# --- Flask Routes ---
@app.route("/")
def index():
    """根目錄，用於健康檢查。"""
    return "Stock AI Webhook service is running."


@app.route("/webhook", methods=["POST"])
@require_token
def webhook_trigger():
    """
    Webhook 端點，用於觸發資料抓取任務。
    - 需要在 Header 中提供 'Authorization: Bearer <YOUR_TOKEN>'。
    - 如果已有任務在執行，會回傳 429 Too Many Requests。
    """
    global task_running
    with task_lock:
        if task_running:
            logging.warning("Webhook 觸發，但已有任務正在執行。")
            return jsonify({"status": "error", "message": "A task is already running. Please try again later."}), 429
        task_running = True

    # 在背景執行緒中啟動資料抓取任務
    thread = threading.Thread(target=run_task_in_background)
    thread.start()

    logging.info("Webhook 成功觸發，資料抓取任務已在背景開始。")
    return jsonify({"status": "success", "message": "Task accepted and is running in the background."}), 202


if __name__ == "__main__":
    # 使用 gunicorn 啟動時不會執行這裡的程式碼
    # 這只在直接用 `python app.py` 執行時用於本機測試
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
