import os
from fastapi import FastAPI, HTTPException
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
    Adds a caller to a queue and returns their position.
    When a new caller enters the queue, this endpoint calculates their position
    and stores it in the database.
    """
    try:
        # Check if the caller is already in the queue
        existing_caller_response = supabase.table('queue').select('id').match({
            'phone_number': caller.phone_number,
            'queue_name': caller.queue_name
        }).execute()

        if existing_caller_response.data:
            raise HTTPException(status_code=409, detail="Caller is already in this queue.")

        # Check for existing callers in the same queue
        response = supabase.table('queue').select('id').eq('queue_name', caller.queue_name).execute()
        current_queue_size = len(response.data)
        new_position = current_queue_size + 1

        # Add the new caller to the queue
        insert_response = supabase.table('queue').insert({
            'phone_number': caller.phone_number,
            'queue_name': caller.queue_name,
            'position': new_position
        }).execute()

        if not insert_response.data:
            raise HTTPException(status_code=500, detail="Failed to add caller to the queue.")

        return {"position": new_position}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/decrement")
def decrement_queue(caller: Caller):
    """
    Removes a caller from the queue and updates the positions of others.
    This is triggered when a call is connected to an agent.
    """
    try:
        # Find and remove the caller from the queue
        deleted_caller_response = supabase.table('queue').delete().match({
            'phone_number': caller.phone_number, 
            'queue_name': caller.queue_name
        }).execute()

        if not deleted_caller_response.data:
            # This can happen if the caller is not in the queue, which is not necessarily an error.
            return {"message": "Caller not found in the queue or already removed."}
        
        deleted_position = deleted_caller_response.data[0]['position']

        # Get all callers in the same queue with a higher position
        callers_to_update = supabase.table('queue').select('*')\
            .eq('queue_name', caller.queue_name)\
            .gt('position', deleted_position)\
            .execute()

        # Decrement their positions
        for c in callers_to_update.data:
            new_pos = c['position'] - 1
            supabase.table('queue').update({'position': new_pos}).eq('id', c['id']).execute()

        return {"message": f"Caller {caller.phone_number} removed from queue {caller.queue_name}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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


@app.get("/")
def read_root():
    return {"message": "Welcome to the Five9 Queue Management Service."}

