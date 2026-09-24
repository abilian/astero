# Les solutions d'*Informatique MPI*

Dix-neuf programmes tirés des dépôts qui accompagnent l'ouvrage [*Informatique MPI*](https://www.informatiquempi.fr) d'Aslı Grimaud et Gilles Grimaud, publiés sous l'organisation GitHub [Informatique-MPI](https://github.com/Informatique-MPI), un dépôt par chapitre ou par problème.

Ces dépôts sont sous licence GPL-3.0 et les programmes le restent : le texte de la licence est dans `LICENSE`, à côté d'eux. Contrairement aux programmes de `../simonet/`, réécrits à partir d'énoncés, ceux-ci sont des copies. Chaque fichier commence par un commentaire qui donne le dépôt, le commit et le chemin d'origine, puis la liste de ce qui a été modifié, ou « Unchanged below this comment » si rien ne l'a été. Ce commentaire est le seul ajout aux quatorze fichiers inchangés.

Les dépôts ont été lus au commit du 22 septembre 2026. Seuls les répertoires `solutions/` ont été retenus : les répertoires `exercices/` contiennent des canevas à compléter. Les fichiers `cours/Code_*.ml` sont des extraits des solutions (des déclarations de types, une fonction) qui n'affichent rien.

## Les programmes

| programme | dépôt | ce qu'on y voit | modifié |
| --- | --- | --- | --- |
| `language.ml` | Ch01 Langages réguliers | expressions rationnelles sur l'alphabet de l'ADN, reconnaissance par découpage | non |
| `quickselect.ml` | Ch03 Algorithmes probabilistes | sélection du k-ième élément par pivot aléatoire | non |
| `kosaraju.ml` | Ch05 Algorithmes sur les graphes | parcours en profondeur avec une pile, composantes fortement connexes | non |
| `mergesort.ml` | Ch05 Algorithmes sur les graphes | tri fusion sur des tableaux | non |
| `kruskal.ml` | Ch05 Algorithmes sur les graphes | union-find par rang avec compression de chemin, arbre couvrant minimal | oui |
| `bipartite_matching.ml` | Ch05 Algorithmes sur les graphes | couplage maximum par chemins augmentants | non |
| `automaton.ml` | Ch06 Automates finis | automates : validité, accessibilité, émondage, suppression des ε-transitions, déterminisation | oui |
| `automaton_words.ml` | Ch08 Automates finis (2) | exécution d'un automate déterministe sur un mot | oui |
| `vertex_cover.ml` | Couverture de sommets | recherche exhaustive par masque, 2-approximation gloutonne | non |
| `scheduling.ml` | Ordonnancement des tâches | ordonnancement LPT sur m processeurs | non |
| `knapsack.ml` | Sac à dos | représentation, tri par rapport valeur/poids, vérification | non |
| `knapsack_01_brute_force.ml` | Sac à dos | sac à dos 0/1 par énumération | non |
| `knapsack_01_greedy.ml` | Sac à dos | sac à dos 0/1 glouton | non |
| `knapsack_01_bb.ml` | Sac à dos | sac à dos 0/1 par séparation et évaluation, avec une file de priorité | oui |
| `knapsack_fractional_greedy.ml` | Sac à dos | sac à dos fractionnaire glouton | non |
| `knapsack_unbounded_dp.ml` | Sac à dos | sac à dos non borné, programmation dynamique | non |
| `knapsack_unbounded_greedy.ml` | Sac à dos | sac à dos non borné glouton | non |
| `simple_calculator.ml` | Projet Calculatrice | analyse lexicale par automate, analyse descendante récursive, évaluation | non |
| `sci_calculator.ml` | Projet Calculatrice | la même, avec moins unaire, `pi`, `e`, `cos`, `sin`, `tan` et une boucle d'interaction | oui |

Les noms des fichiers reprennent ceux d'origine sans le préfixe `Grimaud_`, sauf `bipartite_matching.ml` (l'original s'appelle `Grimaud_matching.ml`, et `../matching.ml` existe déjà), `automaton_words.ml` (pour le distinguer de celui du chapitre 6) et `sci_calculator.ml` (l'original est `Grimaud_sci_calculator3.ml`).

## Les cinq modifications

Toutes viennent de ce que le sous-ensemble n'a pas de modules et que la suite lance chaque programme sans argument ni entrée standard. Le détail exact est dans le commentaire en tête de chaque fichier.

- `automaton.ml` et `knapsack_01_bb.ml` concatènent un module et le programme qui l'ouvrait, et retirent la ligne `open`. Un `open` suivi des définitions du programme se comporte comme la concaténation : une définition du programme masque celle du module.
- `kruskal.ml` fait de même avec le corps du module `UnionFindRankPath`, sorti de sa signature `UnionFindAbs`, et retire le `let open` qui l'utilisait.
- `automaton_words.ml` lisait ses deux arguments dans `Sys.argv`. Le `let () =` devient `let main argv =`, et un nouveau `let () =` l'appelle sur six lignes de commande, dont une sans argument pour garder le message d'usage.
- `sci_calculator.ml` lisait l'entrée standard. Un `read_line` défini juste avant la boucle masque celui de la bibliothèque et rejoue une session écrite d'avance : la boucle elle-même n'est pas modifiée.

## Ce qui n'a pas été retenu

| dépôt | fichier | pourquoi |
| --- | --- | --- |
| Ch03 | `Grimaud_quicksort.ml` | tri de Monte-Carlo à budget : ce qu'il affiche dépend des tirages aléatoires |
| Ch07 Intelligence artificielle | `id3/`, `knn/`, `kdtree/` | lisent un fichier CSV et dessinent avec `Graphics` |
| Ch09 Étude des jeux | `Grimaud_astar/` | les labyrinthes sont tirés au hasard, et `Random.init` ne tire pas les mêmes nombres ici qu'OCaml |
| Ch09 Étude des jeux | `Grimaud_jeu_coloration/` | jeu interactif (`read_line`) et générateur aléatoire |
| Projet Calculatrice | `mini_calculator`, `sci_calculator`, `sci_calculator2` | étapes intermédiaires entre `simple_calculator.ml` et `sci_calculator.ml` |
| Projet Jeu de Nim | `Grimaud_Nim_4heaps.ml` | interactif (`read_int_opt`), termine la partie par `exit` |
| Probleme Algorithme de Prim, MAX2SAT, N reines, Plus longue sous-séquence commune ; Projets Classification hiérarchique, Ensembles de Julia ; Ch02, Ch04, Ch10, Ch11 | | pas de solution en OCaml dans le dépôt |

## Ce qu'il a fallu au compilateur

Les accueillir a demandé des ajouts au compilateur. Les programmes, eux, n'ont pas subi d'autre contournement que les cinq modifications ci-dessus. Le compilateur a reçu :

- `Printf.printf` et `Printf.sprintf`, dont le format est typé à partir de ses directives, comme dans OCaml ;
- les modules `Stack`, `Hashtbl`, `Random` et `Float`, pour ce que ces programmes en utilisent ;
- `Sys.argv`, `List.find`, `List.filter_map`, `Char.escaped` et `assert` ;
- la désambiguïsation des champs par le type, puisque `scheduling.ml` déclare deux types d'enregistrement qui ont tous deux un champ `id` ;
- les abréviations de type conservées dans les signatures : `ocamlc -i` écrit `solution` là où le vérificateur écrivait `float array`, et les deux divergeaient sur quatorze de ces dix-neuf programmes.

Pour en lancer un :

```sh
uv run python -m ocaml corpus/grimaud/kosaraju.ml
uv run python -m ocaml --types corpus/grimaud/kosaraju.ml
```
