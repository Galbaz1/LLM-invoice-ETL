# Invoice Information Extractor

A modern web application for extracting structured information from invoices using OpenAI's GPT-4o model and the Instructor Library, with robust data validation through Pydantic V2.

## Features

- Modern web interface with drag-and-drop file upload
- Structured information extraction from invoice text
- Comprehensive validation of Dutch tax rules and business logic
- Support for emballage/statiegeld handling
- Detailed error feedback and analysis
- Multi-supplier support

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd fancy-receipt-extractor
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
export OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Start the server:
```bash
# From the project root directory
python -m src.main
```

2. Open your browser and navigate to:
```
http://127.0.0.1:8000
```

3. Upload a text file containing invoice data
4. View the extracted structured information

## Project Structure

```
src/
  ├── __init__.py
  ├── api/
  │   ├── __init__.py
  │   └── routes/
  │       ├── __init__.py
  │       └── invoice.py
  ├── core/
  │   ├── __init__.py
  │   └── extractors/
  │       ├── __init__.py
  │       └── invoice_extractor.py
  ├── models/
  │   ├── __init__.py
  │   └── pydantic/
  │       ├── __init__.py
  │       ├── invoice.py
  │       └── invoice_detail.py
  └── main.py
static/
  ├── css/
  │   └── styles.css
  └── js/
      └── main.js
templates/
  └── index.html
prompt_templates/
  ├── user_info.txt
  └── emballage_info.txt
requirements.txt
```

## Dependencies

- FastAPI
- Pydantic V2
- OpenAI
- Instructor
- LangSmith
- Additional dependencies in requirements.txt

## Error Handling

The application provides detailed error feedback for:
- Invalid VAT IDs
- Incorrect tax calculations
- Invalid IBAN numbers
- Date format issues
- Amount mismatches
- Citation validation

## Development

The project follows a modular structure:
- `src/models/pydantic/`: Pydantic models for data validation
- `src/core/extractors/`: Core business logic for invoice extraction
- `src/api/routes/`: FastAPI route handlers
- `static/`: Frontend assets (CSS, JavaScript)
- `templates/`: HTML templates
- `prompt_templates/`: GPT-4o prompt templates

## License

[Your License Here]
