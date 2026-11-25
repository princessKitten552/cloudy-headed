# Cloudy Headed

Self-hosted clone of Steam Cloud service to save your progresions in each game (serveur FastAPI + client Tauri).

>Step 3: **FastAPI server + Docker + history**. The client is coming soon.

## Server on local host

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export SAVESYNC_API_TOKEN="$(openssl rand -hex 32)"
export SAVESYNC_DATA_DIR=/tmp/savesync/data SAVESYNC_DB_DIR=/tmp/savesync/db
uvicorn app.main:create_app --factory --port 8000
```

## Server on docker (recomended)

```bash
cp .env.example .env
# Éditer .env : SAVESYNC_API_TOKEN (openssl rand -hex 32), PUID/PGID (id -u ; id -g),
# FORWARDED_ALLOW_IPS (IP du serveur Traefik)

mkdir -p data db          # à créer AVANT le premier démarrage, avec ton utilisateur
docker compose up -d --build
docker compose ps          # l'état doit passer à "healthy"
curl http://127.0.0.1:8000/health
docker compose logs -f savesync
```

- Archives are in `./data`,SQLite database is in `./db` (bind mounts: directories to save).
- Port 8000 is not encrypted : limit his acces to the reverse-proxy server's IP (firewall), or define `SAVESYNC_BIND` on LAN IP.
- If containers stop with « Cannot write to … » : `./data` or `./db` isn't in `PUID:PGID`: 
```bash
(`sudo chown -R $(id -u):$(id -g) data db`).
```
- Update : `git pull && docker compose up -d --build`.

Multi architecture image (amd64 + arm64), test:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64   # once
docker buildx build --platform linux/amd64,linux/arm64 ./server
```

The auto udate of the image will come with step 9.

## Tests

```bash
cd server && source .venv/bin/activate
pytest
```

## API (token : `Authorization: Bearer <token>`, exept `/health`)

| Method | Route | Job |
|---|---|---|
| GET | `/health` | server status (public) |
| GET | `/games` | games and last update |
| POST | `/games/{game_id}/upload` | multipart : `archive`, `sha256`, `modified_at` (ISO 8601 avec fuseau), `machine`, `steam_app_id` (optional) |
| GET | `/games/{game_id}/versions` | most recent history |
| GET | `/games/{game_id}/download?version=latest\|<id>` | zip archive (header `X-Content-SHA256`) |
| DELETE | `/games/{game_id}/versions/{version_id}` | delete a version |
| GET/PUT | `/settings` | `{"max_versions": n}` |

## Hisory keeping

After every succesful upload, the server only keep the `max_versions` most recent versions **of the game** and delete the old ones (database and files).

- Set the value insinde `PUT /settings` (shared across every machine). `SAVESYNC_DEFAULT_MAX_VERSIONS` is only until a new value is registered.
- Edit the value didn't delete anything imediatly: the purge is done on the next upload.
- A refused upload (wrong hash, corupted zip) didn't delete anything, and a purge error don't cancel an upload already saved (it's loged).

Errors looks like: `{"detail": {"code": "...", "message": "..."}}`.
