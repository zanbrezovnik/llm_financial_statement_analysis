"""
Configuration settings for the chatbot application.
"""

# Gemini model for all API calls
MODEL_NAME = "gemini-2.5-pro-preview-05-06"

# Tables to look for during extraction
TARGET_TABLES = [
    "CONSOLIDATED STATEMENTS OF CASH FLOWS",
    "CONSOLIDATED STATEMENTS OF OPERATIONS",
    "CONSOLIDATED BALANCE SHEETS"
]

# Examplary preset questions for the chatbot
PRESET_FINANCIAL_QUESTIONS = {
    "Liability Overview": [
        "What are the company's total liabilities, how are they broken down by maturity and type, and what interest rates apply?"
    ],
    "Debt Characteristics": [
        "How are the company's debt instruments (short-term and long-term) structured, and what is their exposure to floating rates?"
    ],
    "Lease Obligations": [
        "What are the company's lease liabilities, both current and non-current, and how are they structured?"
    ],
    "Interest Rate Risk Hedging": [
        "Is the company exposed to interest rate risk, and does it use derivatives to manage this exposure? If so, specify the instruments, notional amounts, and their purpose."
    ],
    "Currency Risk Hedging": [
        "Does the company hedge foreign exchange risk using derivatives? Provide details on the instruments used, currencies involved and maturities."
    ]
}

# Default folder names
PDF_FOLDER = "fin_statements"
EXCEL_OUTPUT_FOLDER = "output/excel_reports"
LOG_OUTPUT_FOLDER = "output/logs_and_transcripts"
API_KEY_FILE = "api_key.txt" 