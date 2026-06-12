# Messy Real-Estate Ingestion & De-duplication Service

A Django & Django REST Framework service that ingests messy free-text real estate listings (Arabic/English), extracts structured data using the Groq LLM API, normalizes phone numbers, programmatically de-duplicates listings, and stores the results in PostgreSQL. It also provides structured search and natural-language search capabilities.

---

## Technical Stack
- **Framework**: Django & Django REST Framework (DRF)
- **Database**: PostgreSQL (via `psycopg` driver)
- **LLM Engine**: Groq API (OpenAI-compatible client with `llama-3.3-70b-versatile` or local mock fallback)
- **Deployment**: Docker & Docker Compose
- **Testing**: Django standard `TestCase` (configured to support running against a local SQLite fallback for fast local testing)

---

## How to Run the Service

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- A **Groq API Key** (optional, to run live LLM parsing). If you don't have one, the service automatically falls back to a **local rule-based mock extractor** that matches the sample listings and parses queries, allowing you to test everything end-to-end out-of-the-box.

### Step 1: Environment Configuration
Create a `.env` file in the root directory (or copy the existing one):
```bash
# In docker-compose, the database host is 'db'. Locally, it would be 'localhost'.
DATABASE_URL=postgresql://postgres:postgres@db:5432/listings_db

# (Optional) Groq configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### Step 2: Build and Run with Docker Compose
Run the following command in the project root to start the PostgreSQL database and the web service:
```bash
docker compose up --build
```
This command will:
1. Spin up a PostgreSQL container and wait until it is healthy.
2. Build the Django container.
3. Automatically run database migrations.
4. Launch the web server on `http://localhost:8001`.

---

## How to Run Tests

### Running Tests Locally (Fastest)
You can run the test suite locally using a temporary SQLite database without launching Docker. In PowerShell (Windows):
```powershell
$env:DATABASE_URL="sqlite:///db.sqlite3"; python manage.py test
```
In Bash (Linux/macOS):
```bash
DATABASE_URL="sqlite:///db.sqlite3" python manage.py test
```

### Running Tests Inside Docker
To run tests inside the active Docker container:
```bash
docker compose exec web python manage.py test
```

---

## De-duplication Rule ("Same Property")

### Our Rule
I define the **same property** from the **same contact** as:
1. **Same normalized contact phone**: The phone number is normalized to international standard (`+9665XXXXXXXX`).
2. **Same normalized city**: City names are case-insensitive and stripped of whitespace (e.g. "Dammam" matches "dammam").
3. **Same normalized property type**: The property type extracted by the LLM (e.g. "industrial land", "warehouse", "villa", "office", "commercial land").
4. **Same area (m²)**: Matches with a **±1 m² tolerance** to handle extraction/formatting noise or minor rounding differences across posts.

### Why this rule?
- **Contact Phone** identifies the owner/agent.
- **City, Property Type, and Area** collectively act as a unique composite key. It is highly improbable that the same contact would post two *different* properties in the same city of the exact same type with the exact same size (e.g., two different industrial lands of exactly 1250 m² in Dammam).
- The **±1 m² tolerance** on the area is crucial. Messy WhatsApp messages often represent the same property with slight rounding errors (e.g., 1250 m² vs 1251 m²) or the LLM might parse a number slightly differently.
- **Implementation**: To support the ±1 m² range check securely without race conditions, we perform a programmatic check inside a Django database transaction. We lock matching candidate rows using `select_for_update()` and look for an area in `[extracted_area - 1.0, extracted_area + 1.0]`. If found, we update the existing listing's price, transaction type, raw text, and timestamps instead of creating a duplicate.

---

## Tradeoffs & Future Scope

### Framework Tradeoff: Why Django/DRF despite FastAPI being preferred?
For high-performance ingestion microservices, **FastAPI** is generally preferred due to its asynchronous nature, low latency, and native support for Pydantic models. However, we chose **Django & Django REST Framework (DRF)** for this service due to several key factors:
1. **Batteries-Included ORM & Migrations**: Django ORM provides a mature and secure way to handle transactions (`transaction.atomic`) and row-level database locking (`select_for_update`) which are critical for our de-duplication safety against race conditions. Setting this up securely in FastAPI with SQLAlchemy or Tortoise ORM requires significant boilerplate.
2. **Schema & Migration Management**: Django's built-in migration system is unmatched. It handles schema evolution safely out-of-the-box, ensuring our composite indexes and model fields are correctly managed on PostgreSQL.
3. **Out-of-the-box Admin Dashboard**: Django provides a built-in admin panel which allows administrators or reviewer teams to instantly search, filter, view, and manually resolve duplicates in a user-friendly UI without writing a front-end.
4. **DRF Ecosystem**: DRF provides robust serialization, field validation, and clean error handling, which integrates seamlessly with Django models.

