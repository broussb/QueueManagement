import asyncio
import aiohttp
import random
import uuid

# --- Configuration ---
BASE_URL = "https://queuemanagement-6yti.onrender.com"
QUEUES = ["Sales_HighVolume", "Support_Tier1", "Billing_Inquiries"]
NUM_CONCURRENT_CALLERS = 15  # Number of simulated callers acting at once
TEST_DURATION_SECONDS = 120    # How long to run the test
ADD_CALLER_CHANCE = 0.7      # 70% chance to add a caller, 30% to remove

# ---------------------

active_callers = {}

async def add_caller(session, queue_name):
    """Simulates a new caller entering a queue."""
    phone_number = f"555-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
    caller_id = str(uuid.uuid4())
    payload = {"phone_number": phone_number, "queue_name": queue_name}
    
    try:
        async with session.post(f"{BASE_URL}/queue/increment", json=payload) as response:
            if response.status == 200:
                print(f"[+] Added caller {phone_number} to {queue_name}")
                if queue_name not in active_callers:
                    active_callers[queue_name] = []
                active_callers[queue_name].append(payload)
            else:
                print(f"[!] Failed to add caller. Status: {response.status}")
    except Exception as e:
        print(f"[!] Error adding caller: {e}")

async def remove_caller(session, queue_name):
    """Simulates a caller being removed from a queue (connected or abandoned)."""
    if not active_callers.get(queue_name):
        # print(f"[*] No active callers in {queue_name} to remove.")
        return

    caller_to_remove = active_callers[queue_name].pop(0)
    
    try:
        async with session.post(f"{BASE_URL}/queue/decrement", json=caller_to_remove) as response:
            if response.status == 200:
                print(f"[-] Removed caller {caller_to_remove['phone_number']} from {queue_name}")
            else:
                print(f"[!] Failed to remove caller. Status: {response.status}")
    except Exception as e:
        print(f"[!] Error removing caller: {e}")

async def simulate_caller_activity(session):
    """A single simulated caller's continuous activity."""
    while True:
        queue = random.choice(QUEUES)
        if random.random() < ADD_CALLER_CHANCE:
            await add_caller(session, queue)
        else:
            await remove_caller(session, queue)
        
        await asyncio.sleep(random.uniform(0.1, 0.5)) # Wait a short random time

async def main():
    """Main function to set up and run the simulation."""
    print(f"--- Starting Stress Test for {TEST_DURATION_SECONDS} seconds ---")
    print(f"Target URL: {BASE_URL}")
    print(f"Concurrent Callers: {NUM_CONCURRENT_CALLERS}")
    print("--------------------------------------------------")

    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(simulate_caller_activity(session)) for _ in range(NUM_CONCURRENT_CALLERS)]
        
        # Run the simulation for the specified duration
        await asyncio.sleep(TEST_DURATION_SECONDS)
        
        # Cancel all tasks to stop the simulation
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to finish cancelling
        await asyncio.gather(*tasks, return_exceptions=True)

    print("\n--------------------------------------------------")
    print("--- Stress Test Finished ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Simulation stopped by user.")
