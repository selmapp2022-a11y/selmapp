# selmapp (repository) — serves **https://selmapp.com**

**Read this before deploying anything.** The repository name and the domain it
serves do not match.

| | |
|---|---|
| This repository builds | **https://selmapp.com** — the web application |
| Hosted on | DigitalOcean App Platform, app `selmapp` (web services + job + static site + Postgres + Valkey) |
| Contents | `backend/` (FastAPI), `frontend/`, `nginx/` |

The marketing site at **https://selmapp.ca** is built from the repository named
**`selmapp.com`**, not this one.

Live legal documents are served by the application, not as static files:
`/privacy` and `/terms`. The `*.html` files in `frontend/` are not the
documents users reach.
