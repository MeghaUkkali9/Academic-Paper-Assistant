## client.py
This file talks to arXiv's API. The main method is fetch_papers().
It builds a URL, makes an HTTP request, gets back XML, and turns it into a list of ArxivPaper objects. It also handles rate limiting


## setup.py — Pre-flight checks

### What this file does in one sentence
Before fetching any papers, this file makes sure all the tools
we need are alive and ready to use.

### What tools it checks
1. PostgreSQL (our database) — stores paper metadata
2. OpenSearch (our search engine) — lets us search papers later

### How it checks them
- Database: runs "SELECT 1" — the simplest possible query.
  If it doesn't crash, the database is alive.
- OpenSearch: asks for cluster health. Green/yellow = ok. Red = problem.
  (Note: the code currently accepts "red" as ok — this is a bug)

### What it sets up
- Creates the search index if it doesn't exist yet
- Creates the RRF pipeline (a way of combining keyword + meaning search)
- If they already exist, it skips creation quietly

### What it returns
{"status": "success", "message": "Environment setup completed"}
If anything fails, it raises an Exception and the whole DAG stops.

### Key thing to remember
This runs FIRST in the DAG, every single morning.
If this step fails, none of the other 4 steps run at all.
It's the gatekeeper.

### Known issues (from code review)
- Accepts OpenSearch "red" status as healthy (should be a bug fix)
- Exception wrapping loses the original error traceback
  (use "raise X from e" instead of "raise X")

-----------------------------------------------
## client.py — The arXiv fetcher

### What this file does in one sentence
This file is responsible for talking to arXiv's website,
downloading paper information, and turning it into Python
objects our system can work with.

### Think of it like this
Imagine a librarian who:
1. Knows the address of arXiv's library (base_url)
2. Knows how to ask for books politely (rate limiting)
3. Can read arXiv's language (XML parsing)
4. Brings back a neat list of paper summaries (ArxivPaper objects)
That librarian is ArxivClient.

### The main methods — what each one does

fetch_papers()
  The main one. Fetches papers by category (e.g. cs.AI)
  and optionally by date range. Used by the DAG every morning.
  Example: "give me all cs.AI papers from yesterday"

fetch_papers_with_query()
  Same as above but you write the search query yourself.
  More flexible. Example: "give me papers by LeCun in cs.AI"

fetch_paper_by_id()
  Fetches one specific paper by its arXiv ID.
  Example: "give me paper 2507.17748"
  BUG: missing timeout — can hang forever.

download_pdf()
  Downloads the actual PDF file to a local folder.
  Checks if it's already downloaded first (caching).

_parse_response()
  Takes raw XML from arXiv and turns it into a list
  of ArxivPaper objects. Called internally after every fetch.

_download_with_retry()
  Tries to download a PDF up to N times before giving up.
  Waits longer between each failed attempt (backoff).
  BUG: says "exponential backoff" in comment but is actually linear.

### What is rate limiting and why does it matter
arXiv asks that you wait 3 seconds between requests.
If you spam their API too fast, they block you.
The client tracks the last request time and sleeps if
needed before making the next request.
BUG: if two requests happen at the same time, this can break.
Fix needed: asyncio.Lock around the rate limit check.

### What is XML parsing
arXiv returns data in XML format (like HTML but for data).
The _parse_response() method reads that XML and pulls out:
- Paper ID
- Title
- Authors
- Abstract
- Categories
- PDF URL

### What ArxivPaper is
A simple Python object (defined elsewhere) that holds
all the info about one paper. Like a neat little box
with labeled compartments for title, authors, abstract etc.

### Known bugs (from code review)
1. fetch_paper_by_id() has no timeout — can hang forever
2. Rate limiter is not safe for concurrent (simultaneous) requests
3. Partial PDF downloads not cleaned up on timeout
4. Retry backoff comment says "exponential" but code is linear
5. Rate limit sleep in download always waits full delay unnecessarily


------------------------------------------------
## factory.py + common.py — The glue code

### What these files do in one sentence
factory.py knows HOW to create the arXiv client.
common.py makes sure it's only created ONCE and reused everywhere.

### Think of it like this
Imagine a coffee machine (ArxivClient):
- factory.py is the instruction manual for building it
- common.py is the rule that says "we only build one machine,
  then everyone shares it"

---

## factory.py

### What it does
One job: create and return an ArxivClient.

Steps:
1. Load settings from central config (things like base_url,
   timeout, rate limit delay etc.)
2. Pass those settings into ArxivClient()
3. Return the client

### What to remember
It's intentionally simple. The complexity lives in client.py.
factory.py just handles the "how do I set one up" question.

### Known issues (from code review)
- get_settings() might re-read config every time it's called.
  Should be cached with @lru_cache if it isn't already.
- No error handling if arxiv settings are missing from config.
- The middle variable is unnecessary:
    client = ArxivClient(...)  # this line
    return client              # could just be: return ArxivClient(...)

---

## common.py

### What it does
Creates ALL services (not just arXiv client) and caches them
so they're only initialized once per process.

### The services it creates
1. arxiv_client     — talks to arXiv API
2. pdf_parser       — reads and extracts text from PDFs
3. database         — connects to PostgreSQL
4. metadata_fetcher — fetches extra paper info (uses arxiv_client
                      and pdf_parser internally)
5. opensearch_client — connects to the search engine

### What @lru_cache does here
lru_cache is Python's built-in way of saying:
"run this function once, remember the result,
and return the same result every time after that."

So get_cached_services() only actually builds the services
the first time it's called. Every call after that gets
the already-built services back instantly.

### The important limitation
lru_cache only remembers things inside one running process.
Airflow runs each task in a SEPARATE process.
So the cache doesn't actually help between DAG tasks —
it only helps if multiple things inside the SAME task
call get_cached_services().

### What to remember
common.py is the single place where all services are
born. If you ever need to add a new service to the system,
this is one of the places you'd touch.

### Known issues (from code review)
- Return type Tuple[Any, Any, Any, Any, Any] is too vague.
  A NamedTuple would be clearer:
    services.opensearch_client  ← much better than
    arxiv, _, db, _, opensearch = get_cached_services()
- If one service fails to initialize (e.g. pdf_parser),
  ALL services fail, even ones that already succeeded.
- sys.path.insert(0, "/opt/airflow") is hardcoded and
  will break in any environment where Airflow is installed
  elsewhere.