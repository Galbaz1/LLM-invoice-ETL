import os
import sys
from pathlib import Path
from termcolor import colored

# Constants
CACHE_DIR = ".unified_cache"

def setup_cache_directory():
    try:
        # Create the cache directory if it doesn't exist
        cache_path = Path(CACHE_DIR).absolute()
        cache_path.mkdir(exist_ok=True)
        
        # Set the environment variable
        os.environ["PYTHONPYCACHEPREFIX"] = str(cache_path)
        
        print(colored(f"✓ Cache directory set to: {cache_path}", "green"))
        print(colored("✓ All __pycache__ files will now be stored in this directory", "green"))
        
        # Clean up existing __pycache__ directories
        clean_existing_cache()
        
    except Exception as e:
        print(colored(f"Error setting up cache directory: {str(e)}", "red"))
        sys.exit(1)

def clean_existing_cache():
    try:
        os.system('find . -type d -name "__pycache__" -exec rm -rf {} +')
        print(colored("✓ Cleaned up existing __pycache__ directories", "green"))
    except Exception as e:
        print(colored(f"Warning: Could not clean existing cache: {str(e)}", "yellow"))

if __name__ == "__main__":
    print(colored("Setting up unified Python cache directory...", "cyan"))
    setup_cache_directory() 