"""
CLI utility functions for user input and display.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def log_and_print(message: str, level: int = logging.INFO):
    """Helper to log a message and print it."""
    print(message)
    logging.log(level, message)

def prompt_user(prompt_text: str, options: Dict[str, str]) -> Optional[str]:
    """
    A reusable function to ask the user a question with a list of options.
    Handles input validation and errors.

    Args:
        prompt_text: Text to display before the list of options.
        options: Dictionary of choices, e.g., {"1": "First Choice"}.

    Returns:
        The key of the chosen option, or None if the user cancels.
    """
    print("-" * 30)
    print(prompt_text)
    for key, description in options.items():
        print(f"  {key}. {description}")

    valid_keys = options.keys()
    
    while True:
        try:
            choice = input(f"Select an option ({', '.join(valid_keys)}): ").strip()
            if choice in valid_keys:
                return choice
            else:
                print(f"Invalid selection. Please enter one of the following: {', '.join(valid_keys)}")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            logger.warning("User cancelled input prompt.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during user input: {e}", exc_info=True)
            print("An unexpected error occurred. Please try again.")
            return None