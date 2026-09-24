# Premiers pas

Il y a trois façons de s'en servir, de la plus simple à la plus impliquée.

## 1. Dans votre navigateur

[Ouvrez le bac à sable](../play/). Il n'y a rien à installer, et aucun compte à créer.

Choisissez un programme dans la liste déroulante, ou tapez le vôtre, et appuyez sur <kbd>Ctrl</kbd> ou <kbd>⌘</kbd> + <kbd>Entrée</kbd>. Les cinq onglets de droite montrent ce qu'il affiche, les types inférés, les portées, le Python produit, et votre source réimprimé.

Tout se passe dans la page. Votre code n'est envoyé nulle part, et une fois la page chargée il fonctionne hors ligne. Le bouton **Copier le lien** met votre programme dans l'URL, ce qui permet de l'envoyer à quelqu'un.

## 2. Sur votre machine

Il vous faut [Python 3.11 ou plus récent](https://www.python.org/downloads/) et [uv](https://docs.astral.sh/uv/), qui s'installe en une commande :

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ensuite :

```sh
git clone https://github.com/abilian/astero
cd astero/examples/ocaml
uv run python -m ocaml corpus/fact.ml
```

Cela doit afficher `120` trois fois : `corpus/fact.ml` calcule une factorielle de trois manières différentes.

`uv run` construit l'environnement la première fois et le réutilise ensuite. Il n'y a rien d'autre à configurer, parce que le compilateur est du Python pur, sans aucune dépendance.

### Les cinq vues, en ligne de commande

Chaque onglet du bac à sable est une option :

```sh
python -m ocaml programme.ml              # l'exécuter
python -m ocaml --types programme.ml      # les types inférés
python -m ocaml --names programme.ml      # les portées
python -m ocaml --python programme.ml     # le Python produit
python -m ocaml --printed programme.ml    # votre source, réimprimé
```

Essayez sur un programme que vous connaissez :

```console
$ python -m ocaml --types corpus/tree.ml
val insert : 'a -> 'a tree -> 'a tree
val height : 'a tree -> int
val min_elt : 'a tree -> 'a
val to_list : 'a tree -> 'a list
val summarise : int list -> stats
```

Rien dans `corpus/tree.ml` ne dit de quel type est quoi que ce soit. Tout cela a été déterminé.

### Votre propre bac à sable

Pour faire tourner le bac à sable depuis votre copie :

```sh
make -C .. web-serve
```

Puis ouvrez <http://localhost:8000/>. Cela construit le paquet et lance un petit serveur web ; <kbd>Ctrl</kbd>+<kbd>C</kbd> pour l'arrêter.

## 3. Depuis Python

Le compilateur est un paquet Python ordinaire : vous pouvez appeler les morceaux directement.

```python
from ocaml.front.parser import parse
from ocaml.middle.infer import signature
from ocaml.back.interpret import run_source
from ocaml.back.compile import compile_source

source = "let rec fact n = if n <= 1 then 1 else n * fact (n - 1)"

signature(parse(source))     # ['val fact : int -> int']
compile_source(source)       # le Python produit, sous forme de chaîne
run_source(source)           # l'exécute, et rend la portée globale
```

`ocaml.pipeline.analyse(source)` fait tourner toutes les étapes d'un coup et rend ce que chacune a produit. La ligne de commande et le bac à sable sont tous les deux construits dessus, donc tout ce que l'un ou l'autre affiche est accessible depuis Python.

## Les programmes d'exemple

`corpus/` contient soixante programmes, à lire avant d'écrire les vôtres. Huit d'entre eux correspondent à un chapitre chacun d'un cours type :

| | |
| --- | --- |
| `sorting.ml` | les tris : insertion, sélection, fusion, pivot |
| `stacks.ml` | piles et files, la file amortie sur deux piles |
| `divide.ml` | diviser pour régner : Euclide, exponentiation rapide, dichotomie |
| `dynamic.ml` | programmation dynamique : mémoïsation, somme maximale, plus longue sous-suite commune |
| `assoc.ml` | dictionnaires, en listes d'association |
| `polynomes.ml` | polynômes : Horner, somme, produit, dérivée |
| `combinatoire.ml` | Hanoï, parties, permutations, code de Gray |
| `graphes.ml` | parcours en profondeur et en largeur |

Chacun est accompagné d'un fichier `.expected`, qui est exactement ce qu'il affiche, et d'un fichier `.signature`, qui est le type de chaque définition. Ce ne sont pas des décorations : c'est ce à quoi la suite de tests compare, à chaque modification.

Vingt-trois autres sont dans `corpus/simonet/`, un par sujet de la série de travaux pratiques que [Vincent Simonet](https://www.normalesup.org/~simonet/teaching/caml-prepa/index.html) a donnée au lycée Janson-de-Sailly entre 1998 et 2003, en première et en seconde année. Ils vont plus loin que les huit ci-dessus : compression LZW, arbres rouge et noir, Knuth-Morris-Pratt, construction de Thompson, Barnes et Hut. `corpus/simonet/README.md` en est l'index. Les énoncés d'origine sont sur son site, avec les corrigés.

Les dix-neuf derniers, dans `corpus/grimaud/`, sont des solutions de l'ouvrage [*Informatique MPI*](https://www.informatiquempi.fr) d'Aslı Grimaud et Gilles Grimaud, copiées sous licence GPL-3.0 : composantes fortement connexes, Kruskal, couplage biparti, automates, sac à dos de six façons, une calculatrice. C'est le code des auteurs, écrit pour OCaml : on y voit à quoi ressemble un programme qui utilise `Printf` et des annotations de type partout. `corpus/grimaud/README.md` dit d'où vient chacun et ce qui a été modifié, le cas échéant.

## Ensuite

- [La visite guidée du langage](language/tour.md), si vous voulez commencer à écrire.
- [Le bac à sable](language/playground.md), pour tirer parti des six vues.
- [Comment marche le compilateur](compiler/index.md), si c'est pour cela que vous êtes venu.
