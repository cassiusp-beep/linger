PY ?= .venv/bin/python
.PHONY: setup models check mock cache cache-rules eval eval-local dev pull-data
setup:            ## one-time laptop setup
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	@test -f .env || (cp .env.example .env && echo "Created .env. Fill in WANDB_API_KEY and WANDB_TEAM.")
models:           ## list W&B serverless models
	$(PY) scripts/check_llm.py --models
check:            ## one live LLM call + Weave
	$(PY) scripts/check_llm.py
mock:             ## regenerate mock street footage
	$(PY) scripts/make_mock.py
cache:            ## run the agent with the LLM, save the demo cache
	$(PY) scripts/build_cache.py
cache-rules:      ## run the agent rules-only (no W&B)
	LINGER_LLM=0 $(PY) scripts/build_cache.py
eval:             ## Weave evaluation: the agent never overclaims
	$(PY) scripts/eval_weave.py
eval-local:       ## same evaluation, rules-only, no W&B
	LINGER_LLM=0 $(PY) scripts/eval_weave.py --local
dev:              ## serve at http://localhost:8000/app/
	$(PY) -m uvicorn app.main:app --reload --port 8000
pull-data:        ## get the latest segments.json from the VM teammate
	git pull --rebase && $(PY) scripts/build_cache.py
