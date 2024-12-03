from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from termcolor import colored
from api.routes import invoice

# Initialize the FastAPI application
app = FastAPI(title="Invoice Processor")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(invoice.router)

@app.get("/")
async def home(request: Request):
    """Serve the home page"""
    try:
        print(colored("Serving home page...", "yellow"))
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "AI Invoice Processor"
        })
    except Exception as e:
        print(colored(f"Error serving home page: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True) 