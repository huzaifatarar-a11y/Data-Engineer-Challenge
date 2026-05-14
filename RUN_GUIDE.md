# Data Platform Run & Test Guide

This guide walks you through starting the system, testing data ingestion, verifying database constraints, and validating the API endpoints. 

## 1. Start the Platform
Make sure Docker Desktop is running. In your terminal, start the entire stack (PostgreSQL, Elasticsearch, Kibana, API, and Worker).
```powershell
cd "c:\Users\huzaifa\Documents\GitHub\Data Engineer Challenge\project"
docker compose up -d
```
*Tip: Wait a few seconds for all containers to report "Healthy". You can check their status using `docker compose ps`.*

## 2. Ingest Data (Test the Producer)
You will use the provided producer script to simulate a stream of publications. The producer makes concurrent `POST` requests to the ingestion API endpoint.

Open a new terminal and run:
```powershell
cd "c:\Users\huzaifa\Documents\GitHub\Data Engineer Challenge\producer"
pip install -r requirements.txt
python producer.py --url http://localhost:8000/api/v1/publications --workers 1
```

Let it run for a minute, then stop it by pressing `Ctrl + C`.
While the producer runs, you'll see successful POST operations, as well as `422 Unprocessable Entity` warnings—these are **expected** because the validation layer enforces the strict data quality rules requested in the requirements (e.g. `engagement_rate` out of bounds, future dates).

## 3. Verify System Logs
You can see exactly how the backend handles the events by looking at the logs.

**View API logs (Data Quality & Ingestion):**
```powershell
cd "c:\Users\huzaifa\Documents\GitHub\Data Engineer Challenge\project"
docker compose logs api --tail=50
```
*You should see log entries like `Publication upserted` or validation warnings.*

**View Worker logs (Elasticsearch Indexing):**
```powershell
docker compose logs worker --tail=50
```
*You should see that the worker is picking up the `pg_notify` messages and indexing the documents to Elasticsearch.*

## 4. Test the API Endpoints
Now that you have data in the system, you can verify the reads.

You can visit the interactive API documentation directly in your browser:
**[http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)**

Alternatively, test using `curl` or Powershell `Invoke-RestMethod`:

### A. Full-Text Search (Hits Elasticsearch)
Search for publications containing a random common word (e.g., "market", "music", "beautiful").
```powershell
curl "http://localhost:8000/api/v1/publications/search?q=market&limit=5"
```
*You can also add `&metrics=views:gte:100` to filter by performance metrics.*

### B. Fetch a Specific Publication (Hits PostgreSQL)
First, copy an `id` (UUID) from the previous search results, then run:
```powershell
curl "http://localhost:8000/api/v1/publications/<PASTE_UUID_HERE>"
```

### C. Fetch Author Stats (Hits PostgreSQL)
Copy an `author_id` (from the search results) and check their aggregate statistics:
```powershell
curl "http://localhost:8000/api/v1/authors/<PASTE_AUTHOR_ID_HERE>/stats"
```
*This validates that the `average_engagement_rate` and `total_posts` are dynamically aggregating properly.*

## 5. Teardown
When you are finished testing, you can spin down the containers and clean up the volumes:
```powershell
cd "c:\Users\huzaifa\Documents\GitHub\Data Engineer Challenge\project"
docker compose down -v
```
