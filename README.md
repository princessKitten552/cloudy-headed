# SaveSync

Clone auto-hébergé de Steam Cloud pour les sauvegardes de jeux (serveur FastAPI + client Tauri).

> État : **phase 3 — serveur FastAPI + Docker + rétention des versions**. Le client vient dans les phases suivantes.

## Serveur : lancer en local

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export SAVESYNC_API_TOKEN="$(openssl rand -hex 32)"
export SAVESYNC_DATA_DIR=/tmp/savesync/data SAVESYNC_DB_DIR=/tmp/savesync/db
uvicorn app.main:create_app --factory --port 8000
```

## Serveur : Docker (recommandé)

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

- Les archives sont dans `./data`, la base SQLite dans `./db` (bind mounts : ce sont de simples dossiers à sauvegarder).
- **Traefik** (autre serveur) : faire pointer le domaine vers `http://IP_DU_HOMELAB:8000`. Le HTTPS est géré par Traefik.
- Le port 8000 est en HTTP clair : limiter son accès à l'IP du serveur Traefik (pare-feu), ou définir `SAVESYNC_BIND` sur une IP du LAN.
- Si le conteneur s'arrête avec « Cannot write to … » : `./data` ou `./db` n'appartient pas à `PUID:PGID` (`sudo chown -R $(id -u):$(id -g) data db`).
- Mise à jour : `git pull && docker compose up -d --build`.

Image multi-architecture (amd64 + arm64), test manuel :

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64   # une seule fois
docker buildx build --platform linux/amd64,linux/arm64 ./server
```

La publication automatique de l'image viendra avec la CI (phase 9).

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

## Rétention des versions

Après chaque upload réussi, le serveur ne garde que les `max_versions` versions les plus récentes **du jeu concerné** et supprime les plus anciennes (base de données et fichiers).

- La valeur se règle via `PUT /settings` (partagée par toutes les machines). `SAVESYNC_DEFAULT_MAX_VERSIONS` ne sert que tant qu'aucune valeur n'a été enregistrée.
- Modifier la valeur ne supprime rien immédiatement : l'excédent d'un jeu est purgé lors de son prochain upload.
- Un upload refusé (hash incorrect, zip invalide) ne supprime jamais rien, et une erreur de purge n'annule pas un upload déjà enregistré (elle est journalisée).

Les erreurs ont la forme `{"detail": {"code": "...", "message": "..."}}`.
