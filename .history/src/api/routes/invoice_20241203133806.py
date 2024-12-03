from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from termcolor import colored
from ...core.extractors.invoice_extractor import extract_invoice_details
from ...core.extractors.pdf_extractor import process_pdf
from ...core.db.database import InvoiceDB

router = APIRouter()
db = InvoiceDB()

@router.post("/extract")
async def extract_receipt(file: UploadFile = File(...)):
    """
    Process an uploaded invoice file (PDF or text) and extract structured information.
    Checks database for existing results before processing.
    
    Args:
        file: The uploaded file containing invoice data
        
    Returns:
        JSONResponse containing structured invoice information
    """
    try:
        print(colored(f"Processing uploaded file: {file.filename}", "yellow"))
        
        # Read file content
        contents = await file.read()
        
        # Process based on file type
        if file.filename.lower().endswith('.pdf'):
            # Process PDF file
            text_content = await process_pdf(contents, file.filename)
        elif file.filename.lower().endswith('.txt'):
            # Process text file
            text_content = contents.decode('utf-8')
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a PDF or text file."
            )
        
        # Extract invoice details using GPT-4
        result = await extract_invoice_details(text_content, file.filename)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(colored(f"Error processing file: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e)) 