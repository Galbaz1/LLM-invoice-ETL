Receipt Extractor - AI-Powered Receipt Analysis Tool

This application provides a beautiful, animated web interface for extracting information from receipts and invoices using OpenAI's GPT-4 model.

Features:
- Drag & drop or click to upload text (.txt) files
- Real-time processing with animated feedback
- Side-by-side Markdown and JSON output
- Copy and download functionality for both formats
- Dark mode with animated gradients
- Responsive design with smooth animations

Setup Instructions:
1. Install Python requirements:
   pip install -r requirements.txt

2. Set your OpenAI API key as an environment variable:
   export OPENAI_API_KEY="your-api-key-here"

3. Run the application:
   python main.py

4. Open your browser and navigate to:
   http://127.0.0.1:8000

How It Works:
1. Upload Text File:
   - Drag and drop a receipt text file onto the upload area
   - Or click "Choose File" to select a text file

2. Processing:
   - The text is processed by the backend
   - A loading animation indicates processing status

3. Results:
   - The upload area smoothly transitions to the left
   - Markdown and JSON views appear side by side
   - Both formats can be copied or downloaded

File Structure:
/receipt_extractor
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── README.txt          # This file
├── static/
│   ├── css/
│   │   └── styles.css  # Styling and animations
│   └── js/
│       └── main.js     # Frontend functionality
└── templates/
    └── index.html      # Main webpage template

Notes:
- Requires a valid OpenAI API key
- Supports text (.txt) files only
- Processes one receipt at a time
- Provides structured data output in both Markdown and JSON formats

Error Handling:
- Invalid file types are detected and reported
- API errors are caught and displayed
- Network issues are handled gracefully

The application uses FastAPI for the backend, with a modern frontend featuring CSS animations and JavaScript for interactivity. All processing status is shown with visual feedback, and the results are presented in a clean, user-friendly interface. 