"""
Main application file for the financial chatbot.
This script handles the entire user interaction flow: selecting a company
and financial documents, interacting with the AI, and saving the results.
"""
import os
import glob
import argparse
import logging
from datetime import datetime
import time
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import re

# Local imports
from src.utils.api_key_loader import load_api_key
from src.llm_processing.gemini_service import GeminiService
from src.utils.report_generator import generate_chat_transcript, generate_extraction_log
from src.config import settings
from src.utils.cli_utils import log_and_print, prompt_user
import google.generativeai as genai

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ask_preset_questions(gemini_service: GeminiService, uploaded_pdf_files_map: Dict[str, Any], chat_history: List[Tuple[str, str]]):
    """Runs through a list of preset questions and records the AI's answers."""
    if not uploaded_pdf_files_map:
        print("\nNo PDF documents loaded for context. Cannot answer preset questions.")
        logger.warning("Attempted to ask preset questions without PDF context.")
        return

    print("\n--- Answering Preset Financial Questions ---")
    logger.info("Starting to answer preset financial questions.")

    for category, questions in settings.PRESET_FINANCIAL_QUESTIONS.items():
        print(f"\n** {category} **")
        for i, question in enumerate(questions):
            print(f"\nPreset Question {i+1}: {question}")
            logger.info(f"Asking preset question: {question}")

            try:
                llm_response, error_message = gemini_service.generate_chat_response(
                    uploaded_pdf_files_map,
                    question
                )

                if llm_response:
                    print(f"\nChatbot: {llm_response}")
                    chat_history.append((f"Preset Question ({category} - {i+1}): {question}", f"Chatbot: {llm_response}"))
                else:
                    error_response = f"Sorry, I encountered an error processing this preset question. {error_message or ''}"
                    print(f"\nChatbot: {error_response}")
                    chat_history.append((f"Preset Question ({category} - {i+1}): {question}", f"Chatbot: {error_response}"))
            except Exception as e:
                logger.error(f"An unexpected error occurred while asking a preset question: {e}", exc_info=True)
                error_response = f"An unexpected critical error occurred: {e}"
                print(f"\nChatbot: {error_response}")
                chat_history.append((f"Preset Question ({category} - {i+1}): {question}", f"Chatbot: {error_response}"))
            
            time.sleep(1)  # Small delay to avoid hitting API rate limits too quickly.

    print("\n--- Finished Answering Preset Financial Questions ---")
    logger.info("Finished answering preset financial questions.")

def parse_arguments() -> argparse.Namespace:
    """Sets up and parses the command-line arguments."""
    parser = argparse.ArgumentParser(description="Interactive Financial Chatbot using Gemini API.")
    parser.add_argument("--pdf_folder", type=str, default=settings.PDF_FOLDER,
                        help="Base folder containing company subdirectories with PDF files.")
    parser.add_argument("--company", type=str, default=None,
                        help="Name of the company subdirectory. Bypasses interactive selection if provided.")
    parser.add_argument("--excel_output_folder", type=str, default=settings.EXCEL_OUTPUT_FOLDER,
                        help="Base folder to save extracted Excel files.")
    parser.add_argument("--log_output_folder", type=str, default=settings.LOG_OUTPUT_FOLDER,
                        help="Base folder to save Word chat transcripts and extraction logs.")
    parser.add_argument("--api_key_file", type=str, default=settings.API_KEY_FILE,
                        help="Path to the API key file.")
    return parser.parse_args()

def setup_company_paths(args: argparse.Namespace, company_name: str) -> Dict[str, str]:
    """Sets up all the company-specific output directories."""
    paths = {
        "pdf": os.path.join(args.pdf_folder, company_name),
        "log": os.path.join(args.log_output_folder, company_name),
        "excel": os.path.join(args.excel_output_folder, company_name)
    }
    os.makedirs(paths["log"], exist_ok=True)
    os.makedirs(paths["excel"], exist_ok=True)
    return paths

