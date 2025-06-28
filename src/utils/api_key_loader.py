"""
Loads the Google API Key from a file.
"""
import os
import logging

logger = logging.getLogger(__name__)

def load_api_key(filepath: str = "api_key.txt") -> str | None:
    """Loads the API key from the specified file."""
    try:
        # The app should be run from the project root, so the filepath
        # is relative to the current working directory.
        if not os.path.exists(filepath):
            logger.error(f"API key file not found at the expected path: {os.path.abspath(filepath)}")
            print(f"Error: API key file not found at: {filepath}")
            print("Please ensure the 'api_key.txt' file is in the project's root directory.")
            return None

        with open(filepath, 'r') as f:
            api_key = f.read().strip()
        
        if not api_key:
            logger.error(f"API key file '{filepath}' is empty.")
            print(f"Error: API key file '{filepath}' is empty.")
            return None
        
        logger.info(f"Successfully loaded API key from {filepath}.")
        return api_key
    except Exception as e:
        logger.error(f"Failed to load API key from {filepath}: {e}", exc_info=True)
        print(f"Error: An unexpected error occurred while loading the API key: {e}")
        return None

if __name__ == '__main__':
    # A quick test to check if the key loads correctly.
    key = load_api_key()
    if key:
        print(f"API Key loaded (first 5 chars): {key[:5]}...")
    else:
        print("API Key not loaded.") 