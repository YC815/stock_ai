import pandas as pd
import logging
import os

# --- Configuration ---
SOURCE_FILE = 'yfinance_data.csv'
CLEANED_FILE = 'data_processing/yfinance_data_cleaned.csv'
LOG_FILE = 'data_processing/data_processing.log'

# Define the columns we want to keep. This simplifies the dataset.
# We choose a mix of identifiers, classification, key metrics, and financial data.
COLUMNS_TO_KEEP = [
    # Identifiers
    'ticker', 'longName', 'shortName', 'quoteType', 'exchange',
    # Classification
    'sector', 'industry', 'country',
    # Key Financials & Ratios
    'marketCap', 'enterpriseValue', 'trailingPE', 'forwardPE', 'trailingEps', 'forwardEps',
    'priceToSalesTrailing12Months', 'priceToBook', 'dividendYield', 'dividendRate',
    'payoutRatio', 'beta',
    # Price & Volume
    'regularMarketPrice', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'fiftyDayAverage',
    'twoHundredDayAverage', 'averageVolume', 'volume',
    # Financial Health
    'totalDebt', 'totalCash', 'quickRatio', 'currentRatio', 'debtToEquity',
    # Income Statement Highlights
    'totalRevenue', 'grossProfits', 'ebitda', 'netIncomeToCommon', 'revenueGrowth',
    # Important Dates (will be converted from timestamps)
    'lastFiscalYearEnd', 'nextFiscalYearEnd', 'mostRecentQuarter', 'exDividendDate',
    'earningsTimestamp', 'fundInceptionDate',
    # Summary
    'longBusinessSummary'
]

# Configure logging
# Placed inside a function to avoid running on import


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )


def convert_timestamp_to_date(series):
    """Safely converts a series of UNIX timestamps to readable dates, handling errors."""
    return pd.to_datetime(series, unit='s', errors='coerce').dt.date


def process_data(source_path, dest_path):
    """
    Loads raw data, cleans it, selects columns, and saves the result.
    """
    if not os.path.exists(source_path):
        logging.error(f"Source file not found: {source_path}")
        return

    logging.info(f"Loading raw data from {source_path}...")
    # Handle potential parsing errors in the large CSV file
    try:
        df = pd.read_csv(source_path)
    except pd.errors.ParserError as e:
        logging.error(f"Failed to parse CSV file: {e}")
        return

    logging.info(f"Loaded {len(df)} rows and {len(df.columns)} columns.")

    # Identify which of our desired columns are actually in the raw data
    available_columns = [col for col in COLUMNS_TO_KEEP if col in df.columns]
    missing_columns = [col for col in COLUMNS_TO_KEEP if col not in df.columns]
    if missing_columns:
        logging.warning(f"The following desired columns were not found in the source file: {missing_columns}")

    logging.info(f"Selecting {len(available_columns)} available columns...")
    df_cleaned = df[available_columns].copy()

    # --- Data Type Conversion and Cleaning ---
    logging.info("Converting timestamp columns to dates...")
    date_columns = [
        'lastFiscalYearEnd', 'nextFiscalYearEnd', 'mostRecentQuarter', 'exDividendDate',
        'earningsTimestamp', 'fundInceptionDate'
    ]
    for col in date_columns:
        if col in df_cleaned.columns:
            df_cleaned[col] = convert_timestamp_to_date(df_cleaned[col])

    logging.info("Ensuring numerical columns are of a numeric type...")
    # A more robust way to select columns to convert to numeric
    numeric_cols = [
        'marketCap', 'enterpriseValue', 'trailingPE', 'forwardPE', 'trailingEps', 'forwardEps',
        'priceToSalesTrailing12Months', 'priceToBook', 'dividendYield', 'dividendRate',
        'payoutRatio', 'beta', 'regularMarketPrice', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
        'fiftyDayAverage', 'twoHundredDayAverage', 'averageVolume', 'volume', 'totalDebt',
        'totalCash', 'quickRatio', 'currentRatio', 'debtToEquity', 'totalRevenue',
        'grossProfits', 'ebitda', 'netIncomeToCommon', 'revenueGrowth'
    ]

    for col in numeric_cols:
        if col in df_cleaned.columns:
            df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')

    # Reorder columns to match the COLUMNS_TO_KEEP list for consistency
    df_cleaned = df_cleaned[available_columns]

    logging.info(f"Saving cleaned data with {len(df_cleaned)} rows and {len(df_cleaned.columns)} columns to {dest_path}...")
    df_cleaned.to_csv(dest_path, index=False)
    logging.info("Data processing complete.")

    print("\n--- Cleaned Data Sample ---")
    print(df_cleaned.head())
    print("\n--- Cleaned Data Info ---")
    df_cleaned.info(verbose=False, show_counts=True)


if __name__ == "__main__":
    setup_logging()
    process_data(SOURCE_FILE, CLEANED_FILE)
