# Sovereign AI Workbench

## Required Ollama models

Pull at least one text model and one vision model so the router has
something to select for each task type:

```
ollama pull qwen3:8b          # general reasoning / coding / documents
ollama pull llava             # vision: images, handwritten notes, engineering drawings
ollama pull nomic-embed-text  # embeddings
```

Any other pulled model matching a family in
`backend/routing/service.py` (`llava`, `bakllava`, `llama3.2-vision`,
`qwen2.5vl`, `qwen2-vl`, `minicpm-v`, `moondream`, etc.) is picked up
automatically — no config changes needed.

## LAN deployment (internal organisation network)

SentinelVault is designed to run on ONE server machine inside your
organisation's network - it is not meant to be exposed to the public
internet. Other employee/manager/admin devices reach it over the same
LAN/Wi-Fi, by IP address, and still go through normal login + RBAC.
Ollama and the local models run only on the server machine; client
devices need nothing installed beyond a browser.

### 1. Start the backend (on the server machine)

```
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` is what makes this reachable from other devices -
without it uvicorn only accepts connections from the server machine
itself. (The Docker image already does this: see `backend/Dockerfile`'s
`CMD`, and `docker-compose.yml`.)

### 2. Start/build the frontend (on the server machine)

Development (hot reload):

```
cd frontend
npm install
npm run dev
```

`vite.config.ts` already sets `host: true`, so this binds to `0.0.0.0`
too and is reachable from other LAN devices on port 5173. Its `/api`
proxy target (`http://localhost:8000`) is resolved by the Vite process
itself, which runs on the server machine right next to the backend - so
it still correctly reaches the backend no matter which LAN device the
browser making the request is on. This is also why the frontend's own
API calls (`frontend/src/services/api.ts`) use a relative `/api` base
URL rather than a hardcoded host: the browser always calls back to
whatever address it loaded the page from.

Production build (served by nginx via Docker, recommended for regular
use - see `docker-compose.yml` / `frontend/Dockerfile` /
`frontend/nginx.conf`):

```
docker compose up -d --build
```

This serves the frontend on port 3000 and proxies `/api` to the backend
container internally - LAN devices only ever need to reach port 3000.

### 3. Find the server machine's LAN IPv4 address

- Linux: `hostname -I` or `ip addr show`
- macOS: `ipconfig getifaddr en0` (or `en1` for Wi-Fi on older Macs)
- Windows: `ipconfig` and read the `IPv4 Address` line under your
  active adapter

Look for an address in a private range: `192.168.x.x`, `10.x.x.x`, or
`172.16.x.x`-`172.31.x.x`.

### 4. URL to open from another device on the same LAN

- Dev mode: `http://SERVER-LAN-IP:5173`
- Docker/production mode: `http://SERVER-LAN-IP:3000`

Do not use `localhost` or `127.0.0.1` from another device - that
always means the device's own computer, never the server.

### 5. Firewall rules

On the server machine, allow inbound TCP connections from your LAN
subnet on whichever port you're serving from:

- Port 5173 (dev) or 3000 (Docker/production) - required, this is what
  employees connect to.
- Port 8000 (backend) - only needed if you want to hit the API/docs
  (`/docs`) directly from another device; normal use goes through the
  proxy on 5173/3000 and never touches 8000 from outside the server.
- Port 11434 (Ollama) should NOT be opened to the LAN - the backend is
  the only thing that needs to reach it, over `localhost` on the server
  itself. Ollama never needs to run on, or be reachable from, client
  devices.

Example (Linux, ufw): `sudo ufw allow from 192.168.1.0/24 to any port 3000`

### 6. Verify another device can connect

From a second device on the same network:

1. Open `http://SERVER-LAN-IP:5173` (or `:3000` for the Docker build).
2. The login page should load. Log in with an Admin, Manager, and
   Employee account and confirm each sees the correct RBAC-scoped
   documents/pages.
3. Open AI Workbench and send a message - confirm it reaches the
   server's Ollama and responds.
4. Open a document-related question and confirm RAG results are
   correctly scoped to that account's permissions.

If step 1 fails, it's almost always the firewall (step 5) or the
server binding to `127.0.0.1` instead of `0.0.0.0` (step 1/2).

### CORS

Both the dev proxy and the production nginx proxy serve the frontend
and `/api` on the exact same origin, so the browser never makes a
cross-origin request in normal use - `CORS_ORIGINS` in `.env` doesn't
need to change for the setups above. It only matters if you ever call
the backend directly from a different origin (e.g. a separate static
file server); if so, add that origin's LAN URL to `CORS_ORIGINS` in
`.env` (see the comment there for the exact format). Do not set it to
allow all origins.
