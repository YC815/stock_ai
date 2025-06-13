# 1. 使用官方 Python 映像作為基礎
# 我們使用 slim 版本，因為它的體積更小
FROM python:3.13.3-slim

# 2. 設定工作目錄
# 容器內的所有後續操作都會在這個目錄下進行
WORKDIR /app

# 3. 安裝依賴
# 首先只複  製 requirements.txt 來利用 Docker 的層快取機制
# 只有當 requirements.txt 改變時，才會重新執行 pip install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 複製應用程式原始碼
# 將專案中的所有檔案複製到工作目錄中
COPY . .

# 5. 設定預設執行指令
# 當容器啟動時，會執行這個指令
# 這裡我們使用 Gunicorn 來啟動 Flask 應用程式
# Zeabur 會自動注入 PORT 環境變數
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"] 