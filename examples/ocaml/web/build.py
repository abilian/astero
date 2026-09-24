"""Build the playground: one zip, and one generated reference page.

Pyodide runs CPython in WebAssembly, and both packages here are pure Python
with no dependencies, so the whole toolchain is one zip and one
`unpackArchive` call. Nothing is compiled and nothing is vendored: the zip
is built from the working tree, so what the page runs is what the tests run.

The documentation's reference card is generated for the same reason. Its
three tables — the operators with their precedence, the keywords, and the
standard library with the type of every name — are all things the compiler
already declares, so they are read off it rather than typed out beside it
and left to rot.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from ocaml.front.lexer import KEYWORDS
from ocaml.front.parser import LEVELS
from ocaml.middle.prelude import PRELUDE_TYPES

WEB = Path(__file__).resolve().parent
EXAMPLE = WEB.parent
ROOT = EXAMPLE.parents[1]
BUNDLE = WEB / "py" / "playground.zip"
DOCS = EXAMPLE / "docs"
PAGE = WEB / "index.template.html"
CARD = EXAMPLE / "docs/{lang}/src/language/reference.template.md"

#: The two editions. Each is a directory under `docs/`, and everything the
#: reader sees is in this table: the site's pages are written twice, and the
#: playground's strings are filled in from here.
LANGUAGES = ("en", "fr")

#: Every string the playground shows. `app.js` reads the second half out of
#: `window.STRINGS`, so no message is written in the code.
PLAYGROUND: dict[str, dict[str, str]] = {
    "en": {
        "lang": "en",
        "title": "caml-prépa — playground",
        "heading": "caml-prépa <small>playground</small>",
        "blurb": (
            "Write OCaml on the left, as taught in French "
            "<em>classes préparatoires</em>. On the right, the compiler shows "
            "what the programme prints, the types it worked out, where each "
            "name is visible, the Python it translates to, and the run one "
            "step at a time. Everything happens in your browser."
        ),
        "nav_home": "caml-prépa",
        "nav_guide": "How to use this",
        "nav_tour": "The language",
        "nav_reference": "Reference card",
        "switch_href": "../../fr/play/",
        "switch_lang": "fr",
        "switch_label": "Français",
        "programme": "Programme",
        "run": "Run",
        "run_title": "Run the source again after editing it (Ctrl/\u2318 + Enter)",
        "share": "Copy link",
        "starting": "starting…",
        "source": "Source",
        "tab_run": "Run",
        "tab_types": "Types",
        "tab_names": "Names",
        "tab_python": "Python",
        "tab_printed": "Read back",
        "tab_step": "Step",
        "step_start": "First step",
        "step_out": "Out of this call",
        "step_back": "Back one",
        "step_forward": "Forward one",
        "step_in": "Into the next call",
        "step_end": "Last step",
        "step_at": "Position in the run",
        "step_cursor": "Go to cursor",
        "step_cursor_title": (
            "Jump to the first step inside what is selected in the source"
        ),
        "step_back_short": "Back",
        "step_forward_short": "Next",
        "step_in_short": "Into call",
        "step_out_short": "Out of call",
        "hint_run": (
            "What the programme prints. It runs twice, once by the "
            "interpreter and once as compiled Python, and the line at the top "
            "right says whether both printed the same thing."
        ),
        "hint_types": (
            "The type of every top-level definition, worked out by the "
            "compiler. <code>'a</code> means any type."
        ),
        "hint_names": (
            "Where each name can be used. Each line is a part of the programme "
            "that opens a scope, with the names it introduces there. Click a "
            "line to find it in the source."
        ),
        "hint_python": "The same programme, translated into Python by the compiler.",
        "hint_printed": (
            "Your programme, written back out from the tree the compiler "
            "built. A bracket you did not write shows how it grouped your code."
        ),
        "hint_step": (
            "The run, one evaluation at a time. Yellow marks the expression "
            "about to be evaluated, green one that has just produced its value."
        ),
        "step_env": "Names in scope",
        "step_store": "Mutable cells",
        "step_python": "The compiled Python, at this point",
        "step_output": "Printed so far",
        "footer": (
            "<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> runs. The scope "
            "trees under <strong>Names</strong> are derived by "
            '<a href="https://astero.lab.abilian.com">astero</a> from one '
            "declaration of the language."
        ),
        "running": "running…",
        "problems": "problem(s)",
        "agree": "\u2713 interpreter and compiled Python agree",
        "disagree": "\u2717 interpreter and compiled Python disagree",
        "loadingPython": "loading Python…",
        "loadingCompiler": "loading the compiler…",
        "noBundle": "py/playground.zip is missing — run `make -C examples web`",
        "linkCopied": "link copied",
        "edited": "source edited: press Run to update the views",
        "mine": "(your own code)",
        "recording": "recording\u2026",
        "steps": "steps recorded",
        "truncated": "stopped recording at",
        "evaluating": "Evaluating",
        "gives": "Result",
        "calls": "Calls",
        "scope": "Scope",
        "line": "line",
        "groupExamples": "Examples",
        "groupSimonet": "Vincent Simonet's exercises",
        "groupGrimaud": "Informatique MPI",
        "kind_module": "the whole programme",
        "kind_binding": "let",
        "kind_let": "let \u2026 in",
        "kind_case": "match case",
        "kind_fun": "fun",
        "kind_for": "for loop",
        "ns_vals": "Values",
        "ns_cons": "Constructors and exceptions",
        "ns_fields": "Record fields",
        "ns_types": "Type names",
        "ns_tyvars": "Type variables",
        "nothingBound": "nothing bound here yet",
        "nothingMutable": "nothing mutable here yet",
        "notYet": "not started",
        "linkInBar": "the link is in the address bar",
        "bootHelp": (
            "The page needs an HTTP server and a network fetch of Pyodide.\n"
            "Serve it with `make -C examples ocaml-docs-serve`, or bump "
            "PYODIDE_VERSION in app.js."
        ),
    },
    "fr": {
        "lang": "fr",
        "title": "caml-prépa — bac à sable",
        "heading": "caml-prépa <small>bac à sable</small>",
        "blurb": (
            "Écrivez de l'OCaml à gauche, tel qu'on l'enseigne en classes "
            "préparatoires. À droite, le compilateur montre ce qu'affiche le "
            "programme, les types qu'il a trouvés, où chaque nom est visible, "
            "le Python qu'il en tire, et l'exécution pas à pas. Tout se passe "
            "dans votre navigateur."
        ),
        "nav_home": "caml-prépa",
        "nav_guide": "Mode d'emploi",
        "nav_tour": "Le langage",
        "nav_reference": "Aide-mémoire",
        "switch_href": "../../en/play/",
        "switch_lang": "en",
        "switch_label": "English",
        "programme": "Programme",
        "run": "Exécuter",
        "run_title": (
            "Exécuter à nouveau le source après l'avoir modifié (Ctrl/\u2318 + Entrée)"
        ),
        "share": "Copier le lien",
        "starting": "démarrage…",
        "source": "Source",
        "tab_run": "Exécution",
        "tab_types": "Types",
        "tab_names": "Noms",
        "tab_python": "Python",
        "tab_printed": "Réécrit",
        "tab_step": "Pas à pas",
        "step_start": "Premier pas",
        "step_out": "Sortir de l'appel",
        "step_back": "Un pas en arrière",
        "step_forward": "Un pas en avant",
        "step_in": "Entrer dans l'appel",
        "step_end": "Dernier pas",
        "step_at": "Position dans l'exécution",
        "step_cursor": "Aller au curseur",
        "step_cursor_title": ("Aller au premier pas situé dans la sélection du source"),
        "step_back_short": "Reculer",
        "step_forward_short": "Avancer",
        "step_in_short": "Entrer",
        "step_out_short": "Sortir",
        "hint_run": (
            "Ce qu'affiche le programme. Il est exécuté deux fois, par "
            "l'interpréteur et sous forme de Python compilé, et la ligne en "
            "haut à droite dit si les deux ont affiché la même chose."
        ),
        "hint_types": (
            "Le type de chaque définition de premier niveau, trouvé par le "
            "compilateur. <code>'a</code> veut dire « n'importe quel type »."
        ),
        "hint_names": (
            "Où chaque nom peut servir. Chaque ligne est une partie du "
            "programme qui ouvre une portée, avec les noms qu'elle y "
            "introduit. Cliquez sur une ligne pour la retrouver dans le source."
        ),
        "hint_python": "Le même programme, traduit en Python par le compilateur.",
        "hint_printed": (
            "Votre programme, réécrit à partir de l'arbre que le compilateur a "
            "construit. Une parenthèse que vous n'aviez pas écrite montre "
            "comment il a groupé votre code."
        ),
        "hint_step": (
            "L'exécution, une évaluation à la fois. Le jaune marque "
            "l'expression sur le point d'être évaluée, le vert celle qui vient "
            "de produire sa valeur."
        ),
        "step_env": "Noms visibles",
        "step_store": "Cases modifiables",
        "step_python": "Le Python compilé, à ce moment",
        "step_output": "Affiché jusqu'ici",
        "footer": (
            "<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Entrée</kbd> exécute. Les "
            "arbres de portées de l'onglet <strong>Noms</strong> sont dérivés "
            'par <a href="https://astero.lab.abilian.com">astero</a> d\'une '
            "seule déclaration du langage."
        ),
        "running": "exécution…",
        "problems": "problème(s)",
        "agree": "\u2713 l'interpréteur et le Python compilé concordent",
        "disagree": "\u2717 l'interpréteur et le Python compilé divergent",
        "loadingPython": "chargement de Python…",
        "loadingCompiler": "chargement du compilateur…",
        "noBundle": "py/playground.zip est absent — lancez `make -C examples web`",
        "linkCopied": "lien copié",
        "edited": "source modifié : cliquez sur Exécuter pour mettre les vues à jour",
        "mine": "(votre propre code)",
        "recording": "enregistrement\u2026",
        "steps": "pas enregistrés",
        "truncated": "enregistrement arrêté à",
        "evaluating": "Évalue",
        "gives": "Résultat",
        "calls": "Appels",
        "scope": "Portée",
        "line": "ligne",
        "groupExamples": "Exemples",
        "groupSimonet": "Les TP de Vincent Simonet",
        "groupGrimaud": "Informatique MPI",
        "kind_module": "le programme entier",
        "kind_binding": "let",
        "kind_let": "let \u2026 in",
        "kind_case": "cas de filtrage",
        "kind_fun": "fun",
        "kind_for": "boucle for",
        "ns_vals": "Valeurs",
        "ns_cons": "Constructeurs et exceptions",
        "ns_fields": "Champs d'enregistrement",
        "ns_types": "Noms de types",
        "ns_tyvars": "Variables de type",
        "nothingBound": "rien de lié ici pour l'instant",
        "nothingMutable": "rien de modifiable ici pour l'instant",
        "notYet": "pas encore commencé",
        "linkInBar": "le lien est dans la barre d'adresse",
        "bootHelp": (
            "La page a besoin d'un serveur HTTP et d'un accès réseau pour "
            "charger Pyodide.\nLancez `make -C examples ocaml-docs-serve`, ou "
            "changez PYODIDE_VERSION dans app.js."
        ),
    },
}

#: The playground lists the corpus in these sets, by the directory each
#: programme sits in. The keys name the heading in `PLAYGROUND`.
GROUPS = {
    "groupExamples": "corpus",
    "groupSimonet": "simonet",
    "groupGrimaud": "grimaud",
}

#: What `app.js` reads out of `window.STRINGS`. The rest fills the page.
RUNTIME_STRINGS = (
    "running", "problems", "agree", "disagree", "loadingPython",
    "loadingCompiler", "noBundle", "linkCopied", "linkInBar", "bootHelp",
    "edited", "mine",
    "recording", "steps", "truncated", "evaluating", "gives",
    "nothingBound", "nothingMutable", "notYet", "calls", "scope", "line",
    "groupExamples", "groupSimonet", "groupGrimaud",
    "kind_module", "kind_binding", "kind_let", "kind_case", "kind_fun",
    "kind_for", "ns_vals", "ns_cons", "ns_fields", "ns_types", "ns_tyvars",
)  # fmt: skip


def add_tree(bundle: zipfile.ZipFile, source: Path, prefix: str) -> int:
    written = 0
    for path in sorted(source.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        bundle.write(path, f"{prefix}/{path.relative_to(source)}")
        written += 1
    return written


def code(text: str) -> str:
    """A markdown code span. A `|` inside one would end a table cell."""
    return f"`{text}`".replace("|", "\\|")


def operators() -> str:
    """The precedence table, from the one the parser cascades over."""
    rows = [
        f"| {place} | {' '.join(code(op) for op in ops)} | {assoc} |"
        for place, (ops, assoc) in enumerate(reversed(LEVELS), start=1)
    ]
    header = ["| level | operators | associates |", "| --- | --- | --- |"]
    return "\n".join(header + rows)


def keywords() -> str:
    """Every reserved word, from the lexer's own set."""
    return " ".join(code(word) for word in sorted(KEYWORDS))


