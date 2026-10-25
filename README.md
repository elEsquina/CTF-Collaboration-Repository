# ACM CTF Track Challenge Tool

A private, lightweight challenge library for a team. Upload, browse, search, edit, and download CTF challenges. React/Vite/Tailwind frontend, FastAPI/SQLAlchemy backend, SQLite metadata, and local ZIP storage. There are no accounts, scores, challenge execution, or automatic Docker deployments.

## Docker Compose

Prerequisite: Docker Engine/Desktop with Docker Compose **2.24+**. From the repository root:

```bash
docker compose up
```

The first run builds both images. Open **http://localhost:8080**. On first startup, the backend prints `First-start shared password: ...` in the terminal. The generated password and session secret are saved in the Docker volume and reused on subsequent starts. To see the first-start message again: `docker compose logs backend`.

If `server/.env` already exists, Compose loads your configured password, session secret, and upload limits instead. No password or other secret is built into either image. Missing credentials are generated automatically. For a colleague accessing a different hostname, set `ALLOWED_ORIGINS` to the browser's exact origin before starting, for example:

```bash
ALLOWED_ORIGINS=http://ctf.internal:8080 docker compose up
```

Nginx serves the built React application and proxies `/api` to FastAPI under the same origin. Only port 8080 is exposed; the backend is internal. Both containers run as non-root users. Compose waits for the database-backed backend health check before starting the frontend.

```bash
docker compose up -d          # run in the background
docker compose logs -f       # follow logs
docker compose down          # stop; retain uploaded challenges and credentials
docker compose up --build    # rebuild after source/dependency changes
```

The named `repository-data` volume holds `/data/ctf.db`, `/data/challenges/`, and `/data/.env` inside the backend container. Container recreation and `docker compose down` preserve it. **`docker compose down -v` deletes the repository and its credentials.** Local development data in `server/ctf.db` and `server/challenges/` is separate and is not imported automatically. Keep one backend container/worker.

To locate storage or back up a stopped repository:

```bash
docker compose exec backend ls -la /data
docker compose stop backend
docker compose cp backend:/data ./repository-backup
docker compose start backend
```

The backup includes private flags and credentials. Restore by copying the backup's contents into `/data` with the backend stopped, preserving ownership for UID/GID 10001. For HTTPS behind another proxy, enable `COOKIE_SECURE=true` in `server/.env` and include the external HTTPS origin in `ALLOWED_ORIGINS`.

Compose verification passed: both images built, both health checks passed, and login, Docker/static uploads, edits, rejected replacements, downloads, logout, and persistence across backend container recreation worked through Nginx.

## Local setup

Prerequisites: Python 3.11+ with `venv`, Node.js 20.19+ (or 22.12+), and npm. Run commands from this repository's root.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.lock.txt
npm ci --prefix frontend
```

`requirements.lock.txt` records the versions verified during development. `requirements.txt` contains the direct dependency ranges.

Create `server/.env` with a password you choose and a generated secret. This command prompts without echoing the password, generates the session secret, and refuses to overwrite an existing configuration:

```bash
python - <<'PY'
import getpass
import json
import secrets
from pathlib import Path
password = getpass.getpass('Shared repository password: ')
if not password:
    raise SystemExit('A nonempty password is required.')
with Path('server/.env').open('x') as env:
    env.write('CTF_SHARED_PASSWORD=' + json.dumps(password) + '\n')
    env.write('SESSION_SECRET=' + secrets.token_hex(32) + '\n')
