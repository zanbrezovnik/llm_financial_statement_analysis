"""
Handles all communication with the Google Gemini API.
"""
import google.generativeai as genai
import logging
import json
import time
from typing import List, Dict, Any, Tuple
import os

from src.config.settings import MODEL_NAME

logger = logging.getLogger(__name__)

class GeminiService:
    """A service class for all Gemini API interactions."""
    def __init__(self, api_key: str):
        """Sets up the Gemini API with the provided key."""
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(MODEL_NAME)
            logger.info(f"GeminiService initialized with model: {MODEL_NAME}")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}", exc_info=True)
            raise ValueError(f"Failed to configure Gemini API. Please check your API key and permissions.")

    def _upload_pdf(self, pdf_path: str) -> Tuple[genai.types.File | None, str | None]:
        """Uploads a PDF to Gemini and waits for it to be processed."""
        logger.info(f"Uploading PDF: {pdf_path}...")
        try:
            uploaded_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
            logger.info(f"Successfully started upload for '{pdf_path}' as '{uploaded_file.name}'.")

            # Wait for the file to finish processing.
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = genai.get_file(name=uploaded_file.name)
                logger.debug(f"File '{uploaded_file.name}' state: {uploaded_file.state.name}")

            if uploaded_file.state.name == "FAILED":
                error_msg = f"File upload failed for {pdf_path}."
                logger.error(error_msg)
                return None, error_msg
            
            logger.info(f"Successfully uploaded file '{pdf_path}' ({uploaded_file.name}).")
            return uploaded_file, None
        except Exception as e:
            error_msg = f"An unexpected error occurred during PDF upload for {pdf_path}: {e}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    def _delete_file(self, file_object: genai.types.File):
        """Deletes a file from Gemini."""
        if not file_object:
            return
        try:
            genai.delete_file(name=file_object.name)
            logger.info(f"Successfully deleted uploaded file: {file_object.name}")
        except Exception as e:
            logger.error(f"Failed to delete uploaded file {file_object.name}: {e}", exc_info=True)

    def extract_tables_from_pdf(self, pdf_path: str, target_tables: List[str]) -> Tuple[Dict[str, List[List[Any]]] | None, str | None]:
        """Extracts key financial tables from a PDF using a specific prompt."""
        logger.info(f"Attempting to extract tables: {', '.join(target_tables)} from PDF: {pdf_path}")
        uploaded_file = None
        try:
            uploaded_file, error = self._upload_pdf(pdf_path)
            if error:
                return None, error
            
            # This prompt guides the AI to extract specific tables and return them as JSON.
            prompt = f"""
            You are an expert financial data analyst specializing in extracting information from corporate financial statements.
            Analyze the provided PDF document: "{uploaded_file.display_name}".

            Your task is to identify and extract the full content of the following tables:
            {', '.join([f'"{name}"' for name in target_tables])}

            Important Instructions:
            1.  For each target table, extract all rows and columns accurately.
            2.  Ensure you capture tables even if they span multiple pages.
            3.  Include any footnotes or notes that are part of the table structure or immediately follow it and are clearly linked.
            4.  Parse financial terminology correctly. Understand that financial terms can be expressed in various ways. For example, "hedging" might be described as "an advanced risk management strategy involving buying or selling an investment to potentially help reduce the risk of loss of an existing position." Recognize such descriptions if they relate to the content or context of the target tables. Be flexible with minor variations in table titles if the content clearly matches one of the target tables.
            5.  The primary goal is to extract the specified tables. If a table title is very similar (e.g., "Consolidated Statement of Operations" instead of "CONSOLIDATED STATEMENTS OF OPERATIONS") but the content matches, extract it under the target name.
            6.  Structure the output as a single JSON object.
            7.  The JSON object should have keys corresponding to each of the target table names listed above.
            8.  The value for each key should be the extracted table data, represented as a list of lists, where the first inner list contains the header row, and subsequent inner lists contain the data rows.
            9.  If a specific target table is not found in the document, its key should still be present in the JSON, but its value should be an empty list or a list containing a single row like [["Table Not Found"]].
            10. Ensure all numerical values are extracted as strings to preserve formatting (e.g., "$1,234.56", "(789)"). Do not convert them to numbers yet.
            11. Pay close attention to the exact wording of the table titles.

            Example of expected JSON structure for one table:
            {{
              "CONSOLIDATED STATEMENTS OF OPERATIONS": [
                ["Revenue", "2023", "2022"],
                ["Product Sales", "$1,000,000", "$900,000"],
                ["Service Revenue", "$500,000", "$450,000"],
                ["Total Revenue", "$1,500,000", "$1,350,000"],
                ["Cost of Revenue", "($800,000)", "($700,000)"],
                ["Gross Profit", "$700,000", "$650,000"]
              ],
              "CONSOLIDATED BALANCE SHEETS": [
                ["Table Not Found"] 
              ]
              // ... other tables
            }}
            """
            
            response = self.model.generate_content([prompt, uploaded_file],
                                                   generation_config=genai.types.GenerationConfig(
                                                       response_mime_type="application/json"))
            
            logger.debug(f"Raw LLM response for table extraction from {pdf_path}: {response.text[:500]}...")
            
            # The JSON parsing is implemented in case the AI's output isn't perfect.
            try:
                extracted_data = json.loads(response.text)
                # Validate structure
                validated_data = {}
                for table_name in target_tables:
                    if table_name in extracted_data and isinstance(extracted_data[table_name], list):
                        # Basic check: if not empty, first element should be a list (header)
                        if not extracted_data[table_name] or isinstance(extracted_data[table_name][0], list):
                             validated_data[table_name] = extracted_data[table_name]
                        else: # Malformed table data
                            logger.warning(f"Table '{table_name}' from {pdf_path} has malformed data (expected list of lists). Assigning 'Table Not Found'.")
                            validated_data[table_name] = [["Table Data Malformed by LLM"]]
                    else:
                        logger.warning(f"Target table '{table_name}' not found or not a list in LLM response for {pdf_path}. Assigning 'Table Not Found'.")
                        validated_data[table_name] = [["Table Not Found in LLM Response"]]
                
                logger.info(f"Successfully extracted and parsed tables from {pdf_path}.")
                return validated_data, None
            except json.JSONDecodeError as je:
                error_msg = f"Failed to parse JSON response from LLM for {pdf_path}: {je}. Response text: {response.text[:500]}"
                logger.error(error_msg)
                return None, error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during table data processing for {pdf_path}: {e}"
                logger.error(error_msg)
                return None, error_msg

        except Exception as e:
            error_msg = f"An error occurred during table extraction for {pdf_path}: {e}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
        finally:
            if uploaded_file:
                self._delete_file(uploaded_file)
    
    def generate_chat_response(self, uploaded_pdf_files: Dict[str, Any], user_query: str) -> Tuple[str | None, str | None]:
        """Sends the user's question and the PDF context to Gemini to get a response."""
        if not uploaded_pdf_files:
            error_msg = "No PDF files provided for context."
            logger.warning(error_msg)
            return "I don't have any documents loaded to answer your question. Please load a document first.", error_msg
        
        logger.info(f"Generating chat response for query: '{user_query}' using {len(uploaded_pdf_files)} PDF(s).")
        
        # This detailed prompt is crucial for getting good, well-cited answers from the AI.
        pdf_references = "\n".join([f'- "{filename}" (File ID: {file_obj.name})' for filename, file_obj in uploaded_pdf_files.items()])
        
        prompt_parts = [
            f"""You are an expert financial analyst assistant. Your knowledge is strictly limited to the content of the following PDF document(s):
            {pdf_references}

            A user has asked the following question: "{user_query}"

            Your main task is to provide a comprehensive summary of the information found throughout the *entire content* of the referenced PDF document(s) that directly answers the user's question. This includes information from narrative text, discussions, tables, and any other relevant sections. Do not limit your search to just tables.
            
            Important Instructions for your response:
            1.  **Conciseness and Clarity:** Provide a concise and straightforward answer. Get directly to the point while still being comprehensive. Avoid unnecessary jargon or overly lengthy explanations if a simpler one suffices.
            2.  **Structured Output:** Please structure your response clearly. You can use the following format as a guideline:
                *   `**Key Findings:**`
                    *   `If the user's query specifically asks for one or more numerical values (e.g., "What is the total debt?", "What are the total assets and revenue?"), this section should present *only* those numerical values as directly and concisely as possible. For example: "Total Debt: $1,234,567" or "Total Assets: $2,500,000; Total Revenue: $800,000". Include currency symbols or units where appropriate as found in the document.`
                    *   `If the query is more general or asks for a non-numerical summary, provide a brief, direct textual answer or summary here.`
                    *   `If the requested numerical value(s) or information is not found after a thorough review, state this clearly here (e.g., "The total debt figure is not specified in the provided document(s).").`
                *   `**Details:**` `[This section, should provide more specific information, context, breakdowns (e.g., components of a total figure presented in Key Findings, such as types of debt), data points, or explanations supporting or elaborating on the Key Findings. Use bullet points for lists if appropriate.]`
                *   `**Citations:**` `[As detailed below, provide sources for specific facts or figures mentioned in Key Findings or Details.]`
            3.  Synthesize information from all relevant parts of the document(s) to form your answer.
            4.  Understand Financial Concepts Broadly: Financial concepts can be described using a variety of terms. When a user asks about a concept like "liabilities," your search and summary should consider related terms and sub-categories. For example, for "liabilities," look for and include information related to: 'debt', 'debt obligations', 'long-term debt', 'short-term debt', 'long-term liabilities', 'short-term liabilities', 'notes payable', 'lines of credit', 'credit facilities', and corresponding 'maturities' or 'repayment schedules'. Apply similar broad interpretation to other financial concepts mentioned in user queries.
            5.  Formatting for Readability:
                *   Use simple Markdown for emphasis: `**bold text**` for bold and `*italic text*` for italics.
                *   Use bullet points (e.g., `* Item 1`) for lists where appropriate under "**Details**".
                *   Ensure clear paragraph breaks for distinct ideas.
                *   If you need to present data in a tabular format, use a simple Markdown-like table structure:
                    Example:
                    | Header 1 | Header 2 | Header 3 |
                    |----------|----------|----------|
                    | Row1Col1 | Row1Col2 | Row1Col3 |
                    | Row2Col1 | Row2Col2 | Row2Col3 |
                    Ensure each cell content is within the pipes `|`. Do not use complex table structures.
            6.  Citations (to be placed under the `**Citations:**` heading as defined in instruction #2, or inline if only one or two minor facts that don't disrupt flow):
                *   If your answer includes a specific numeric fact, a direct figure, or a direct quote that can be attributed to a specific part of the document (like a table or a particular section/page), you MUST cite that specific source. For example: "(Source: filename.pdf, Page X, Table: CONSOLIDATED BALANCE SHEETS)" or "(Source: filename.pdf, Page Y, Section: Management Discussion)".
                *   If you present data in a table format as part of your response (using the Markdown structure), place all relevant citations for that table *immediately after* the entire table, typically under the `**Citations:**` heading related to that table's data.
                *   If information is drawn from general discussion or narrative text spanning multiple areas, and a precise page/table is not applicable for a specific point, you can state that the information is based on the overall content of "filename.pdf" after your thorough review, under the `**Citations:**` heading.
            7.  If, after a thorough review of the entire content of the document(s), the information needed to answer the question is not available, ensure this is stated clearly as per the guideline in instruction #2 under `**Key Findings:**`. Do not make assumptions or use external knowledge.
            8.  Provide a clear, concise, and well-summarized answer, following the structure outlined.
            9.  If the user's query is ambiguous, you can ask for clarification, but first attempt to provide a helpful summary based on a reasonable interpretation of the full document context, keeping in mind the broad interpretation of financial terms and the requested output structure.
            10. For complex queries, break down your answer logically, possibly using sub-headings (e.g., `***Sub-Topic***`) within the "**Details**" section.
            """
        ]
        
        # Add the uploaded PDF file objects to the request.
        for file_obj in uploaded_pdf_files.values():
            prompt_parts.append(file_obj)

        try:
            response = self.model.generate_content(prompt_parts)
            logger.info(f"Successfully generated chat response for query: '{user_query}'.")
            return response.text, None
        except Exception as e:
            error_msg = f"Error generating chat response from LLM: {e}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg 