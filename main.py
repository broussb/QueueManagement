import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase setup
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise Exception("Supabase URL and Key must be set in the .env file")

supabase: Client = create_client(supabase_url, supabase_key)

templates = Jinja2Templates(directory="templates")

app = FastAPI(
    title="Five9 Queue Management Service",
    description="A service to manage caller positions in a queue.",
    version="1.0.0",
)

class Caller(BaseModel):
    phone_number: str
    queue_name: str

@app.post("/queue/increment")
def increment_queue(caller: Caller):
    """
    Adds a caller to a queue atomically using a database function and returns their position.
    """
    try:
        # Call the PostgreSQL function `add_caller_to_queue`
        result = supabase.rpc('add_caller_to_queue', {
            'p_phone_number': caller.phone_number,
            'p_queue_name': caller.queue_name
        }).execute()

        # The function returns the new position
        new_position = result.data
        return {"position": new_position}
    except Exception as e:
        # The DB function raises an exception for duplicates, which the client library surfaces.
        # We check for the specific error message to return a clean 409 response.
        if 'Caller is already in queue' in str(e):
            raise HTTPException(status_code=409, detail="Caller is already in this queue.")
        # For any other unexpected database errors, return a generic 500.
        raise HTTPException(status_code=500, detail=f"An unexpected database error occurred: {e}")

@app.post("/queue/decrement")
def decrement_queue(caller: Caller):
    """
    Removes a caller from the queue atomically using a database function.
    """
    try:
        # Call the PostgreSQL function `remove_caller_from_queue`
        result = supabase.rpc('remove_caller_from_queue', {
            'p_phone_number': caller.phone_number,
            'p_queue_name': caller.queue_name
        }).execute()

        # The function returns the position of the deleted caller, or 0 if not found.
        deleted_position = result.data

        if deleted_position > 0:
            return {"message": f"Caller {caller.phone_number} removed from queue {caller.queue_name}."}
        else:
            return {"message": "Caller not found in the queue or already removed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected database error occurred: {e}")

class CallerStatus(BaseModel):
    phone_number: str
    queue_name: str
    in_queue: bool
    position: int | None = None

@app.get("/queue/status", response_model=CallerStatus)
def get_caller_status(phone_number: str, queue_name: str):
    """
    Checks if a specific caller is currently in a queue and returns their status and position.
    This is useful for checking if a caller abandoned before decrementing the queue.
    """
    try:
        response = supabase.table('queue').select('id, position').match({
            'phone_number': phone_number,
            'queue_name': queue_name
        }).execute()

        if response.data:
            return {
                "phone_number": phone_number,
                "queue_name": queue_name,
                "in_queue": True,
                "position": response.data[0]['position']
            }
        else:
            return {
                "phone_number": phone_number,
                "queue_name": queue_name,
                "in_queue": False,
                "position": None
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue/count/{queue_name}")
def get_queue_count(queue_name: str):
    """
    Returns the current number of callers in a specific queue.
    """
    try:
        # Use count='exact' for an efficient count query
        response = supabase.table('queue').select('id', count='exact').eq('queue_name', queue_name).execute()
        
        count = response.count if response.count is not None else 0
        
        return {"queue_name": queue_name, "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queues/summary")
def get_queues_summary():
    """
    Returns a summary of all active queues and their current caller counts.
    """
    try:
        # This query will group by queue_name and count the callers in each.
        # Note: Supabase Python client doesn't directly support GROUP BY. 
        # We fetch all records and process them in Python.
        response = supabase.table('queue').select('queue_name').execute()
        
        if not response.data:
            return {"queues": []}

        # Count occurrences of each queue name
        queue_counts = {}
        for record in response.data:
            q_name = record['queue_name']
            queue_counts[q_name] = queue_counts.get(q_name, 0) + 1

        # Format the output
        summary = [{'queue_name': name, 'count': count} for name, count in queue_counts.items()]
        
        return {"queues": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """
    Serves the live dashboard HTML page.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/")
def read_root():
    return {"message": "Welcome to the Five9 Queue Management Service. Visit /dashboard to see the live queue status."}

