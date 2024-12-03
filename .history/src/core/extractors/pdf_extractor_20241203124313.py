import os
import logging
from pathlib import Path
from termcolor import colored
from typing import Dict, Any
from unstract.llmwhisperer import LLMWhispererClientV2

# Constants
API_KEY_ENV = "LLMWHISPERER_API_KEY"
LOGGING_LEVEL = "INFO"
DEFAULT_TIMEOUT = 300
FORM_MODE = "form"
OUTPUT_MODE = "layout_preserving"
LINE_SPLITTER_TOLERANCE = 0.4
HORIZONTAL_STRETCH = 1.1
MAX_FILE_SIZE_MB = 50
SUPPORTED_EXTENSIONS = ['.pdf', '.PDF']

# Configure logging
logging.basicConfig(
    level=LOGGING_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_pdf(file_content: bytes, filename: str) -> None:
    """
    Validate PDF file before processing.
    
    Args:
        file_content: Binary content of the PDF file
        filename: Name of the uploaded file
        
    Raises:
        ValueError: If file validation fails
    """
    # Check file extension
    if not any(filename.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise ValueError(colored(f"Unsupported file type. Please provide a PDF file.", "red"))
    
    # Check file size
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            colored(f"File size ({file_size_mb:.1f}MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB}MB)", "red")
        )

def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        error_msg = f"API Key not found! Please set the {API_KEY_ENV} environment variable"
        logger.error(error_msg)
        raise ValueError(colored(error_msg, "red"))
    return api_key

async def process_pdf(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Process a PDF file using LLMWhisperer with optimal settings.
    
    Args:
        file_content: Binary content of the PDF file
        filename: Name of the uploaded file
    
    Returns:
        Dict containing the extraction results
    """
    try:
        print(colored("→ Starting PDF processing...", "cyan"))
        print(colored(f"  File: {filename}", "cyan"))
        
        # Validate PDF
        validate_pdf(file_content, filename)
        
        # Get API key and initialize client
        api_key = get_api_key()
        client = LLMWhispererClientV2(api_key=api_key)
        
        # Save temporary file
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / filename
        
        try:
            # Write temporary file
            with open(temp_file, "wb") as f:
                f.write(file_content)
            
            # Process with LLMWhisperer
            result = client.whisper(
                file_path=str(temp_file),
                wait_for_completion=True,
                wait_timeout=DEFAULT_TIMEOUT,
                mode=FORM_MODE,
                output_mode=OUTPUT_MODE,
                line_splitter_tolerance=LINE_SPLITTER_TOLERANCE,
                horizontal_stretch_factor=HORIZONTAL_STRETCH,
            )
            
            # Validate response
            if not isinstance(result, dict) or 'extraction' not in result:
                raise RuntimeError("Invalid response from API")
            
            print(colored("✓ PDF processing completed successfully", "green"))
            return result['extraction']['result_text']
            
        finally:
            # Cleanup temporary file
            if temp_file.exists():
                temp_file.unlink()
            
    except Exception as e:
        error_msg = f"Error processing PDF: {str(e)}"
        logger.error(error_msg)
        raise 