def select_company(pdf_folder: str) -> Optional[str]:
    """Lets the user select a company to analyze."""
    if not os.path.isdir(pdf_folder):
        log_and_print(f"Error: Base PDF folder '{pdf_folder}' not found.", level=logging.ERROR)
        return None

    available_companies = [d for d in os.listdir(pdf_folder) if os.path.isdir(os.path.join(pdf_folder, d))]
    
    if not available_companies:
        log_and_print(f"Warning: No company subdirectories found in '{pdf_folder}'.", level=logging.WARNING)
        return "Default_Session_NoCompany"

    company_options = {str(i+1): name for i, name in enumerate(available_companies)}
    company_options[str(len(available_companies) + 1)] = "Skip company selection (chat without specific PDF context)"

    choice_key = prompt_user("Available companies for chat context:", company_options)
    if not choice_key:
        return None # User cancelled

    if int(choice_key) <= len(available_companies):
        selected_company = available_companies[int(choice_key) - 1]
        logger.info(f"User selected company: {selected_company}")
        return selected_company
    else:
        logger.info("User skipped company selection for chat.")
        return "General_Chat_NoCompany"

def select_analysis_pdfs(company_pdf_folder: str, company_name: str) -> Tuple[Optional[str], List[str], str]:
    """Asks user for single/multi-year analysis and which PDFs to use."""
    all_pdf_paths = sorted(glob.glob(os.path.join(company_pdf_folder, "*.pdf")))
    if not all_pdf_paths:
        log_and_print(f"Warning: No PDF files found for {company_name}.", level=logging.WARNING)
        return None, [], f"Chat for {company_name} (No PDFs found)"
    
    analysis_choice = prompt_user(
        f"For {company_name}, select analysis type:",
        {"1": "Single-Year (one PDF for chat)", "2": "Multi-Year (all PDFs for chat)"}
    )
    if not analysis_choice:
        return None, [], "Cancelled"

    if analysis_choice == "1":
        pdf_options = {str(i+1): os.path.basename(p) for i, p in enumerate(all_pdf_paths)}
        pdf_choice_key = prompt_user("Select PDF for Single-Year Analysis:", pdf_options)
        
        if not pdf_choice_key:
            return None, [], "Cancelled"
            
        selected_pdf = all_pdf_paths[int(pdf_choice_key) - 1]
        desc = f"Single-Year Analysis for {company_name} ({os.path.basename(selected_pdf)})"
        logger.info(f"User selected single PDF: {os.path.basename(selected_pdf)}")
        return "single", [selected_pdf], desc
    else: # analysis_choice == "2"
        desc = f"Multi-Year Analysis for {company_name}"
        logger.info(f"User selected Multi-Year Analysis. Using all {len(all_pdf_paths)} PDFs.")
        return "multi", all_pdf_paths, desc

def _clean_and_convert_to_numeric(value: Any) -> Any:
    """
    Cleans up number strings from the PDF to be usable in Excel.
    Handles things like '$', ',', and '(123)' for negatives.
    """
    if not isinstance(value, str):
        return value  # Return non-string values as is

    cleaned_value = value.strip()
    
    if not cleaned_value or cleaned_value.lower() in ['n/a', 'not applicable']:
        return None  # Represent empty or N/A as blank cells

    # Handle accounting-style dashes for zero
    if cleaned_value in ('-', '–', '—'):
        return 0.0

    # Handle parentheses for negative numbers, e.g., (1,234) -> -1234
    if cleaned_value.startswith('(') and cleaned_value.endswith(')'):
        cleaned_value = '-' + cleaned_value[1:-1]
        
    # Remove currency symbols and commas
    cleaned_value = re.sub(r'[$,€]', '', cleaned_value)
    cleaned_value = cleaned_value.replace(',', '')

    try:
        # Convert to float
        return float(cleaned_value)
    except (ValueError, TypeError):
        # If conversion fails, return the original string value
        return value

