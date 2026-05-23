# Android Usage and VPS Deployment

This guide deploys the current MVP E2E flow:

```mermaid
flowchart TD
    A["Android app login/register"] --> B["Record guided scan video"]
    B --> C["Upload MP4 + metadata to HTTPS API"]
    C --> D["FastAPI stores videos and metadata"]
    D --> E["Backend runs FFmpeg COLMAP OpenMVS Blender"]
    E --> F["Android receives webDesignUrl"]
    F --> G["Open https://domain/design?scanId=..."]
    G --> H["Web auto-loads scan and GLB"]
    H --> I["User designs and exports ZIP"]
```

## Android Device Usage

### Local LAN development

Use this only when your phone and laptop are on the same trusted Wi-Fi.

1. Find the laptop LAN IP, for example `192.168.1.20`.
2. Backend `.env` should allow the Vite origin and generate phone-openable web URLs:

```text
WEB_APP_BASE_URL=http://192.168.1.20:5173
CORS_ORIGINS=["http://192.168.1.20:5173","http://localhost:5173","http://127.0.0.1:5173"]
```

3. Run backend on all local interfaces:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. Run frontend on all local interfaces:

```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

5. Run the Android app against the laptop IP:

```powershell
cd mobile
flutter pub get
flutter run --dart-define=BACKEND_BASE_URL=http://192.168.1.20:8000
```

Do not use `127.0.0.1` on a physical Android phone. It points to the phone itself, not your laptop.

### VPS/production Android build

After the VPS is deployed with HTTPS, build the Android app against the public domain:

```powershell
cd mobile
flutter pub get
flutter build apk --release --dart-define=BACKEND_BASE_URL=https://your-domain.example.com
```

Install on your device:

```powershell
adb install -r build\app\outputs\flutter-apk\app-release.apk
```

For a quick debug install:

```powershell
flutter run --dart-define=BACKEND_BASE_URL=https://your-domain.example.com
```

## VPS Deployment Architecture

```mermaid
flowchart LR
    A["Internet"] -->|"80/443 only"| B["Caddy web container"]
    B -->|"/api and /health"| C["FastAPI backend container:8000"]
    B -->|"static files"| D["React dist"]
    C -->|"TLS outbound"| E["Neon Postgres"]
    C -->|"local volume or S3/R2"| F["Artifact storage"]
    C -->|"CPU-heavy local binaries"| G["FFmpeg COLMAP OpenMVS Blender"]
```

Public host ports:

| Port | Public? | Reason |
|---|---:|---|
| `22/tcp` or your custom SSH port | Yes | VPS administration only |
| `80/tcp` | Yes | HTTP redirect and Let's Encrypt ACME challenge |
| `443/tcp` | Yes | Public HTTPS app/API |
| `8000/tcp` | No | FastAPI is internal Docker network only |
| `5173/tcp` | No | Vite dev server is never used in production |
| `5432/tcp` | No | Postgres is Neon-managed, not hosted on this VPS |

## Backend Reconstruction Toolchain Image

The backend Docker image now builds and ships the reconstruction runtime instead of relying on manual VPS installs:

```mermaid
flowchart TD
    A["docker compose build backend"] --> B["Build OpenMVS v2.4.0 from source"]
    B --> C["Copy OpenMVS binaries to /opt/openmvs/bin"]
    A --> D["Install Debian packages"]
    D --> E["ffmpeg colmap blender runtime libraries"]
    C --> F["FastAPI container starts"]
    E --> F
    F --> G["/api/system/reconstruction-readiness"]
    G --> H{"ready?"}
    H -->|"yes"| I["mobile uploads can process immediately"]
    H -->|"no"| J["scan is preserved, status toolchain_unavailable"]
