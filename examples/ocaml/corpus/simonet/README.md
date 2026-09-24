# Les TP de Vincent Simonet

Vingt-trois programmes, un par sujet de travaux pratiques de la série que [Vincent Simonet](https://www.normalesup.org/~simonet/teaching/caml-prepa/index.html) a donnée au lycée Janson-de-Sailly entre 1998 et 2003, en MPSI puis en MP.

Les énoncés d'origine sont en PDF sur son site, avec les corrigés, sous licence GNU FDL. Ce qui est ici n'en est pas une copie : ce sont les mêmes algorithmes, écrits pour ce compilateur, dans le sous-ensemble d'OCaml que le reste du corpus utilise. Les énoncés restent la référence.

## Première année (MPSI)

| programme | sujet | ce qu'on y voit |
| --- | --- | --- |
| `suites.ml` | Suites récurrentes | Fibonacci en temps exponentiel, linéaire et logarithmique |
| `points.ml` | Les deux points les plus proches | force brute, tri, diviser pour régner |
| `sous_suites.ml` | Plus longue sous-suite commune | récurrence naïve puis programmation dynamique |
| `gloutons.ml` | Algorithmes gloutons | cinq problèmes, dont deux que le glouton rate |
| `permutations.ml` | Permutations | composition, ordre lexicographique, cycles |
| `interrupteurs.ml` | Commutation d'interrupteurs | parties d'un ensemble, incrément binaire, code de Gray |
| `lzw.ml` | Compression LZW | un dictionnaire que les deux bouts construisent séparément |
| `abr.ml` | Arbres binaires de recherche | taille, hauteur, insertion, suppression, tables d'association |
| `labyrinthes.ml` | Labyrinthes | pile explicite, parcours en profondeur, génération |
| `logique.ml` | Un peu de logique | satisfiabilité par recherche exhaustive, trois énigmes |
| `multiensembles.ml` | Multi-ensembles | somme, union, intersection, différence, forme canonique |
| `rsa.ml` | Cryptographie RSA | Euclide étendu, exponentiation modulaire, clefs |
| `marienbad.ml` | Le jeu de Marienbad | écriture binaire, somme de Nim, stratégie gagnante |
| `huffman.ml` | Codage de Huffman | arbre de code, codage, décodage |
| `monnaie.ml` | Rendu de monnaie | glouton, poids minimaux, critère de Kozen et Zaks |
| `impossible.ml` | Le problème impossible | crible d'Ératosthène, puis l'énigme de Gardner |

## Seconde année (MP)

| programme | sujet | ce qu'on y voit |
| --- | --- | --- |
| `hachage.ml` | Tables de hachage | hachage des entiers et des chaînes, table fixe puis dynamique |
| `allocation.ml` | Allocation mémoire | listes de blocs libres, fusion, chaînage dans la mémoire |
| `rouge_noir.ml` | Arbres rouge et noir | les deux invariants, et l'insertion qui les rétablit |
| `matrices.ml` | Multiplication d'une suite de matrices | programmation dynamique et parenthésage |
| `rationnelles.ml` | Expressions rationnelles | construction de Thompson, construction des sous-ensembles |
| `motifs.ml` | Recherche de motifs | méthode naïve, Knuth-Morris-Pratt, Boyer-Moore |
| `quadtree.ml` | Quadtrees | Barnes et Hut, et ce que coûte l'approximation |

## Ce qui accompagne chaque programme

`x.expected` est ce que le programme affiche et `x.signature` les types que le vérificateur infère. Les deux sont vérifiés par la suite de tests, sur les deux back-ends, et par `ocaml` et `ocamlc -i` là où ils sont installés.

Pour en lancer un :

```sh
uv run python -m ocaml corpus/simonet/huffman.ml
uv run python -m ocaml --types corpus/simonet/huffman.ml
```
