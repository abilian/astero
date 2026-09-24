# The caml-prépa documentation site: two editions, and a chooser.
#
# Everything here can also be reached from `examples/`, which delegates to
# this file, so `make -C examples ocaml-docs` and `make -C examples/ocaml/docs`
# do the same thing.
#
#     make            build both editions into site/
#     make serve      write: one edition, hot-reloading
#     make preview    check: both editions, as deployed
#
# `serve` runs `zensical serve`, which watches the sources, so a saved page
# rebuilds and reloads. It serves **one edition at its own root**, because
# that is what a zensical configuration describes, so the other language is
# not there and `lang.js` hides the language selector rather than leaving it
# pointing at a 404. `preview` is the one that shows the site as deployed,
# with the chooser and a working selector, and has no hot reload.
#
# Both depend on `generated`: the reference card and the playground are
# built from the compiler. Neither target watches those, so change
# `../web/app.js` or one of the compiler's tables and re-run.

EDITION ?= fr
PORT ?= 8010
EDITIONS := en fr
ZENSICAL := uv run --group docs --python 3.13 zensical

.PHONY: all build generated serve preview clean

all: build

# The playground's bundle and page, and each edition's reference card. The
# tables in that card are read off the compiler, so this is what keeps the
# documentation from falling behind it.
generated:
	cd .. && uv run python web/build.py

build: generated
	cd .. && for lang in $(EDITIONS); do \
		$(ZENSICAL) build -f docs/zensical.$$lang.toml --strict || exit 1; \
	done
	cp index.html site/index.html

serve: generated
	cd .. && $(ZENSICAL) serve \
		-f docs/zensical.$(EDITION).toml -a localhost:$(PORT)

preview: build
	@echo
	@echo "  http://localhost:$(PORT)/     both editions, as deployed"
	@echo
	python3 -m http.server -d site $(PORT)

clean:
	rm -rf site
	rm -rf $(addsuffix /src/play,$(EDITIONS))
	rm -f $(addsuffix /src/language/reference.md,$(EDITIONS))
