"""
This script fetches historical stock data from Yahoo Finance and stores it in a MySQL database.

It downloads data for all tickers from S&P 500, Dow Jones, NASDAQ, and selected ETFs.
The script supports incremental updates to avoid re-downloading existing data.
Each ticker's data is saved in a separate table in the database.
"""
import logging
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tqdm import tqdm
from yahoo_fin import stock_info as si

# --- Configuration ---
load_dotenv()  # 從 .env 文件加載環境變數

DB_USERNAME = os.getenv("SQL_USERNAME")
DB_PASSWORD = os.getenv("SQL_PASSWORD")
DB_HOST = os.getenv("SQL_HOST")
DB_PORT = os.getenv("SQL_PORT")
DB_NAME = os.getenv("SQL_DATABASE")

# 資料庫連接字串
DATABASE_URL = f"mysql+mysqlconnector://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_db_engine():
    """創建並返回一個 SQLAlchemy 資料庫引擎。"""
    try:
        engine = create_engine(DATABASE_URL)
        # 測試連接
        with engine.connect() as connection:
            logging.info("資料庫連接成功！")
        return engine
    except Exception as e:
        logging.error("無法連接到資料庫: %s", e)
        return None


def setup_logging():
    """Sets up logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[
            logging.FileHandler("get_data.log", mode='w'),
            logging.StreamHandler()
        ]
    )


def fetch_all_tickers():
    """
    Fetches a list of tickers from yahoo_fin for US stocks, indices, and ETFs.
    """
    logging.info("Fetching list of all tickers from yahoo_fin...")
    tickers = []
    try:
        tickers.extend(si.tickers_sp500())
        tickers.extend(si.tickers_dow())
        tickers.extend(si.tickers_nasdaq())
    except Exception as e:
        logging.error("Failed to fetch tickers for S&P 500, Dow, or NASDAQ: %s", e)

    try:
        tickers.extend(si.tickers_etfs())
    except AttributeError:
        logging.warning("si.tickers_etfs() is unavailable or deprecated, skipping ETFs.")
    except Exception as e:
        logging.error("Failed to fetch ETF tickers: %s", e)

    # Use a set to get unique tickers, then sort
    unique_tickers = sorted(list(set(tickers)))
    # Filter for valid ticker formats (usually uppercase letters, can contain '-' or '.')
    valid_tickers = [t for t in unique_tickers if re.search(r"^[A-Z-.]+$", t) and len(t) <= 64]  # MySQL table name length limit
    logging.info("Found %d unique, valid tickers for DB.", len(valid_tickers))
    return valid_tickers


def fetch_historical_data(engine, ticker_list):
    """
    為指定的 ticker 列表獲取歷史市場數據，並支援增量更新到資料庫。

    Args:
        engine: SQLAlchemy database engine.
        ticker_list (list): The list of stock tickers to fetch data for.
    """
    logging.info("Starting historical data fetch for %d tickers...", len(ticker_list))

    for ticker in tqdm(ticker_list, desc="Fetching Historical Data to DB"):
        table_name = ticker.replace('.', '_').replace('-', '_')  # Sanitize ticker for table name
        start_date = "1950-01-01"

        try:
            with engine.connect() as connection:
                if engine.dialect.has_table(connection, table_name):
                    query = text(f"SELECT MAX(Date) FROM `{table_name}`")
                    result = connection.execute(query).scalar()
                    if pd.notna(result):
                        last_date = result
                        if isinstance(last_date, str):
                            last_date = datetime.strptime(str(last_date), '%Y-%m-%d').date()
                        elif isinstance(last_date, datetime):
                            last_date = last_date.date()

                        start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                        logging.debug("[%s] Existing data found. Fetching new data from %s.", ticker, start_date)

            t_obj = yf.Ticker(ticker)
            df_new = t_obj.history(start=start_date, auto_adjust=True)

            if df_new.empty:
                logging.info("[%s] No new data available since %s.", ticker, start_date)
                continue

            df_new.reset_index(inplace=True)
            # Ensure correct data types for DB
            df_new['Date'] = pd.to_datetime(df_new['Date']).dt.date
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in df_new.columns:
                    df_new[col] = pd.to_numeric(df_new[col])

            # Write to database
            df_new.to_sql(table_name, con=engine, if_exists='append', index=False)
            logging.info("[%s] Saved/Appended %d records to table `%s`.", ticker, len(df_new), table_name)

        except Exception as e:
            logging.error("[%s] Failed to process ticker: %s", ticker, e)


if __name__ == "__main__":
    setup_logging()
    db_engine = get_db_engine()

    if db_engine:
        # --- 測試模式開關 ---
        # 設定為 True，只會抓取 test_tickers 列表中的股票
        # 設定為 False，會抓取所有找到的股票
        TEST_MODE = False
        test_tickers = ['AAPL', 'GOOGL', 'TSLA', 'BRK.B']  # 用於測試的股票列表

        if TEST_MODE:
            logging.info("--- 運行於測試模式 ---")
            tickers_to_fetch = test_tickers
        else:
            logging.info("--- 運行於完整模式 ---")
            tickers_to_fetch = fetch_all_tickers()

        if tickers_to_fetch:
            fetch_historical_data(db_engine, tickers_to_fetch)
            logging.info("歷史數據抓取流程完成。")
        else:
            logging.warning("沒有找到任何股票代碼，腳本終止。")
    else:
        logging.error("無法建立資料庫引擎，腳本終止。")
