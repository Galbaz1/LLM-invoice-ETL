import sys
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import os
from typing import Dict
import json
# Import other necessary modules for processing

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    logger.info(f"Received file: {file.filename} with content type: {file.content_type}")

    if not (file.content_type == 'text/plain' or file.filename.endswith('.txt')):
        logger.error("Invalid file type received.")
        raise HTTPException(status_code=400, detail='Invalid file type. Only .txt files are accepted.')

    try:
        contents = await file.read()
        logger.info(f"Read {len(contents)} bytes from the file.")

        # TODO: Implement your receipt processing logic here
        # For demonstration, we'll just return the text content
        data = {
            "parsed_text": contents.decode('utf-8')
        }

        logger.info("Successfully processed the file.")
        return JSONResponse(content=data)

    except Exception as e:
        logger.exception("An error occurred while processing the file.")
        raise HTTPException(status_code=500, detail=str(e))