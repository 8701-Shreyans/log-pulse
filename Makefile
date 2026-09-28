.PHONY: dev test build up down sim-spike sim-recover aws-setup

# One-command local demo: backend + simulator + frontend (requires GNU make + bash)
dev:
	@echo "Start three terminals: make dev-backend | make dev-sim | make dev-frontend"

# Run local development servers (FastAPI backend + Vite frontend)
dev-backend:
	PYTHONPATH=backend python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

dev-sim:
	python -m backend.simulator.generate_logs --file ./data/app.log --rps 30

# Run full test suite
test:
	pytest -v

# Run Docker Compose demo
up:
	docker compose up --build

down:
	docker compose down -v

# Trigger simulation scenarios from CLI
sim-spike:
	python -c "import json; json.dump({'active': True, 'scenario': 'spike', 'error_ratio': 0.60, 'expires_at': 9999999999, 'duration_sec': 45}, open('./data/sim_control.json', 'w'))"

sim-recover:
	python -c "import json; json.dump({'active': False, 'scenario': 'normal', 'error_ratio': 0.02}, open('./data/sim_control.json', 'w'))"

# Setup AWS infrastructure
aws-setup:
	bash infra/aws-setup.sh
