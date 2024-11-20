from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import base64
from termcolor import colored
import os
from typing import Dict
import json
from openai import AsyncOpenAI
from datetime import datetime
import asyncio
import aiofiles
import re
from typing_extensions import List, Literal, Optional, Union, Annotated, Self, Set
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field, Tag, ValidationInfo, field_validator, model_validator, EmailStr
from pydantic.types import Discriminator
from langsmith import traceable
from langsmith.wrappers import wrap_openai
import instructor
from pathlib import Path
from difflib import SequenceMatcher



# Wrap the OpenAI client with LangSmith and patch with instructor
client = wrap_openai(AsyncOpenAI())
client = instructor.from_openai(client)

# Semaphore to limit concurrent tasks
sem = asyncio.Semaphore(500)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

async def process_image_with_gpt4(image_base64: str) -> Dict:
    try:
        print(colored("Processing image with GPT-4...", "cyan"))
        
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a receipt/invoice analysis expert. Extract all relevant information from the image and return it in a structured JSON format."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please analyze this receipt image and extract all relevant information."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            response_format={ "type": "json_object" }
        )
            
        print(colored("Successfully processed image!", "green"))
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(colored(f"Error processing image: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def home(request: Request):
    try:
        print(colored("Serving home page...", "yellow"))
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        print(colored(f"Error serving home page: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract")
async def extract_receipt(file: UploadFile = File(...)):
    try:
        print(colored(f"Processing uploaded file: {file.filename}", "yellow"))
        
        # Read and encode the image
        contents = await file.read()
        base64_image = base64.b64encode(contents).decode('utf-8')
        
        # Process with GPT-4
        result = await process_image_with_gpt4(base64_image)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(colored(f"Error in extract_receipt: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True) 