def save_tables_to_excel(excel_path: str, tables_data: Dict[str, List[List[Any]]], pdf_filename: str):
    """
    Saves extracted tables to a formatted Excel file.
    It cleans the data, formats numbers, and auto-fits columns.
    """
    sheets_to_write = {}
    for table_name, table_data in tables_data.items():
        if not (isinstance(table_data, list) and len(table_data) > 0 and 
                isinstance(table_data[0], list) and table_data != [["Table Not Found"]]):
            logger.warning(f"Skipping malformed table '{table_name}' from {pdf_filename} (invalid structure).")
            continue

        header = table_data[0]
        data_rows = table_data[1:]
        num_header_cols = len(header)

        if num_header_cols == 0:
            logger.warning(f"Skipping table '{table_name}' from {pdf_filename} due to empty header.")
            continue

        processed_rows = []
        for i, row in enumerate(data_rows):
            row_copy = list(row) if isinstance(row, list) else []
            if len(row_copy) > num_header_cols:
                row_copy = row_copy[:num_header_cols]
            elif len(row_copy) < num_header_cols:
                row_copy.extend([""] * (num_header_cols - len(row_copy)))
            
            cleaned_row = [_clean_and_convert_to_numeric(cell) for cell in row_copy]
            processed_rows.append(cleaned_row)
        
        if not processed_rows:
            logger.warning(f"No valid data rows found for table '{table_name}' after processing.")
            continue
            
        try:
            df = pd.DataFrame(processed_rows, columns=header)
            safe_sheet_name = "".join(c for c in table_name if c.isalnum() or c in (' ', '_')).strip()[:31]
            sheets_to_write[safe_sheet_name] = df
        except Exception as e:
            logger.error(f"Pandas could not create DataFrame for table '{table_name}': {e}", exc_info=True)

    if not sheets_to_write:
        logger.warning(f"No valid tables could be processed for {pdf_filename}. No Excel file will be created.")
        print(f"  No valid tables found to save for {pdf_filename}.")
        return

    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for sheet_name, df in sheets_to_write.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Apply Number Formatting and Auto-Fit Columns
                worksheet = writer.sheets[sheet_name]
                
                # This format string displays numbers with thousands separators and no decimal places.
                # Excel handles using '.' or ',' for separators based on the user's system locale.
                number_format = '#,##0'
                
                # Apply format to all numeric cells
                for row in worksheet.iter_rows(min_row=2): # Skip header row
                    for cell in row:
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = number_format
                
                # Auto-fit column widths for better readability
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        logger.info(f"Successfully wrote and formatted {len(sheets_to_write)} sheet(s) to {excel_path}")
        print(f"  Tables extracted and formatted to: {excel_path}")
    except Exception as e:
        logger.error(f"Failed to write final Excel file at {excel_path}: {e}", exc_info=True)
        print(f"  Error writing final Excel file: {e}")

