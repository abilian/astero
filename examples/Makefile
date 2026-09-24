# The worked examples are projects of their own, and this runs them.
#
# Each is a member of the workspace declared in the root `pyproject.toml`,
# so `uv run` from inside one uses the same environment and the same
# editable astero. `make test` at the root calls this target.

EXAMPLES := pl0 tinypy ocaml

.PHONY: all test lint web web-serve ocaml-docs ocaml-docs-serve \
	ocaml-docs-preview clean

all: test

test:
	@for example in $(EXAMPLES); do \
		printf '\n=== %s ===\n' "$$example"; \
		(cd $$example && uv run pytest -q) || exit 1; \
	done

# The browser playground: one zip of pure Python, run by Pyodide.
web:
	cd ocaml && uv run python web/build.py

web-serve: web
	@echo
	@echo "  http://localhost:8000/"
	@echo
	python3 -m http.server -d ocaml/web 8000

# The caml-prépa documentation site. Defined in `ocaml/docs/Makefile`, and
# reached from here too, so there is one place that knows how to build it.
#
#     make -C examples ocaml-docs                    both editions
#     make -C examples ocaml-docs-serve              write, hot-reloading
#     make -C examples ocaml-docs-serve EDITION=en   the English one
#     make -C examples ocaml-docs-preview            check, as deployed
ocaml-docs:
	$(MAKE) -C ocaml/docs build

ocaml-docs-serve:
	$(MAKE) -C ocaml/docs serve

ocaml-docs-preview:
	$(MAKE) -C ocaml/docs preview

lint:
	@for example in $(EXAMPLES); do \
		printf '\n=== %s ===\n' "$$example"; \
		(cd $$example && uv run ruff check . && uv run ruff format --check .) || exit 1; \
	done

clean:
	rm -rf $(addsuffix /.pytest_cache,$(EXAMPLES)) \
		$(addsuffix /__pycache__,$(EXAMPLES)) \
		$(addsuffix /tests/__pycache__,$(EXAMPLES))
