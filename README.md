# Fancy Receipt Extractor

A modern web application for extracting structured information from PDF invoices and receipts using OpenAI's GPT-4o model, LLMWhisperer for PDF processing, and the Instructor Library, with robust data validation through Pydantic V2.

## Features

- Modern web interface with drag-and-drop PDF upload
- PDF preview with multi-page navigation
- Structured information extraction from PDFs
- Comprehensive validation of Dutch tax rules and business logic
- Support for emballage/statiegeld handling
- Detailed error feedback and analysis
- Multi-supplier support
- SQLite database for result storage

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/fancy-receipt-extractor.git
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
export LLMWHISPERER_API_KEY=your_api_key_here
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

3. Upload a PDF file containing invoice/receipt data
4. View the PDF preview and extracted structured information

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
  │   ├── db/
  │   │   ├── __init__.py
  │   │   └── database.py
  │   └── extractors/
  │       ├── __init__.py
  │       ├── invoice_extractor.py
  │       └── pdf_extractor.py
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
- LLMWhisperer
- SQLite
- Additional dependencies in requirements.txt

## Error Handling

The application provides detailed error feedback for:
- Invalid file formats or sizes
- PDF processing issues
- Invalid VAT IDs
- Incorrect tax calculations
- Invalid IBAN numbers
- Date format issues
- Amount mismatches
- Citation validation

## Development

The project follows a modular structure:
- `src/models/pydantic/`: Pydantic models for data validation
- `src/core/extractors/`: Core business logic for PDF and invoice extraction
- `src/core/db/`: Database operations
- `src/api/routes/`: FastAPI route handlers
- `static/`: Frontend assets (CSS, JavaScript)
- `templates/`: HTML templates
- `prompt_templates/`: GPT-4o prompt templates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

Copyright (c) 2024 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
