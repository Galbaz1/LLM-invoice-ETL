#!/usr/bin/env python3
"""
PDF Invoice Extractor using LLMWhisperer API

This script processes PDF invoices and receipts using the LLMWhisperer API with optimal OCR settings.
It saves both the extracted text and complete metadata in a structured format.

Usage:
    python pdf_extractor.py <path_to_pdf>

Environment Variables:
    LLMWHISPERER_API_KEY: Your LLMWhisperer API key
"""

# Constants and Configuration
OUTPUT_DIR = "extracted_data"
API_KEY_ENV = "LLMWHISPERER_API_KEY"
LOGGING_LEVEL = "INFO"
DEFAULT_TIMEOUT = 300
FORM_MODE = "form"
OUTPUT_MODE = "layout_preserving"
LINE_SPLITTER_TOLERANCE = 0.4
HORIZONTAL_STRETCH = 1.1
MAX_FILE_SIZE_MB = 50  # Maximum file size in MB
SUPPORTED_EXTENSIONS = ['.pdf', '.PDF']
PROGRESS_INTERVAL = 5  # Seconds between progress updates

# Imports
import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
import logging
from termcolor import colored
from typing import Dict, Optional
import threading

# Configure logging
logging.basicConfig(
    level=LOGGING_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import LLMWhisperer
try:
    from unstract.llmwhisperer import LLMWhispererClientV2
except ImportError:
    print(colored("Error: LLMWhisperer client not found. Installing required package...", "red"))
    os.system("pip install llmwhisperer-client")
    from unstract.llmwhisperer import LLMWhispererClientV2

def validate_pdf(file_path: str) -> None:
    """
    Validate PDF file before processing.
    
    Args:
        file_path: Path to the PDF file
        
    Raises:
        ValueError: If file validation fails
    """
    path = Path(file_path)
    
    # Check if file exists
    if not path.exists():
        raise ValueError(colored(f"File not found: {file_path}", "red"))
    
    # Check file extension
    if path.suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(colored(f"Unsupported file type. Please provide a PDF file.", "red"))
    
    # Check file size
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            colored(f"File size ({file_size_mb:.1f}MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB}MB)", "red")
        )

def setup_output_directory() -> Path:
    """Create output directory if it doesn't exist."""
    try:
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(colored(f"✓ Output directory ready: {output_dir}", "green"))
        return output_dir
    except Exception as e:
        error_msg = f"Failed to create output directory: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(colored(error_msg, "red"))

def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        error_msg = f"API Key not found! Please set the {API_KEY_ENV} environment variable"
        logger.error(error_msg)
        raise ValueError(colored(error_msg, "red"))
    return api_key

def show_progress(stop_event: threading.Event) -> None:
    """Show progress indicator while processing."""
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    while not stop_event.is_set():
        print(colored(f"\r{spinner[i]} Processing...", "cyan"), end="")
        i = (i + 1) % len(spinner)
        time.sleep(0.1)
    print("\r", end="")

def process_pdf(file_path: str, client: LLMWhispererClientV2) -> Dict:
    """
    Process a PDF file using LLMWhisperer with optimal settings for complex invoices.
    
    Args:
        file_path: Path to the PDF file
        client: LLMWhisperer client instance
    
    Returns:
        Dict containing the extraction results
    """
    try:
        print(colored("→ Starting PDF processing...", "cyan"))
        print(colored(f"  File: {file_path}", "cyan"))
        
        # Start progress indicator
        stop_progress = threading.Event()
        progress_thread = threading.Thread(target=show_progress, args=(stop_progress,))
        progress_thread.daemon = True
        progress_thread.start()
        
        try:
            # Use optimal settings for complex invoices
            result = client.whisper(
                file_path=file_path,
                wait_for_completion=True,
                wait_timeout=DEFAULT_TIMEOUT,
                mode=FORM_MODE,
                output_mode=OUTPUT_MODE,
                line_splitter_tolerance=LINE_SPLITTER_TOLERANCE,
                horizontal_stretch_factor=HORIZONTAL_STRETCH,
            )
        finally:
            # Stop progress indicator
            stop_progress.set()
            progress_thread.join()
        
        # Validate response
        if not isinstance(result, dict) or 'extraction' not in result:
            raise RuntimeError("Invalid response from API")
            
        print(colored("✓ PDF processing completed successfully", "green"))
        return result
        
    except Exception as e:
        error_msg = f"Error processing PDF: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(colored(error_msg, "red"))

def save_results(result: Dict, original_pdf_path: str, output_dir: Path) -> None:
    """Save extraction results to JSON and text files."""
    try:
        print(colored("→ Saving extraction results...", "cyan"))
        
        # Create filename based on original PDF name
        base_name = Path(original_pdf_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save extracted text
        text_file = output_dir / f"{base_name}_{timestamp}.txt"
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(result["extraction"]["result_text"])
        print(colored(f"✓ Extracted text saved to: {text_file}", "green"))
        
        # Save full extraction data
        json_file = output_dir / f"{base_name}_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(colored(f"✓ Full extraction data saved to: {json_file}", "green"))
        
    except Exception as e:
        error_msg = f"Failed to save results: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(colored(error_msg, "red"))

def main():
    """Main function to process PDF files."""
    try:
        if len(sys.argv) != 2:
            print(colored("Error: Invalid number of arguments", "red"))
            print(colored("Usage: python pdf_extractor.py <path_to_pdf>", "yellow"))
            sys.exit(1)
            
        pdf_path = sys.argv[1]
        
        # Validate PDF file
        validate_pdf(pdf_path)
            
        # Setup
        print(colored("→ Initializing...", "cyan"))
        output_dir = setup_output_directory()
        api_key = get_api_key()
        
        # Initialize client
        print(colored("→ Connecting to LLMWhisperer API...", "cyan"))
        client = LLMWhispererClientV2(api_key=api_key)
        
        # Process PDF
        result = process_pdf(pdf_path, client)
        
        # Save results
        save_results(result, pdf_path, output_dir)
        
        print(colored("✓ All operations completed successfully!", "green"))
        
    except Exception as e:
        print(colored(f"Error: {str(e)}", "red"))
        sys.exit(1)

if __name__ == "__main__":
    main() 