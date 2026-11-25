COMPOSE := docker compose

.PHONY: up down build logs test dev-backend dev-frontend clean

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

test:
	cd backend && .venv/bin/pytest -v

dev-backend:
	cd backend && DATABASE_URL="sqlite:///./data/app.db" .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev -- --port 3000

clean:
	$(COMPOSE) down -v --remove-orphans