def stdlib() -> str:
    """Every prelude name with its type, from the checker's own table."""
    groups: dict[str, list[tuple[str, str]]] = {"": []}
    for name, written in PRELUDE_TYPES.items():
        module, _, rest = name.partition(".")
        where = module if rest else ""
        groups.setdefault(where, []).append((rest or name, written))
    out = []
    for where, entries in groups.items():
        heading = where or "Always in scope"
        out += [f"### {heading}\n", "| name | type |", "| --- | --- |"]
        out += [
            f"| {code(f'{where}.{name}' if where else name)} | {code(written)} |"
            for name, written in entries
        ]
        out.append("")
    return "\n".join(out)


def reference(lang: str) -> Path:
    """One edition's reference card, with its derived tables filled in."""
    template = Path(str(CARD).format(lang=lang))
    page = template.read_text(encoding="utf-8")
    for marker, made in (
        ("<!--OPERATORS-->", operators()),
        ("<!--KEYWORDS-->", keywords()),
        ("<!--STDLIB-->", stdlib()),
    ):
        if marker not in page:
            raise ValueError(f"{template} has no {marker}")
        page = page.replace(marker, made)
    written = template.with_name("reference.md")
    written.write_text(page, encoding="utf-8")
    return written


def playground(lang: str, into: Path) -> Path:
    """The playground, with one edition's strings, copied into `into`.

    `app.js` and `style.css` are the same for both; only the page differs,
    and every string it shows comes from `PLAYGROUND` rather than from the
    markup or the code.
    """
    words = PLAYGROUND[lang]
    page = PAGE.read_text(encoding="utf-8")
    runtime = {name: words[name] for name in RUNTIME_STRINGS}
    page = page.replace("{{strings}}", json.dumps(runtime, ensure_ascii=False))
    for key, value in words.items():
        page = page.replace(f"{{{{{key}}}}}", value)
    if "{{" in page:
        left = page[page.index("{{") : page.index("{{") + 30]
        raise ValueError(f"{PAGE.name}: no string for {left}")
    into.mkdir(parents=True, exist_ok=True)
    (into / "index.html").write_text(page, encoding="utf-8")
    if into.resolve() == WEB.resolve():
        return into / "index.html"
    for name in ("app.js", "style.css"):
        shutil.copy2(WEB / name, into / name)
    if (WEB / "py").is_dir():
        shutil.copytree(WEB / "py", into / "py", dirs_exist_ok=True)
    return into / "index.html"