def handle_table_extraction(gemini_service: GeminiService, company_name: str, all_pdfs: List[str],
                            analysis_choice: str, selected_single_pdf: Optional[str],
                            excel_output_folder: str, log_output_folder: str):
    """Handles the table extraction process based on user choices."""
    print("-" * 30)
    pdfs_to_process = []

    try:
        # Determine which PDFs to process based on user's analysis choice.
        if analysis_choice == "single" and selected_single_pdf:
            confirm = input(f"Do you want to export tables for {os.path.basename(selected_single_pdf)}? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                pdfs_to_process = [selected_single_pdf]
        elif analysis_choice == "multi":
            confirm = input("Do you want to export tables for the multi-year analysis? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                scope = input("Export for: 1. ALL years, 2. A SINGLE year? (1/2): ").strip()
                if scope == '1':
                    pdfs_to_process = all_pdfs
                elif scope == '2':
                    # Let user pick one PDF from the multi-year list
                    print("\nSelect PDF for single-year table export:")
                    for i, pdf in enumerate(all_pdfs):
                        print(f"  {i+1}. {os.path.basename(pdf)}")
                    choice_str = input(f"Select by number (1-{len(all_pdfs)}): ").strip()
                    choice_num = int(choice_str)
                    if 1 <= choice_num <= len(all_pdfs):
                        pdfs_to_process = [all_pdfs[choice_num-1]]

    except (ValueError, KeyboardInterrupt):
        print("\nTable extraction cancelled.")
        logger.info("User cancelled table extraction.")
        return

    if not pdfs_to_process:
        print("Table export skipped.")
        return

    logger.info(f"Starting table extraction for {len(pdfs_to_process)} PDF(s).")
    extraction_log_entries = []

    for pdf_path in pdfs_to_process:
        pdf_filename = os.path.basename(pdf_path)
        print(f"\nProcessing for tables: {pdf_filename}")
        start_time = time.time()
        
        extracted_data, error = gemini_service.extract_tables_from_pdf(pdf_path, settings.TARGET_TABLES)
        
        duration = time.time() - start_time
        log_entry = {'pdf_filename': pdf_filename, 'processing_time_seconds': duration}

        if error:
            log_entry.update({'status': 'Failure', 'message': error, 'extracted_tables': []})
            print(f"  Error extracting tables: {error}")
        elif extracted_data:
            excel_file_path = os.path.join(excel_output_folder, f"{os.path.splitext(pdf_filename)[0]}_extracted_tables.xlsx")
            save_tables_to_excel(excel_file_path, extracted_data, pdf_filename)
            
            extracted_names = [name for name, data in extracted_data.items() if data and data != [["Table Not Found"]]]
            log_entry.update({
                'status': 'Success' if extracted_names else 'Partial Success (No Tables Found)',
                'message': f'Extraction process completed. See log for table details. Saved to: {excel_file_path}',
                'extracted_tables': extracted_names or ["None"]
            })
        else:
             log_entry.update({'status': 'Failure', 'message': 'No data returned from service.', 'extracted_tables': []})

        extraction_log_entries.append(log_entry)

    # Save the log file for the session
    if extraction_log_entries:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filepath = os.path.join(log_output_folder, f"{company_name}_extraction_log_{timestamp}.docx")
        generate_extraction_log(extraction_log_entries, log_filepath)
        print(f"\nTable extraction log saved to: {log_filepath}")

def upload_pdfs_for_chat(gemini_service: GeminiService, pdf_paths: List[str]) -> Dict[str, Any]:
    """Uploads the selected PDFs to Gemini to be used in the chat."""
    if not pdf_paths:
        return {}
    
    print(f"\nUploading {len(pdf_paths)} PDF(s) for chat context. This may take a moment...")
    logger.info(f"Attempting to upload {len(pdf_paths)} PDFs for chat.")
    
    uploaded_files_map = {}
    for pdf_path in pdf_paths:
        pdf_filename = os.path.basename(pdf_path)
        print(f"  - Uploading {pdf_filename}...")
        
        # The GeminiService's _upload_pdf is abstracted away here.
        # This function organizes the upload for multiple files.
        uploaded_file, error = gemini_service._upload_pdf(pdf_path)
        
        if error:
            logger.error(f"Failed to upload {pdf_filename}: {error}")
            print(f"  Error uploading {pdf_filename}. It will be excluded from the chat context.")
        elif uploaded_file:
            uploaded_files_map[pdf_filename] = uploaded_file
            logger.info(f"Successfully uploaded '{pdf_filename}' (ID: {uploaded_file.name}) for chat context.")
            print(f"  Successfully uploaded {pdf_filename}.")
        else:
            logger.error(f"An unknown error occurred during upload of {pdf_filename}.")
            print(f"  An unknown error occurred while uploading {pdf_filename}.")
            
    return uploaded_files_map

def prompt_for_next_action(has_context: bool) -> str:
    """Asks the user if they want to run preset questions or start chatting."""
    if not has_context:
        logger.info("No PDF context loaded, proceeding directly to interactive chat.")
        return 'interactive'

    choice = prompt_user(
        "What would you like to do next?",
        {
            "1": "Answer a set of preset financial questions",
            "2": "Proceed directly to interactive chatbot",
            "3": "Exit"
        }
    )
    if not choice:
        return 'exit' # Treat cancellation as exit
    
    action_map = {'1': 'preset', '2': 'interactive', '3': 'exit'}
    return action_map[choice]

def main():
    """Runs the main application loop."""
    args = parse_arguments()
    selected_company_name = args.company or select_company(args.pdf_folder)
    
    if not selected_company_name:
        log_and_print("No company selected or provided. Exiting application.", level=logging.WARNING)
        return

    paths = setup_company_paths(args, selected_company_name)
    log_and_print(f"Starting Chatbot for Session: {selected_company_name}")

    api_key = load_api_key(args.api_key_file)
    if not api_key:
        log_and_print("API Key not loaded. Exiting.", level=logging.CRITICAL)
        return

    gemini_service: Optional[GeminiService] = None
    uploaded_pdf_files_map = {}
    chat_history = []
    
    try:
        gemini_service = GeminiService(api_key=api_key)
        
        pdf_files_for_chat = []
        analysis_desc = "General Chat"

        if selected_company_name not in ["General_Chat_NoCompany", "Default_Session_NoCompany"]:
            analysis_choice, pdf_files_for_chat, analysis_desc = select_analysis_pdfs(paths['pdf'], selected_company_name)
            
            if not analysis_choice: # User cancelled selection
                return

            all_pdfs_in_folder = sorted(glob.glob(os.path.join(paths['pdf'], "*.pdf")))
            selected_pdf = pdf_files_for_chat[0] if analysis_choice == 'single' and pdf_files_for_chat else None
            handle_table_extraction(gemini_service, selected_company_name, all_pdfs_in_folder, 
                                    analysis_choice, selected_pdf, 
                                    paths['excel'], paths['log'])

        # Upload PDFs that will be used for the chat session
        if pdf_files_for_chat:
            uploaded_pdf_files_map = upload_pdfs_for_chat(gemini_service, pdf_files_for_chat)
            if not uploaded_pdf_files_map:
                print("\nWarning: All PDF uploads failed. Chat will proceed without document context.")
                logger.warning("All PDF uploads failed. No context for chat.")

        # Ask the user what to do next (preset questions or interactive chat)
        next_action = prompt_for_next_action(bool(uploaded_pdf_files_map))
        
        if next_action == 'exit':
            return # This will trigger the final block for cleanup

        if next_action == 'preset':
            ask_preset_questions(gemini_service, uploaded_pdf_files_map, chat_history)
            print("-" * 30)
            try:
                continue_choice = input("Preset questions answered. Proceed to interactive chatbot? (yes/no): ").strip().lower()
                if continue_choice not in ['yes', 'y']:
                    return # Exit if they don't want to continue
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                return

        # Main chat loop where the user can ask questions
        print("\n" + "="*50)
        print("Financial Chatbot is Ready!".center(50))
        print(f"Context: {analysis_desc}".center(50))
        print("Type 'exit' or 'quit' to end the session.".center(50))
        print("="*50)

        # If user chose 'preset', they have already seen this message.
        if next_action == 'preset':
             print("\n--- You can now ask your own questions ---")

        while True:
            user_query = input("\nYou: ").strip()
            if not user_query:
                continue
            if user_query.lower() in ["exit", "quit"]:
                logger.info("User initiated exit.")
                break
            
            logger.info(f"User query: {user_query}")
            
            if not uploaded_pdf_files_map:
                print("Chatbot: I don't have any documents loaded to answer your question. Please restart and select a company with PDFs.")
                continue

            # This block is where the app communicates with the LLM for a user's custom query.
            # Solid error handling here was crucial for a good user experience.
            try:
                llm_response, error_message = gemini_service.generate_chat_response(uploaded_pdf_files_map, user_query)
                if llm_response:
                    print(f"\nChatbot: {llm_response}")
                    chat_history.append((f"You: {user_query}", f"Chatbot: {llm_response}"))
                else:
                    error_msg = f"Sorry, I encountered an error. {error_message or 'Please try again.'}"
                    print(f"\nChatbot: {error_msg}")
                    chat_history.append((f"You: {user_query}", f"Chatbot: {error_msg}"))

            except Exception as e:
                logger.error(f"An unexpected error occurred during chat: {e}", exc_info=True)
                print("\nChatbot: A critical error occurred. Please try again or restart the application.")
                chat_history.append((f"You: {user_query}", "Chatbot: [Critical Error]"))

    except ValueError as e:
        logger.critical(f"Failed to initialize Gemini Service: {e}. Exiting application.", exc_info=True)
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user. Exiting.")
        logger.info("Chat session interrupted by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"An unexpected error occurred in the main application flow: {e}", exc_info=True)
        print(f"A critical error occurred: {e}")
    finally:
        # Final cleanup: save transcript and delete uploaded files
        if chat_history:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            transcript_filename = f"{selected_company_name}_chat_transcript_{timestamp}.docx"
            transcript_filepath = os.path.join(paths['log'], transcript_filename)
            
            print(f"\nSaving chat transcript to {transcript_filepath}...")
            loaded_pdf_names = [os.path.basename(p) for p in pdf_files_for_chat]
            
            generate_chat_transcript(chat_history, loaded_pdf_names, transcript_filepath)

        if uploaded_pdf_files_map and gemini_service:
            print("\nCleaning up uploaded files...")
            logger.info(f"Cleaning up {len(uploaded_pdf_files_map)} files from service.")
            for filename, file_obj in uploaded_pdf_files_map.items():
                gemini_service._delete_file(file_obj)
            print("Cleanup complete.")

        print("\nThank you for using the Financial Chatbot. Goodbye!")

if __name__ == '__main__':
    main() 