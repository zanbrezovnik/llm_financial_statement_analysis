# Financial Report Extraction and Analysis Prototype

## Overview

This tool provides an end-to-end pipeline for extracting financial data from corporate annual reports (in PDF format), transforming it into structured Excel files, and enabling interactive querying via Google's Gemini API. It is designed to assist financial professionals in quickly navigating multi-year financial data without manual preprocessing.

## Key Features

-   **Interactive Setup**: A command-line interface guides you through selecting a company and analysis type.
-   **Multi-Year Analysis**: Load multiple annual reports (e.g., 2022, 2023, 2024) to ask comparative questions.
-   **Automated Table Extraction**: Automatically extracts key financial tables:
    -   Consolidated Balance Sheets
    -   Consolidated Statements of Operations
    -   Consolidated Statements of Cash Flows
-   **Formatted Excel Exports**: Exports extracted tables into a structured Excel file, with numbers cleaned and formatted for immediate use in calculations.
-   **AI-Powered Chat**: Interactively ask complex financial analysis questions about the loaded documents.
-   **Automated Reporting**: Generates `.docx` (Word) reports for chat session transcripts and detailed extraction logs.

## Requirements

-   Python 3.9+
-   A Google API Key with access to the Gemini API.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your_repo_url>
    cd <repository_directory>
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Add Your API Key:**
    -   Create a file named `api_key.txt` in the root directory of the project.
    -   Paste your Google API Key into this file and save it. The file should contain only the key itself.

5.  **Prepare PDF Documents:**
    -   Place your financial statement PDFs inside the `fin_statements` directory.
    -   Create a separate subdirectory for each company (e.g., `fin_statements/Amazon/`, `fin_statements/Walmart/`). The application will find these automatically.

## Usage Instructions

-   Simply run the application from the root directory:
    ```bash
    python3 chatbot_app.py
    ```
-   The command-line interface will guide you through the rest:
    1.  Choose a company.
    2.  Select Single-Year or Multi-Year analysis.
    3.  Choose whether to extract tables to Excel.
    4.  Choose whether to answer preset questions or start an interactive chat.

## Directory Structure
```
.
├── chatbot_app.py              # Main application entry point (CLI)
├── api_key.txt                 # Your Google Gemini API key
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── .gitignore                  
│
├── fin_statements/             # Folder for your source PDF reports
│   └── CompanyA/
│       └── report_2023.pdf
│
├── output/
│   ├── excel_reports/          # Auto-generated Excel files from extracted tables
│   └── logs_and_transcripts/   # Word documents for logs and chat transcripts
│
└── src/
    ├── config/
    │   └── settings.py         # App configuration (model name, preset questions)
    ├── llm_processing/
    │   └── gemini_service.py   # All Gemini API logic
    └── utils/
        ├── api_key_loader.py   # Loads the API key from the file
        ├── cli_utils.py        # Reusable CLI helper functions
        └── report_generator.py # Generates .docx reports
```

## Author

Zan Brezovnik
*Developed as part of a Bachelor's thesis project.* 