print('Created server/.env')
PY
```

Alternatively, copy `server/.env.example` to `server/.env` and replace both placeholder secrets. Keep `.env` private; it is ignored by Git. Backend startup fails clearly if required configuration is missing.

Terminal 1, from the repository root:

```bash
source .venv/bin/activate
uvicorn server.main:create_app --factory --reload --reload-dir server --host 127.0.0.1 --port 8000
```

Terminal 2, from the repository root:

```bash
npm run dev --prefix frontend -- --port 5173
```

Open **http://localhost:5173** and enter your shared password. Vite proxies `/api` to port 8000; the browser uses one origin for cookies and API calls. FastAPI documentation is at http://127.0.0.1:8000/docs. Use one backend worker; archive mutations are serialized within that process.

## Authentication and configuration

All colleagues use the same password and have the same access. The backend compares the password using a timing-safe comparison and issues a signed HTTP-only, SameSite=Lax session cookie. Sessions expire after 12 hours by default. Logout clears the browser cookie. The password and flag are never stored in browser localStorage or sessionStorage. A session CSRF token is kept in frontend memory and required on authenticated writes; state-changing browser requests also require an allowed Origin. This follows [Starlette's session cookie configuration](https://starlette.dev/middleware/#sessionmiddleware).

Configuration is loaded from `server/.env` regardless of the shell's current directory. Environment variables override `.env`.

| Variable | Default / purpose |
| --- | --- |
| `CTF_SHARED_PASSWORD` | Required shared password |
| `SESSION_SECRET` | Required random secret, at least 32 characters; keep stable across restarts |
| `COOKIE_SECURE` | `false`; set `true` when serving through HTTPS |
| `SESSION_MAX_AGE` | `43200` seconds |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173`; comma-separated, no spaces |
| `MAX_UPLOAD_BYTES` | 50 MiB per ZIP |
| `MAX_EXTRACTED_BYTES` | 250 MiB per archive |
| `MAX_FILE_BYTES` | 100 MiB per extracted file |
| `MAX_ZIP_MEMBERS` | 5,000 archive entries |
| `MAX_COMPRESSION_RATIO` | 200 per file |
| `DATA_DIR` | Backend directory; optional isolated data directory for tests/development |

The entire HTTP request is additionally bounded to the ZIP limit plus 1 MiB of multipart overhead, including requests without Content-Length. No CORS bypass is necessary with the Vite proxy. For an internal HTTPS host, serve the frontend and `/api` under the same origin, add that origin to `ALLOWED_ORIGINS`, and enable secure cookies.

## ZIP layouts

Any category can be Docker or static; category does not determine deployment requirements.

Docker challenges require a `Dockerfile`, `compose.yaml`, `compose.yml`, `docker-compose.yml`, or `docker-compose.yaml`, plus a `dist/` directory. Both must be at the archive root or inside one common enclosing folder:

```text
my-challenge/                  # enclosing folder is optional
├── Dockerfile                 # or a supported Compose filename
├── dist/
│   └── player-files.txt
└── src/
    └── app.py
```

Static challenges can contain any safe file structure; neither Docker configuration nor `dist/` is required. Explicit empty `dist/` entries are accepted. Additional files are allowed. Original ZIP bytes and extracted relative paths are preserved, including enclosing folders.

Only stored and Deflate-compressed ZIPs are accepted. Invalid archives, traversal/absolute/Windows paths, symlinks, special files, encrypted entries, duplicate/conflicting paths, excessive compression ratios, and configured size/count/depth limits are rejected. Extraction streams bounded chunks and verifies CRCs. Python's [ZIP documentation](https://docs.python.org/3/library/zipfile.html) describes why inspecting untrusted members before extraction is necessary. Uploaded scripts and Docker files are never executed. Markdown descriptions render without raw HTML, with safe link handling; external images are displayed as alt text.

## Storage and editing

The backend creates its SQLite database and storage directory automatically:

