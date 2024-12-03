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
        
        # Check if file was processed before
        existing_result = db.check_file_exists(contents)
        if existing_result and existing_result.get('json_result'):
            print(colored("✓ Found existing results in database", "green"))
            return JSONResponse(content=existing_result['json_result'])
        
        # Process based on file type
        if file.filename.lower().endswith('.pdf'):
            # Save PDF content first
            file_hash, is_new = db.save_file(file.filename, contents)
            
            # Check if we have text content
            text_content = db.get_text_content(file_hash)
            if not text_content:
                # Process PDF file
                text_content = await process_pdf(contents, file.filename)
                # Update with text content
                db.save_file(file.filename, contents, text_content=text_content)
        elif file.filename.lower().endswith('.txt'):
            # Process text file
            text_content = contents.decode('utf-8')
            file_hash, is_new = db.save_file(
                file.filename, 
                contents, 
                text_content=text_content
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a PDF or text file."
            )
        
        # Extract invoice details using GPT-4
        result = await extract_invoice_details(text_content, file.filename)
        
        # Save the final results
        db.save_file(file.filename, contents, text_content=text_content, json_result=result)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(colored(f"Error processing file: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e)) 