```

Build characteristics:

| Concern | Docker/VPS self-contained toolchain |
|---|---|
| Scalability | Good for one CPU worker per VPS. Split reconstruction into a separate worker service before high traffic. |
| Maintainability | Stronger than manual installs because binary versions are pinned in `backend/Dockerfile` and Compose. |
| Security | Backend port remains private. Review OpenMVS AGPL-3.0 obligations before commercial network use. |
| Performance | CPU-only reconstruction is slow but predictable. Use 4+ vCPU, 12-16 GB RAM, and 40+ GB free disk for practical builds. |
| User experience | Mobile can upload scans to one HTTPS API; users see queued, processing, completed, failed, or toolchain_unavailable status. |

The first build can take tens of minutes because OpenMVS compiles from source and Blender/COLMAP pull large system dependencies.
## VPS Setup Steps

1. Point DNS `A` record to the VPS public IP:

```text
your-domain.example.com -> VPS_PUBLIC_IP
```

2. Install Docker Engine and Docker Compose plugin on the VPS.

3. Copy the repository to the VPS.

4. Create public Compose env:

```bash
cp deploy/.env.example deploy/.env
nano deploy/.env
```

Example:

```text
APP_DOMAIN=your-domain.example.com
ACME_EMAIL=admin@your-domain.example.com
```

5. Create backend secret env:

```bash
cp deploy/backend.env.example deploy/backend.env
nano deploy/backend.env
```

Required production edits:

```text
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=["https://your-domain.example.com"]
WEB_APP_BASE_URL=https://your-domain.example.com
DATABASE_URL=postgresql://USER:PASSWORD@HOST-POOLER.neon.tech/neondb?sslmode=require&channel_binding=require
DATABASE_AUTO_CREATE_TABLES=false
JWT_SECRET_KEY=<random secret from openssl rand -base64 48>
ENABLE_DEMO_AUTH=false
```

Generate JWT secret:

```bash
openssl rand -base64 48
```

6. Configure firewall on the VPS.

If SSH runs on port 22:

```bash
sudo bash deploy/ufw-allow-web.sh
```

If SSH runs on a custom port, for example `2222`:

```bash
sudo SSH_PORT=2222 bash deploy/ufw-allow-web.sh
```

Also mirror the same rule set in your cloud provider firewall/security group:

```text
Allow: SSH_PORT/tcp from your trusted IP if possible
Allow: 80/tcp from 0.0.0.0/0
Allow: 443/tcp from 0.0.0.0/0
Deny: 8000, 5173, 5432, all other inbound ports
```

7. Build and start. The first backend image build is intentionally heavy because it compiles OpenMVS:

```bash
DOCKER_BUILDKIT=1 docker compose --env-file deploy/.env up -d --build
```

8. Verify:

```bash
docker compose ps
curl -I https://your-domain.example.com
curl https://your-domain.example.com/health
curl https://your-domain.example.com/api/system/reconstruction-readiness
```

9. View logs when needed:

```bash
docker compose logs -f web
docker compose logs -f backend
```

## Update Deployment

```bash
git pull
DOCKER_BUILDKIT=1 docker compose --env-file deploy/.env up -d --build
```

The backend container runs `alembic upgrade head` before starting Uvicorn. Rebuild after changing `backend/Dockerfile`, `OPENMVS_REF`, or reconstruction dependencies.

## Storage Options

| Option | Scalable | Maintainable | Security | Performance | UX |
|---|---|---|---|---|---|
| Local Docker volume | OK for one VPS | Simplest | API still protects files, but tied to one server | Fast on same VPS | Good for MVP |
| S3/R2-compatible | Best for growth | Adapter already exists | Better isolation and lifecycle control | Better for large downloads | Better reliability |
| Public bucket files | Scales | Simple serving | Weak unless every object is non-sensitive | Fast with CDN | Risky for user uploads |

Recommended path:

- Start with `STORAGE_BACKEND=local` for first VPS validation.
- Move to `STORAGE_BACKEND=s3` when scans/exports become valuable or traffic grows.

## Security Checklist

- `deploy/backend.env` and `deploy/.env` must never be committed.
- `ENABLE_DEMO_AUTH=false` in production.
- `JWT_SECRET_KEY` must be random and at least 32 bytes.
- `CORS_ORIGINS` must list only the production HTTPS origin.
- Do not open backend port `8000` publicly.
- Do not open Vite port `5173` publicly.
- Do not host Postgres on the VPS for this app; use Neon outbound TLS only.
- Keep VPS packages and Docker updated.
- Prefer SSH key auth and disable password SSH login.