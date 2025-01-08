from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from .utils import *

import os
import logging

# setup loggers
log_dir = "logs"

if not os.path.exists:
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename="logs/api_log.txt",
    filemode="w",
    level=logging.INFO
)

# get root logger
logger = logging.getLogger(__name__)  # the __name__ resolve to "main" since we are at the root of the project. 

# Initialize FastAPI app
app = FastAPI()

# Delete the jobs.db file if it exists
if os.path.exists("jobs.db"):
    os.remove("jobs.db")

# Initialize APScheduler
scheduler = BackgroundScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(url="sqlite:///jobs.db")  # Persistent job store
    },
    executors={
        "default": ThreadPoolExecutor(10),  # Adjust thread pool size as needed
    },
    timezone="CET",  # Set your timezone
)

scheduler.add_job(
    id="added_url_scanner",  # Unique job ID
    func=scan_url_call,  # The function to run
    trigger="interval",   # Interval-based scheduling
    seconds=120,           # Runs every 120 seconds
)

scheduler.add_job(
    id="availability_scanner",  # Unique job ID
    func=availability_call,  # The function to run
    trigger="interval",   # Interval-based scheduling
    seconds=10800,           # Runs every 10800 seconds (3 hours)
)

# Serve static files (for Bootstrap and custom styles)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Set up Jinja2 templates directory
templates = Jinja2Templates(directory="src/templates")

# Create Tables if not exist
create_tables()

# Start the scheduler when the application starts
@app.on_event("startup")
def start_scheduler():
    scheduler.start()

# Shutdown the scheduler when the application stops
@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

# Define the index route
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Route for the Add Manga page
@app.get("/add-manga", response_class=HTMLResponse)
async def get_add_manga(request: Request):
    return templates.TemplateResponse("add_manga.html", {"request": request})

# Handle form submission from the Add Manga page
@app.post("/add-manga", response_class=HTMLResponse)
async def post_add_manga(request: Request, manga_urls: str = Form(...)):
    # Split the input by newlines to handle multiple URLs if entered
    urls_list = [url.strip() for url in manga_urls.splitlines() if url.strip()]
    
    # For debugging purposes, print the URLs entered
    logger.info("********************************")
    logger.info("Manga URLs Submitted:", urls_list)
    logger.info("********************************")
    
    # Adding urls to the db for a later parsing
    for url in urls_list:
        clean_url = url.strip().lower()
        add_url(clean_url)

    # Display a confirmation message in the response
    message = f"URLs submitted and added to the database successfully!"
    
    # Pass the submitted URLs and message back to the template for feedback
    return templates.TemplateResponse("add_manga.html", {
        "request": request,
        "submitted_urls": urls_list,
        "message": message
    })

@app.route('/list-all')
def list_all(request: Request):
    try:
        conn = create_connection(input_msg='List-all Route')
        cursor = conn.cursor(dictionary=True)
        query = "SELECT title, price, availability, cover, trama, url FROM manga"
        cursor.execute(query)
        mangas = cursor.fetchall()
    except Exception as e:
        return HTMLResponse(content=f"Error retrieving mangas: {e}", status_code=500)
    finally:
        close_connection(conn)
    # Render the template with manga data
    return templates.TemplateResponse(
        "list_all.html", {"request": request, "mangas": mangas}
    )

# Define a status endpoint to verify the application is running
@app.get("/status")
def read_status():
    return {"status": "running", "app": "FastAPI Application", "version": "1.0"}


# Define an endpoint to list all scheduled jobs
@app.get("/jobs")
def get_jobs():
    jobs = scheduler.get_jobs()
    return [{"id": job.id, "next_run": job.next_run_time} for job in jobs]


