SHELL := /bin/bash
VENV := .venv
# Only the linter needs the venv. Anything that exercises the plugin's own
# scripts runs on the bare system interpreter, because that is the only
# environment they are promised to work in — see `test-unit` below.
VENV_PYTHON := $(VENV)/bin/python3
PYTHON := python3
SCRIPTS_DIR := skills/epistemic-debt/scripts

.PHONY: venv lint test test-unit test-integration check install-hooks clean

# Rebuilt whenever requirements-dev.txt changes; otherwise `make venv` is a
# no-op on repeat runs (this file's mtime is the up-to-date marker).
$(VENV)/bin/activate: requirements-dev.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt
	touch $(VENV)/bin/activate

venv: $(VENV)/bin/activate

lint: venv
	$(VENV_PYTHON) -m ruff check $(SCRIPTS_DIR)

# Deliberately no `venv` prerequisite and no install step: the scripts are
# stdlib-only by design so they run against any target repo on whatever
# python3 is already there. Running the suite inside a populated venv would
# let a stray third-party import pass here and fail in the field.
test-unit:
	$(PYTHON) -m unittest discover -s $(SCRIPTS_DIR) -p "test_*.py"

test: test-unit

# The behavioral eval suite (evals/) needs `claude plugin eval`, gated
# behind early access — see evals/README.md. Not part of `check`/pre-push
# since it can't run in every environment yet.
test-integration:
	claude plugin eval . --scaffold --allow-tools Bash Write

# Stdlib-only too, so no venv prerequisite — this must stay runnable in a
# checkout with nothing installed.
validate-manifests:
	$(PYTHON) scripts/check_manifests.py

# Everything a push should be blocked on. Kept deliberately narrow (no
# test-integration) so the pre-push hook only requires things every
# contributor's machine can run.
check: lint test-unit validate-manifests

install-hooks:
	mkdir -p .git/hooks
	cp scripts/git-hooks/pre-push .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
	@echo "Installed pre-push hook -> runs 'make check' before every push."

clean:
	rm -rf $(VENV) .ruff_cache
