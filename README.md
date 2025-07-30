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

## Deployment (Render)

1.  **Sign up for Render:** Create an account at [render.com](https://render.com).

2.  **Create a New Web Service:**
    -   From the dashboard, click **New +** > **Web Service**.
    -   Connect your GitHub account and select your repository (`broussb/QueueManagement`).

3.  **Configure the Service:**
    -   **Name:** Give your service a unique name (e.g., `five9-queue-manager`).
    -   **Region:** Choose a region closest to you.
    -   **Branch:** `main`
    -   **Build Command:** `pip install -r requirements.txt`
    -   **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

4.  **Add Environment Variables:**
    -   Under the **Environment** section, click **Add Environment Variable**.
    -   Add your `SUPABASE_URL` and `SUPABASE_KEY` from your `.env` file. Make sure to add them as two separate variables.

5.  **Deploy:**
    -   Click **Create Web Service**. Render will automatically build and deploy your application.
    -   Once the deployment is complete, Render will provide you with a public URL (e.g., `https://your-service-name.onrender.com`). This is the URL you will use in your Five9 IVR.