def main(target: Path = BUNDLE) -> Path:
    """Write the bundle, and say what went into it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        modules = add_tree(bundle, ROOT / "src" / "astero", "astero")
        modules += add_tree(bundle, EXAMPLE / "src" / "ocaml", "ocaml")
        # Flat in the zip, whatever the tree looks like: the page lists
        # what it finds in one directory, and the names are unique.
        programmes = sorted((EXAMPLE / "corpus").rglob("*.ml"))
        for path in programmes:
            bundle.write(path, f"corpus/{path.name}")
        # Which set each programme belongs to, for the page's grouped list.
        groups = {
            group: [p.name for p in programmes if p.parent.name == folder]
            for group, folder in GROUPS.items()
        }
        bundle.writestr("corpus/groups.json", json.dumps(groups))
        # `grimaud/` is copied under the GPL-3.0, which travels with the
        # copies. Not a `.ml`, so the page does not list it.
        bundle.write(EXAMPLE / "corpus/grimaud/LICENSE", "corpus/LICENSE.grimaud")
    for lang in LANGUAGES:
        reference(lang)
        playground(lang, DOCS / lang / "src" / "play")
    # The standalone `make -C examples web-serve` serves `web/` itself, so
    # the English page is written there too.
    playground("en", WEB)
    size = target.stat().st_size // 1024
    # `relative_to` only where it applies: a test builds into a temporary
    # directory, which is not under the repository at all.
    where = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
    print(f"{where}: {modules + 1} modules, {len(programmes)} programmes, {size} KB")
    return target


if __name__ == "__main__":
    main()
