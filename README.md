# Shoe Visual Customizer

Prototype MVP for a shoe-only video-to-3D reconstruction and web visual customization workflow.

The system is split into three applications:

- **`backend/`**: Python FastAPI API server, SQLAlchemy models, Alembic migrations, local storage, Neon Postgres persistence, and async reconstruction/baking worker.
- **`mobile/`**: Flutter scanner app. Guided captures for shoe videos and metadata upload.
- **`frontend/`**: Vite + React web 3D editor. Loads shoe GLB models, offers surface snapping, and creates custom designs.
- **`docs/`**: Architecture, API contract, scan guidelines, and rollout guides.

## Local Pipeline Requirements

For real 3D reconstruction and decal baking, the backend host requires:
- `ffmpeg`
- `colmap`
- OpenMVS toolchain (`InterfaceCOLMAP`, `DensifyPointCloud`, `ReconstructMesh`, `RefineMesh`, `TextureMesh`)
- `blender` (v3.6+ or modern LTS recommended)

Configure paths in `backend/.env` with `FFMPEG_BIN`, `COLMAP_BIN`, `OPENMVS_BIN_DIR`, and `BLENDER_BIN`.

## Development Setup

### 1. Backend

The backend uses [uv](https://github.com/astral-sh/uv) for fast Python packaging.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Copy and configure the environment variables:
   ```bash
   cp .env.example .env
   ```
   *Note: Ensure `DATABASE_URL` is set to your Neon Postgres database instance.*
3. Install dependencies and sync virtual environment:
   ```bash
   uv sync
   ```
4. Run Alembic database migrations:
   ```bash
   uv run alembic upgrade head
   ```
5. Run the FastAPI development server:
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
6. Verify the server is running:
   ```bash
   curl http://localhost:8000/health
   ```

### 2. Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the Vite development server:
   ```bash
   npm run dev -- --host 0.0.0.0 --port 5173
   ```
4. Build the production bundle:
   ```bash
   npm run build
   ```

### 3. Mobile

1. Navigate to the mobile directory:
   ```bash
   cd mobile
   ```
2. Run the Flutter app with custom backend endpoint:
   ```bash
   flutter run --dart-define=BACKEND_BASE_URL=http://YOUR_BACKEND_HOST:8000
   ```

## Key Configuration Variables (`backend/.env`)

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | Neon Postgres connection string. |
| `DATABASE_AUTO_CREATE_TABLES` | Set `true` to auto-generate missing tables during FastAPI lifespan startup (fallback). |
| `BLENDER_BIN` | Path to the Blender executable (e.g. `C:\Program Files\Blender Foundation\Blender 3.6\blender.exe`). |
| `FFMPEG_BIN` | Path to the FFmpeg executable. |
| `COLMAP_BIN` | Path to the COLMAP executable. |
| `OPENMVS_BIN_DIR` | Path to the directory containing OpenMVS binaries. |
| `RECONSTRUCTION_MAX_THREADS` | Thread limit for photogrammetry pipeline (default `4`). |
| `RECONSTRUCTION_MIN_AVAILABLE_MEMORY_GB` | RAM safety threshold (default `4.0`). |
| `RECONSTRUCTION_MIN_FREE_STORAGE_GB` | Storage space safety threshold (default `8.0`). |

## Testing and Quality Checks

Run quality checks from the `backend/` directory:
- Run unit and integration tests:
  ```bash
  uv run pytest
  ```
- Run code formatting and linting check:
  ```bash
  uv run ruff check .
  ```

## Deployment

See [docs/vps-android-deployment.md](file:///F:/_FPT/_EXE101/ar-ai-exe/docs/vps-android-deployment.md) for Docker Compose setup, Android debugging instructions, and VPS server configuration.