```text
CTF_Challs/
├── frontend/
│   ├── src/
│   │   ├── components/        # layout helpers and shared challenge form
│   │   ├── pages/             # login, dashboard, submission, details, editing
│   │   ├── services/          # API client and data loading
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
├── server/
│   ├── main.py                # app factory and authenticated REST endpoints
│   ├── config.py / auth.py
│   ├── database.py / models.py / schemas.py / crud.py
│   ├── archive.py             # ZIP inspection and extraction
│   ├── Dockerfile / container.py # container build and first-start configuration
│   ├── requirements.txt / requirements.lock.txt
│   ├── .env.example
│   ├── tests/test_api.py
│   ├── ctf.db                 # generated at startup, ignored by Git
│   └── challenges/            # generated at startup, private
│       └── 001_challenge-name/
│           ├── original.zip
│           └── extracted/
├── compose.yaml               # frontend, backend, persistent volume
├── .dockerignore
├── .gitignore
└── README.md
```

Names are sanitized and prefixed by an autoincrementing database ID. Renaming metadata keeps the existing folder. Replacement uses an ID/name/random-suffix folder, validates/extracts first, commits the new pointer, and then removes the previous folder. Failed validation or database commits preserve the working archive and clean temporary uploads. Metadata-only edits retain the ZIP. Enabling Docker checks the current ZIP; select a compatible replacement in the same form if needed. Timestamps use UTC and retain timezone information after SQLite reads.

SQLite contains metadata, including flags, but no ZIP binaries. List responses omit flags; authenticated details include them. Challenge directories are never statically hosted. Back up the database and challenge directory together with the backend stopped.

## API

Successful JSON responses use `{"data": ...}`; the list also returns global `stats` unaffected by filters. Errors use `{"error": {"message": "..."}}`.

| Method | Path | Input |
| --- | --- | --- |
| POST | `/api/login` | JSON `{ "password": "..." }` |
| POST | `/api/logout` | CSRF header |
| GET | `/api/me` | Returns session and CSRF token |
| GET | `/api/challenges` | Optional `category=web&search=sql` |
| GET | `/api/challenges/{id}` | Full metadata including flag |
| POST | `/api/challenges` | Multipart `name`, `description`, `flag`, `category`, `requires_docker`, `archive` |
| PATCH | `/api/challenges/{id}` | JSON with changed metadata fields |
| PUT | `/api/challenges/{id}/archive` | Multipart `archive`; optional `metadata` containing a complete metadata JSON object, applied atomically |
| GET | `/api/challenges/{id}/download` | Original ZIP attachment |

Category values: `web`, `pwn`, `reverse-engineering`, `cryptography`, `forensics`, `osint`, `miscellaneous`. For authenticated writes send `X-CSRF-Token` from login or `/api/me`, alongside the cookie. FastAPI's generated OpenAPI schemas describe response types.

## Verification

```bash
source .venv/bin/activate
python -m pytest server/tests -q
npm test --prefix frontend
npm run build --prefix frontend
```

Verification result: **69 backend tests and 7 frontend API tests passed**, and the Vite production build succeeded. The installed Starlette version emits one test-client HTTPX deprecation warning; it does not affect the application.

Tests use temporary storage and an isolated SQLite database, without real `.env` credentials. They cover login/logout, private endpoints, CSRF/origin checks, Docker/static layouts, enclosing folders, unsafe/corrupt/encrypted ZIPs, size limits, filtering/search, metadata edits, archive replacement, rollback cleanup, downloads, and persistence after reconnecting.

Browser verification covered login errors, protected routes, Docker/static uploads, Markdown script protection, flag visibility, editing, rejected replacements, exact ZIP download checksums, search/filtering, session reloads, and logout. All five pages passed automated WCAG A/AA checks at 320, 390, 768, and 1440 pixels, with no horizontal overflow. A live backend process restart retained both challenge records and their ZIPs. Concurrent checks passed for 12 uploads and 25 live HTTP reads. npm and pip-audit found no known vulnerabilities in the locked dependencies at verification time. Automated accessibility checks do not replace a manual accessibility audit.

This is an internal repository with a shared password, no individual audit trail or session revocation list, and no login throttling. Run one backend process. An abrupt process or machine crash between filesystem and database operations can leave an unreferenced folder; handled operation failures clean up automatically. Backups, HTTPS termination, and public production hosting are outside this application's scope.
