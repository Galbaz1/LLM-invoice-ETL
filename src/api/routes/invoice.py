from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from termcolor import colored
from ...core.extractors.invoice_extractor import extract_invoice_details

router = APIRouter()

@router.post("/extract")
async def extract_receipt(file: UploadFile = File(...)):
    """
    Process an uploaded invoice text file and extract structured information.
    
    Args:
        file: The uploaded text file containing invoice data
        
    Returns:
        JSONResponse containing structured invoice information
    """
    try:
        print(colored(f"Processing uploaded file: {file.filename}", "yellow"))
        
        # Read and decode the text file
        contents = await file.read()
        text_content = contents.decode('utf-8')
        
        # Process with GPT-4 using the invoice extractor
        result = await extract_invoice_details(text_content, file.filename)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(colored(f"Error processing text file: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e)) 