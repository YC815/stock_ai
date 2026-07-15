"""
This script fetches historical stock data from Yahoo Finance and stores it in a MySQL database.

It downloads data for all tickers from S&P 500, Dow Jones, NASDAQ, and selected ETFs.
The script supports incremental updates to avoid re-downloading existing data.
Each ticker's data is saved in a separate table in the database.
"""
import logging
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tqdm import tqdm
from yahoo_fin import stock_info as si

# --- New Imports for Caching and Rate Limiting ---
from requests import Session
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterMixin, MemoryQueueBucket
from pyrate_limiter import Duration, RequestRate, Limiter

# --- Session Class for Rate-Limited, Cached API calls ---


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    """
    A custom session class that combines caching and rate-limiting
    for robust API interactions.
    """
    pass


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
    Fetches a list of tickers from yahoo_fin for US stocks.
    Applies filtering to remove obviously invalid ticker symbols.
    """
    logging.info("Fetching list of all tickers from yahoo_fin...")
    tickers = []
    try:
        # These lists can contain invalid symbols like 'BRK.B' or 'BF.B' which yfinance handles,
        # but also junk like '-', '---', etc. which we need to filter out.
        tickers.extend(si.tickers_sp500(include_company_data=False))
        tickers.extend(si.tickers_dow(include_company_data=False))
        tickers.extend(si.tickers_nasdaq(include_company_data=False))
    except Exception as e:
        logging.error("Failed to fetch tickers for S&P 500, Dow, or NASDAQ: %s", e)

    try:
        # tickers_etfs often fails or returns an empty list, so we handle it gracefully.
        tickers.extend(si.tickers_etfs(include_company_data=False))
    except Exception:
        logging.warning("si.tickers_etfs() is unavailable or returned no data, skipping ETFs.")

    if not tickers:
        logging.error("Could not fetch any tickers. Exiting.")
        return []

    # Use a set to get unique tickers
    unique_tickers = sorted(list(set(tickers)))

    # Filter for valid ticker formats
    # - Must contain at least one letter.
    # - Can contain letters, numbers, '-', and '.'
    # - Filters out symbols that are only punctuation (e.g., '-', '---').
    # - Limits length to a reasonable number for a ticker symbol.
    valid_tickers = [
        t for t in unique_tickers
        if re.search(r"[A-Z]", t) and re.match(r"^[A-Z0-9-.]+$", t) and 1 <= len(t) <= 10
    ]

    logging.info("Found %d unique, valid tickers for DB.", len(valid_tickers))
    return valid_tickers


@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    with open(os.devnull, 'w') as fnull:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = fnull, fnull
        try:
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


def process_ticker(ticker, engine, session):
    """
    Processes a single ticker: fetches new data and appends it to the database.
    This function is designed to be run in a separate thread.
    """
    table_name = ticker.replace('.', '_').replace('-', '_')
    start_date = "1950-01-01"

    try:
        with engine.connect() as connection:
            if connection.dialect.has_table(connection, table_name):
                query = text(f"SELECT MAX(Date) FROM `{table_name}`")
                result = connection.execute(query).scalar()
                if pd.notna(result):
                    last_date = pd.to_datetime(result).date()
                    start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')

        # Create the Ticker object, passing the session to its constructor
        t_obj = yf.Ticker(ticker, session=session)

        # .history() will use the session from the Ticker object
        df_new = t_obj.history(start=start_date, auto_adjust=True)

        if df_new.empty:
            # A quick check to see if the ticker is valid at all.
            # This .info call will also use the session from the Ticker object.
            # The 'info' property is lazily loaded and will trigger a network call.
            # A common reason for an empty 'info' dict is that the ticker is invalid.
            if not t_obj.info:
                return f"[{ticker}] 處理失敗：可能是已下市或無效的股票代碼。"
            return f"[{ticker}] 沒有需要更新的資料。"

        df_new.reset_index(inplace=True)
        df_new['Date'] = pd.to_datetime(df_new['Date']).dt.date

        # Ensure correct data types for DB
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df_new.columns:
                df_new[col] = pd.to_numeric(df_new[col])

        # Write to database
        df_new.to_sql(table_name, con=engine, if_exists='append', index=False, chunksize=1000)
        return f"[{ticker}] 成功儲存/更新 {len(df_new)} 筆記錄。"

    except Exception as e:
        error_str = str(e)
        # Check for common, non-critical errors that indicate an invalid ticker
        if "No timezone found" in error_str or "delisted" in error_str or "Failed to get ticker" in error_str:
            return f"[{ticker}] 處理失敗：可能是已下市或無效的股票代碼。"
        else:
            # Log unexpected errors to the file for debugging, but return a user-friendly message
            logging.error("[%s] 發生未預期的錯誤: %s", ticker, error_str)
            return f"[{ticker}] 處理失敗，錯誤已記錄。"


def fetch_historical_data(engine, ticker_list, session):
    """
    Concurrently fetches historical market data for a list of tickers.
    """
    logging.info("開始併發下載 %d 支股票的歷史資料...", len(ticker_list))

    # Use a ThreadPoolExecutor to fetch data in parallel
    # NOTE: A high number of workers (e.g., 10+) can quickly exhaust the API rate limit,
    # causing the process to pause. A lower number like 2 is safer and prevents stalling.
    with ThreadPoolExecutor(max_workers=16) as executor:
        # Create a future for each ticker, passing the session along
        future_to_ticker = {executor.submit(process_ticker, ticker, engine, session): ticker for ticker in ticker_list}

        # Process futures as they complete
        for future in tqdm(as_completed(future_to_ticker), total=len(ticker_list), desc="正在抓取歷史資料"):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                # Log only successes or common, translatable warnings.
                if "成功" in result or "沒有需要更新" in result:
                    logging.info(result)
                else:  # Log other failures as warnings.
                    logging.warning(result)
            except Exception as e:
                logging.error(f"處理股票 {ticker} 時發生嚴重錯誤: {e}")


def run_data_collection():
    """主執行函式，用於抓取和存儲股票數據。"""
    setup_logging()
    db_engine = get_db_engine()

    if db_engine:
        # --- Setup a Cached and Rate-Limited Session ---
        # Limits based on Yahoo's public recommendations:
        # 2,000 requests per hour per IP -> ~33/minute
        # We'll be conservative at 25 per minute.
        session = CachedLimiterSession(
            limiter=Limiter(RequestRate(25, Duration.MINUTE)),
            bucket_class=MemoryQueueBucket,
            backend=SQLiteCache("yfinance.cache"),
        )

        # --- 測試模式開關 ---
        # 透過環境變數 `TEST_MODE=true` 來啟用測試模式
        # 預設為 False (完整模式)
        TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
        test_tickers = ['AAPL', 'GOOGL', 'TSLA', 'BRK-B']  # 用於測試的股票列表 (BRK.B -> BRK-B)

        if TEST_MODE:
            logging.info("--- 運行於測試模式 ---")
            tickers_to_fetch = test_tickers
        else:
            logging.info("--- 運行於完整模式 ---")
            tickers_to_fetch = fetch_all_tickers()

        if tickers_to_fetch:
            fetch_historical_data(db_engine, tickers_to_fetch, session)
            logging.info("歷史數據抓取流程完成。")
        else:
            logging.warning("沒有找到任何股票代碼，腳本終止。")
    else:
        logging.error("無法建立資料庫引擎，腳本終止。")


if __name__ == "__main__":
    run_data_collection()
