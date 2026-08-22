.PHONY: setup api web demo test docker docker-demo docker-down

setup:            ## one-time: create the venv and install both stacks
	python3 -m venv .venv && .venv/bin/pip install -q -r backend/requirements.txt
	cd frontend && npm install --include=dev
	cp -n .env.example .env || true

api:              ## run the API on :8000 (OpenAPI docs at /docs)
	.venv/bin/uvicorn backend.app.main:app --reload --port 8000

web:              ## run the React console on :5173
	cd frontend && npm run dev

demo:             ## push simulated application traffic through the API
	.venv/bin/python -m backend.data.simulate --n 60 --rate 5 --ring

test:             ## run the test suite
	.venv/bin/python -m pytest backend/tests -q

docker:           ## run everything in containers - open http://localhost:8000
	docker compose up --build

docker-demo:      ## push simulated traffic through the containerised API
	docker compose exec app python -m backend.data.simulate --n 60 --rate 5 --ring \
		--password "$$SEED_ANALYST_PASSWORD"

docker-down:      ## stop the containers (add -v to also wipe the data)
	docker compose down
