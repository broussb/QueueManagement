# Five9 Queue Management Service

This service provides a way to manage a caller's position in a queue for a Five9 environment. It uses FastAPI for the web service and Supabase for the database.

## Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up Supabase:**
    - Create a new project on [Supabase](https://supabase.com/).
    - Create a table named `queue` with the following columns:
        - `id` (int8, primary key, auto-incrementing)
        - `created_at` (timestamptz, default now())
        - `phone_number` (text)
        - `queue_name` (text)
        - `position` (int4)
        - Add a unique constraint on `phone_number` and `queue_name` to prevent duplicates.

3.  **Configure environment variables:**
    - Create a `.env` file in the project root.
    - Add your Supabase URL and Key to the `.env` file:
      ```
      SUPABASE_URL=your_supabase_url
      SUPABASE_KEY=your_supabase_key
      ```

4.  **Run the service:**
    ```bash
    uvicorn main:app --reload
    ```

## API Endpoints

-   `POST /queue/increment`: Adds a caller to the queue and returns their position.
-   `POST /queue/decrement`: Removes a caller from the queue.
