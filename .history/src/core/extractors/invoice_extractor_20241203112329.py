import os
import re
from typing import Dict, Any
import asyncio
from termcolor import colored
from openai import AsyncOpenAI
from langsmith import traceable
from langsmith.wrappers import wrap_openai
import instructor
from pathlib import Path

# Load template files
with open('./prompt_templates/user_info.txt', 'r', encoding='utf-8') as file:
    user_info = file.read()
with open('./prompt_templates/emballage_info.txt', 'r', encoding='utf-8') as file:
    emballage_info = file.read()

# Semaphore to limit concurrent tasks
sem = asyncio.Semaphore(500)

# Initialize OpenAI client with LangSmith and Instructor
client = wrap_openai(AsyncOpenAI())
client = instructor.from_openai(client)

@traceable(name="demo", project_name="ai-builders-demo")
async def extract_invoice_details(data: str, file: str) -> Dict[str, Any]:
    """
    Extract structured information from invoice text using GPT-4o.
    
    Args:
        data: The text content of the invoice
        file: The filename of the invoice
        
    Returns:
        Dict containing structured invoice information
    """
    try:
        print(colored(f"Processing invoice: {file}", "yellow"))
        
        async with sem:
            # Check if invoice contains emballage/statiegeld
            if re.search(r'statiegeld|emballage', data, re.IGNORECASE):
                additional_info = emballage_info
            else:
                additional_info = ""

            messages = [
                {
                    "role": "system",
                    "content": f"""Your name is Luca, you are a sophisticated extraction and classification algorithm. You are tasked with processing invoices for user.
                    
                        **User Profile**: Take the context of the user into consideration when making decisions.
                        {user_info}

                        ###
                        {additional_info}

                        ###Critical Instructions for Data Extraction:
                        You are tasked with extracting data from invoices and must adhere to the following guidelines strictly:

                        1. Truthfulness and Accuracy:
                        - Extreme accuracy and precision is a matter of life and death.
                        - Great pain will be caused if you make mistakes.
                        - You must not make mistakes.
                        2. Error Handling:
                        - If you encounter the phrase "Luca! Pay Attention!", it indicates a failure in your last attempt, you only get one chance to correct the mistake.
                        - After the phrase "Luca! Pay Attention!", an error message will follow, providing specific instructions to correct the mistake.
                        - If you see the phrase again, apply the instructions from the latest error message to rectify the issue with great rigor.

                        By following these instructions, you ensure the integrity and accuracy of the extracted data, minimizing errors and maintaining compliance with validation requirements. 
                    """
                },
                {
                    "role": "user",
                    "content": f"Here is the invoice:\n{data}"
                }
            ]

            response = await client.chat.completions.create(
                model="gpt-4o",
                temperature=0.0,
                top_p=0.9,
                response_model=InvoiceDetail,
                max_retries=2,
                messages=messages
            )
            
            # Convert the Pydantic model to a dictionary
            return response.model_dump(mode='json')
            
    except Exception as e:
        print(colored(f"Error extracting invoice details: {str(e)}", "red"))
        raise 