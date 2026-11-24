# SaveSync

Clone auto-hébergé de Steam Cloud pour les sauvegardes de jeux (serveur FastAPI + client Tauri).

> État : **phase 1 — serveur FastAPI + tests**. Docker, rétention et client viennent dans les phases suivantes.

## Serveur : lancer en local

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export SAVESYNC_API_TOKEN="$(openssl rand -hex 32)"
export SAVESYNC_DATA_DIR=/tmp/savesync/data SAVESYNC_DB_DIR=/tmp/savesync/db
uvicorn app.main:create_app --factory --port 8000
```

## Tests

```bash
cd server && source .venv/bin/activate
pytest
```

## API (jeton : `Authorization: Bearer <token>`, sauf `/health`)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health` | état du serveur (public) |
| GET | `/games` | jeux et dernière version |
| POST | `/games/{game_id}/upload` | multipart : `archive`, `sha256`, `modified_at` (ISO 8601 avec fuseau), `machine`, `steam_app_id` (optionnel) |
| GET | `/games/{game_id}/versions` | historique, plus récent d'abord |
| GET | `/games/{game_id}/download?version=latest\|<id>` | archive zip (en-tête `X-Content-SHA256`) |
| DELETE | `/games/{game_id}/versions/{version_id}` | supprime une version |
| GET/PUT | `/settings` | `{"max_versions": n}` |

Les erreurs ont la forme `{"detail": {"code": "...", "message": "..."}}`.
