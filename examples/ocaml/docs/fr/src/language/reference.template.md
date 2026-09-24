# Aide-mémoire

Cette page rassemble tout ce que contient le sous-ensemble.

!!! note "Trois de ces tableaux sont engendrés"
    Les opérateurs, les mots-clés et la bibliothèque standard sont lus
    directement dans le compilateur au moment où cette page est construite :
    ils ne peuvent donc pas prendre du retard sur lui. Le texte autour est
    écrit à la main.

## Définitions

```ocaml
let x = 42
let f x y = x + y                     (* deux paramètres *)
let rec fact n =                      (* rec, pour un appel récursif *)
  if n <= 1 then 1 else n * fact (n - 1)
let rec pair n = ... and impair n = ...  (* récursivité croisée *)
let () = print_int (fact 5)           (* exécuter quelque chose *)
let a, b = 1, 2                       (* un motif lie *)
let g x = let y = x * 2 in y + 1      (* local, avec `in` *)
```

## Types

```ocaml
int  float  char  string  bool  unit  exn
'a list        'a array       'a option      'a ref
int * string                          (* un couple *)
int -> int -> int                     (* une fonction à deux arguments *)

type couleur = Rouge | Vert | Bleu
type 'a arbre = Vide | Noeud of 'a arbre * 'a * 'a arbre
type point = { x : float; mutable y : float }
type entier = int                     (* un alias *)
exception Vide
exception Trop_grand of int
```

Un constructeur prend un argument, et `of int * string` fait de cet argument un couple. `mutable` est ce qui permet d'affecter un champ avec `<-`.

## Expressions

```ocaml
if c then a else b                    (* les deux branches, même type *)
match e with | p -> a | q when g -> b
function | p -> a | q -> b            (* une fonction qui filtre *)
fun x y -> e                          (* anonyme *)
try e with Vide -> a | Failure m -> b
while c do e done
for i = 0 to n - 1 do e done          (* `downto` décompte *)
a; b                                  (* a est évalué pour son effet *)
begin a; b end                        (* pareil, entre délimiteurs *)
[ 1; 2; 3 ]      1 :: reste      l1 @ l2
[| 1; 2; 3 |]    t.(i)           t.(i) <- v
s.[i]            "bon" ^ "jour"
{ x = 1.0; y = 2.0 }    p.x      p.y <- 3.0    { p with x = 0.0 }
let r = ref 0 in r := !r + 1; incr r
```

## Motifs

```ocaml
_                    x                    42        'a'       "s"
(a, b)               a :: reste           []        [ a; b ]  [| a; b |]
Noeud (g, v, d)      Some x               None
{ x = a; y = b }     p as tout            0 | 1 | 2
```

Toutes les alternatives d'un motif `|` doivent lier les mêmes noms. Un cas peut porter une garde : `| n when n < 0 -> ...`.

## Opérateurs

Les opérateurs vont du plus prioritaire au moins prioritaire. L'application est plus prioritaire que tous, et les préfixes `-`, `-.` et `!` davantage encore.

<!--OPERATORS-->

Les formes avec un point sont pour les flottants : `1 + 2` et `1.0 +. 2.0`, jamais les deux mélangés. `=` est l'égalité structurelle, `<>` sa négation, et `:=` écrit à travers une `ref`. N'importe lequel s'utilise comme valeur en le mettant entre parenthèses, comme dans `List.fold_left ( + ) 0`.

## Mots-clés

<!--KEYWORDS-->

## La bibliothèque standard

Voici tout ce qu'un programme peut utiliser sans le définir, avec son type. Il n'y a pas d'`open` : un nom de module est un préfixe.

<!--STDLIB-->

## Différences volontaires avec OCaml

| | ici | le vrai OCaml |
| --- | --- | --- |
| `int` | non borné | 63 bits, et il boucle |
| ordre des arguments | de gauche à droite | non spécifié |
| `<` et ses semblables | `int`, `float`, `char`, `string` | n'importe quel type |
| appels terminaux | consomment de la pile | n'en consomment pas |
| `==` et `!=` | absents | égalité physique |
| exhaustivité d'un `match` | non vérifiée | un avertissement |
| une chaîne dans un commentaire | non analysée | analysée |
| `assert false` | de type `unit` | de n'importe quel type |
| `Random` | le générateur de Python | celui d'OCaml, donc d'autres nombres |

Chacune est une décision assumée, avec une porte de sortie, que donne la [spécification](specification.md#differences-avec-ocaml).

## Hors du sous-ensemble

Le sous-ensemble n'a ni modules, ni foncteurs, ni objets, ni classes, ni GADT, ni variants polymorphes, ni arguments étiquetés ou optionnels, ni modules de première classe, ni `lazy`, ni opérateurs définis par l'utilisateur.

`Printf`, `Hashtbl` et `Stack` sont là, pour les fonctions listées plus haut. Comme en OCaml, un format de `Printf` est typé d'après ses directives : `%d`, `%s`, `%f`, `%.2f`, `%c`, `%b` et leurs largeurs. Il doit être la chaîne littérale passée à `printf` ; liée d'abord par un `let`, ce n'est plus qu'une chaîne.
