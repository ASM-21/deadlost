# chess-lab
# `make help` lists everything. Engine stages are resumable; interrupting is safe.

PY ?= python
.DEFAULT_GOAL := help

.PHONY: help install data build tracks verify test lint claims manifest export report figures clean distclean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install the package and dev dependencies
	$(PY) -m pip install -e ".[dev]"

data: ## Fetch the corpora (~150 MB from GitHub mirrors)
	bash scripts/fetch_data.sh

build: ## Full rebuild: ingest, engine, all tracks, checks (~1h, resumable)
	bash scripts/build_all.sh

tracks: ## Re-run every analysis track from cached engine evaluations (fast)
	@for t in t1_ingest t2_openings t3_blunders t4_inflation t5_color \
	          t6_swindles t8_player_panel t9_otb_swindles t11_matched_skill t12_titled_tuesday t10_multiverse t7_falsify; do \
	  echo "== $$t"; $(PY) -m chesslab.tracks.$$t >/dev/null || exit 1; \
	done
	$(PY) scripts/power_report.py

report: ## Build the self-contained findings page for GitHub Pages
	$(PY) scripts/make_report.py

lint: ## Run ruff
	ruff check src scripts tests

verify: ## Run tests, claims check and manifest check
	$(PY) -m chesslab.cli verify

test: ## Run the test suite only
	$(PY) -m pytest -q

claims: ## Check every published number against the results files
	$(PY) scripts/check_claims.py

manifest: ## Record current content hashes as the reference state
	$(PY) scripts/manifest.py write

export: ## Write the reusable dataset and data dictionary
	$(PY) -m chesslab.cli export

figures: tracks ## Regenerate all figures
	@ls figures/

clean: ## Remove caches and build artefacts (keeps data and results)
	rm -rf .pytest_cache **/__pycache__ src/*.egg-info build dist export

distclean: clean ## Also remove fetched data and engine evaluations
	rm -rf data/raw data/derived data/eval
