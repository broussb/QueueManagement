import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
import json
import asyncio
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
import asyncio

# --- Real-time Broadcast Manager ---
class BroadcastManager:
    def __init__(self):
        self.subscribers = []
        self.lock = asyncio.Lock()

    async def subscribe(self, queue):
        async with self.lock:
            self.subscribers.append(queue)

    async def unsubscribe(self, queue):
        async with self.lock:
            self.subscribers.remove(queue)

    async def broadcast(self, message: str):
        async with self.lock:
            for queue in self.subscribers:
                await queue.put(message)

broadcaster = BroadcastManager()

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
async def increment_queue(caller: Caller):
    """
    Adds a caller to a queue atomically using a database function and returns their position.
    """
    try:
        result = supabase.rpc('add_caller_to_queue', {
            'p_phone_number': caller.phone_number,
            'p_queue_name': caller.queue_name
        }).execute()
        new_position = result.data
        # After a successful update, trigger a broadcast
        await broadcast_update()
        return {"position": new_position}
    except Exception as e:
        if 'Caller is already in queue' in str(e):
            raise HTTPException(status_code=409, detail="Caller is already in this queue.")
        raise HTTPException(status_code=500, detail=f"An unexpected database error occurred: {e}")

@app.post("/queue/decrement")
async def decrement_queue(caller: Caller):
    """
    Removes a caller from the queue atomically using a database function.
    """
    try:
        result = supabase.rpc('remove_caller_from_queue', {
            'p_phone_number': caller.phone_number,
            'p_queue_name': caller.queue_name
        }).execute()
        deleted_position = result.data
        if deleted_position > 0:
            # After a successful update, trigger a broadcast
            await broadcast_update()
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


# Helper function to fetch the latest summary and broadcast it
async def broadcast_update():
    try:
        response = supabase.rpc('get_queue_summary').execute()
        summary = response.data or {}
        await broadcaster.broadcast(json.dumps(summary))
    except Exception as e:
        print(f"Error broadcasting update: {e}")

@app.get("/stream/queues/summary")
async def stream_queues_summary(request: Request):
    queue = asyncio.Queue()
    await broadcaster.subscribe(queue)

    # Send initial data on connect
    await broadcast_update()

    async def event_generator():
        try:
            while True:
                message = await queue.get()
                if await request.is_disconnected():
                    break
                yield message
        finally:
            await broadcaster.unsubscribe(queue)
            print("Client disconnected, unsubscribed.")

    return EventSourceResponse(event_generator())


@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """
    Serves the live dashboard HTML page.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/")
def read_root():
    return {"message": "Welcome to the Five9 Queue Management Service. Visit /dashboard to see the live queue status."}

