# Mini Market API

FastAPI REST API for Mini Market supermarket website.

## Setup Instructions

### 1. Install Dependencies

(Optional) Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Database Setup with Docker Compose

Start all services (Postgres, NocoDB, and the FastAPI app):
```bash
docker compose up -d
```

This will start:
- **Postgres** on port `5432` with database `minimarket`
- **NocoDB** admin UI on port `8080`
- **FastAPI app** on port `8000`

To build and start only the database services (without the app):
```bash
docker compose up -d postgres nocodb
```

### 3. Access NocoDB Admin UI

Open NocoDB in your browser:
```
http://localhost:8080
```

#### Adding Postgres as a Data Source in NocoDB

1. Sign up/login to NocoDB (first time setup)
2. Click "Add Project" or "New Project"
3. Select "Postgres" as the data source
4. Enter connection details:
   - **Host**: `postgres` (use the service name from docker-compose)
   - **Port**: `5432`
   - **Database**: `minimarket`
   - **User**: `minimarket`
   - **Password**: `minimarket`
5. Click "Test Connection" and then "Save"

### 4. Environment Variables

Copy `.env.example` to `.env` and update the values:
```bash
cp .env.example .env
```

Edit `.env` and set:
- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET_KEY`: A secure random string for JWT token signing
- `FRONTEND_ORIGIN`: Your frontend URL (default: http://localhost:5173)

### 5. Run the Server

**Option A: Run with Docker (recommended)**
```bash
docker compose up -d app
# Or build and start: docker compose up -d --build app
```

**Option B: Run locally**
```bash
uvicorn app:app --reload --port 8000
```

**Note**: When running locally, make sure Postgres is running via Docker Compose first.

**CORS Configuration**: The API is configured to allow requests from the frontend origin specified in `FRONTEND_ORIGIN` environment variable (default: `http://localhost:5173`). This enables the Vite dev server to make API calls.

## Frontend Integration

- React dev server: http://localhost:5173
- If you use a Vite proxy (recommended), the UI can call `/api/...` directly.

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Authentication

This API implements a simple in-memory user system with token-based auth.
- Register: `POST /api/auth/register`
- Login: `POST /api/auth/login` → returns Bearer token
- Use: `Authorization: Bearer <token>`

**Note**: Currently, storage is in-memory (resets when the server restarts). Migrate to Postgres for persistence.

## Docker Commands

- Start all services: `docker compose up -d`
- Start specific service: `docker compose up -d <service_name>`
- Build and start: `docker compose up -d --build`
- Stop services: `docker compose down`
- View logs: `docker compose logs -f [service_name]`
- Rebuild app: `docker compose build app`
- Stop and remove volumes: `docker compose down -v` (⚠️ deletes data)

### Building the Docker Image

To build the app image manually:
```bash
docker build -t minimarket-api .
```

To run the container manually:
```bash
docker run -p 8000:8000 --env-file .env minimarket-api
```
