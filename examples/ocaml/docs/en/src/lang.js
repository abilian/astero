// Make the header's language selector land on the same page.
//
// Zensical renders one link per edition, each pointing at that edition's
// root, so switching from /en/compiler/meaning/ would land on /fr/. This
// rewrites each link to the matching page instead, and remembers the choice
// under the key the chooser at the site root reads.
//
// Both editions carry the same pages, which `test_the_two_editions_have_the
// _same_pages` holds, so a rewritten link always exists on the built site.
//
// `zensical serve` is the exception, and the reason for `hide` below. It
// serves one edition at its own root, so /en/ is not there at all and the
// links would land on its 404 page. When the current path does not start
// with any edition's prefix, that is where we are, and the control is
// removed rather than left pointing at nothing. `make -C examples
// ocaml-docs-preview` serves the whole site, where it works.
(function () {
  var KEY = "caml-prepa:lang";

  function hide(links) {
    for (var i = 0; i < links.length; i++) {
      var option = links[i].closest(".md-header__option");
      if (option) option.hidden = true;
    }
    console.info(
      "caml-prépa: one edition is being served on its own, so the language " +
        "selector is hidden. `make -C examples ocaml-docs-preview` serves both."
    );
  }

  function rewrite() {
    var links = document.querySelectorAll("a.md-select__link[hreflang]");
    if (!links.length) return;

    // Each link's own href gives that edition's prefix, so nothing here
    // assumes the site is served from the root of a domain.
    var editions = [];
    Array.prototype.forEach.call(links, function (link) {
      editions.push({
        link: link,
        lang: link.getAttribute("hreflang"),
        base: new URL(link.getAttribute("href"), location.href).pathname,
      });
    });

    var here = null;
    editions.forEach(function (entry) {
      if (location.pathname.indexOf(entry.base) === 0) here = entry;
    });
    if (!here) {
      hide(links);
      return;
    }

    var rest = location.pathname.slice(here.base.length);
    editions.forEach(function (entry) {
      entry.link.setAttribute("href", entry.base + rest + location.hash);
      entry.link.addEventListener("click", function () {
        try {
          localStorage.setItem(KEY, entry.lang);
        } catch (e) {
          /* a browser that refuses storage still follows the link */
        }
      });
    });
  }

  rewrite();
  // `navigation.instant` swaps the page without a reload, so the header is
  // rebuilt and the links have to be rewritten again.
  document.addEventListener("DOMContentLoaded", rewrite);
  if (window.document$ && window.document$.subscribe) {
    window.document$.subscribe(rewrite);
  }
})();
