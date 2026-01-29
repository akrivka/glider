# Repository Guidelines

## Project Structure & Module Organization
- `glider-web/` contains the SvelteKit frontend. Core code lives in `glider-web/src/` with routes in `glider-web/src/routes/` and shared components/utilities in `glider-web/src/lib/`.
- `glider-operator/` contains the Python backend/workers. Main package code is in `glider-operator/glider/` with integrations and scheduler logic under `glider-operator/glider/integrations/` and `glider-operator/glider/sync/`.
- `docker-compose.yaml` defines local dev services (frontend, worker, SurrealDB, Surrealist UI).
- `specs/` and `sources/` hold research notes and supporting materials.

## Build, Test, and Development Commands
- `docker compose up --build` starts the full local stack (SurrealDB, Surrealist UI, frontend, worker).
- `cd glider-web && npm install` installs frontend dependencies.
- `cd glider-web && npm run dev` runs the SvelteKit dev server.
- `cd glider-web && npm run build` builds the production frontend; `npm run preview` serves it.
- `cd glider-operator && uv sync` installs backend dependencies; `python -m glider.scheduler` runs the worker process.

## Coding Style & Naming Conventions
- Frontend formatting uses Prettier with tabs, single quotes, and 100-char lines (see `glider-web/.prettierrc`). Run `npm run format` or `npm run lint` in `glider-web/`.
- Frontend linting uses ESLint; keep file names and route folders aligned with SvelteKit conventions.
- Backend formatting/linting uses Ruff with 100-char lines and double quotes; type checks use `ty` (see `glider-operator/pyproject.toml`). Prefer 4-space indentation in Python.

## Testing Guidelines
- Frontend unit tests use Vitest (`npm run test:unit`) and live alongside code; e2e tests use Playwright in `glider-web/e2e/*.test.ts` (`npm run test:e2e`).
- There are no backend tests yet; if you add them, document the framework and commands here.

## Commit & Pull Request Guidelines
- Recent commit history uses short, lowercase, imperative subjects without prefixes (e.g., "separate scripts"). Follow that style.
- PRs should include a brief summary, testing notes (commands run), and screenshots for UI changes when applicable.

## Configuration & Secrets
- Local secrets live in `glider-operator/secrets/`; do not commit secret files.
- Service connection details are configured via environment variables in `docker-compose.yaml` and `glider-operator/config.toml`.
