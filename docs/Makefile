# The astero documentation site, built with Zensical.
#
#     make build              build into docs/site/
#     make serve              live-reloading preview
#     make serve PORT=8030    the same, somewhere else
#     make publish            build and deploy
#
# The repository root offers the same two builds as `make docs` and
# `make docs-serve`, which run from there with `-f docs/zensical.toml`.
#
# Zensical and mkdocstrings are in the project's `docs` dependency group,
# not in `dev`, and that group is marked for 3.13 and 3.14 because zensical
# needs a recent Python and this project's floor is 3.11. Both flags are
# needed: without `--group docs` the environment has no zensical, and
# without `--python 3.13` the group's markers exclude everything in it, so
# zensical starts and the plugin is the thing that goes missing. `zensical`
# on PATH is a third environment again, with its own plugins or none.

.PHONY: all build serve publish deploy clean

#: Not zensical's default of 8000, which the browser playground uses
#: (`make -C examples web-serve`) and which a container runtime often holds.
#: The caml-prépa site is on 8010, so the three do not collide.
PORT ?= 8020

ZENSICAL = uv run --project .. --group docs --python 3.13 zensical

all: build

# `--strict` because a broken cross-reference is a broken build. The root
# Makefile's `make docs` does the same, and the two must not diverge.
build:
	$(ZENSICAL) build --strict

serve:
	$(ZENSICAL) serve -a localhost:$(PORT)

publish: clean build
	hop3 deploy --context prod -y

deploy: publish

clean:
	rm -rf site .cache