### What was cut and why?
- **Authentication & Authorization**: Omitted because the service is designed as an internal ingestion microservice; keeping it simple makes it easier to inspect the core business logic.
- **Strict Database Unique Constraints**: A database-level unique constraint on `area` is impossible due to the ±1 m² tolerance requirement (which requires range queries). We instead implemented row locking (`select_for_update()`) to ensure transactional safety during concurrent imports.

### Future Improvements (What would be improved later):
- **Neighborhood/District Extraction**: Extract neighborhood/district data (e.g. "حي اليرموك" in الخبر) using the LLM to refine the de-duplication rules.
- **Asynchronous Ingestion Pipeline**: Ingest requests, return an immediate acknowledgment (`202 Accepted` with a job ID), and offload the LLM extraction and de-duplication to a Celery task or Redis Queue worker to prevent API requests from blocking during LLM calls.
- **Semantic/Vector Duplication Check**: Use text embeddings on the raw text and spatial boundaries to de-duplicate listings that don't match strict area bounds but describe the same physical location.

---

## Sample API Requests

Use these `curl` commands to interact with the API endpoints.

### 1. Ingest Messy Listings (POST `/listings`)

#### Listing 1 (Industrial Land - Inserts new row)
```bash
curl -X POST http://localhost:8001/listings \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "للبيع أرض صناعية بالدمام المنطقة الصناعية الثانية، المساحة ١٢٥٠ متر، السعر ٢٫٨ مليون ريال قابل للتفاوض. للتواصل: ٠٥٥١٢٣٤٥٦٧"}'
```
*Expected response action: `"inserted"`.*

#### Listing 2 (Duplicate Industrial Land - Updates Listing 1 instead of duplicating)
```bash
curl -X POST http://localhost:8001/listings \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "أرض صناعية الدمام ١٢٥٠م للبيع 2800000 — جوال 0551234567"}'
```
*Expected response action: `"updated"` (updates the row from Listing 1, database count remains 1).*

#### Listing 3 (Warehouse for Rent - Inserts new row)
```bash
curl -X POST http://localhost:8001/listings \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "مستودع لإليجار بالدمام، مساحة ٨٠٠ متر، اإليجار السنوي ١٥٠ ألف. الرقم 966500112233+"}'
```
*Expected response action: `"inserted"`.*

#### Listing 4 (Villa in Khobar - Inserts new row)
```bash
curl -X POST http://localhost:8001/listings \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "للبيع فيال في الخبر حي اليرموك مساحة ٤٠٠ متر السعر مليون و٢٠٠ ألف ريال، التواصل واتساب 0539988776"}'
```
*Expected response action: `"inserted"`.*

---

### 2. Search Listings (GET `/listings/search`)

#### Search for all properties in Dammam
```bash
curl "http://localhost:8001/listings/search?city=Dammam"
```

#### Search for properties with max price of 2,000,000 SAR
```bash
curl "http://localhost:8001/listings/search?max_price=2000000"
```

#### Search for properties in Dammam with min area of 1000 m²
```bash
curl "http://localhost:8001/listings/search?city=Dammam&min_area=1000"
```

---

### 3. Natural-Language Search (GET `/listings/match`)

#### Query: "أبغى أرض صناعية بالدمام تحت ٣ مليون" (I want an industrial land in Dammam under 3 million)
```bash
curl "http://localhost:8001/listings/match?q=%d8%a3%d8%a8%d8%ba%d9%89%20%d8%a3%d8%b1%d8%b6%20%d8%b5%d9%86%d8%a7%d8%b9%d9%8a%d8%a9%20%d8%a8%d8%a7%d9%84%d8%af%d9%85%d8%a7%d9%85%20%d8%aa%d8%ad%d8%aa%20%d9%a3%20%d9%85%d9%84%d9%8a%d9%88%d9%86"
```
*Expected response will output the filters parsed by the LLM (`"city": "Dammam"`, `"property_type": "industrial land"`, `"max_price": 3000000.0`) and the matching records.*

