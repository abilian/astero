# Visite guidée

Écrit pour quelqu'un qui connaît un peu Python. Tous les exemples de cette page tournent tels quels dans [le bac à sable](../play/).

OCaml est un langage *fonctionnel*, ce qui se remarque tout de suite à trois choses : on nomme des valeurs, qui ne changent jamais ensuite ; les fonctions sont des valeurs comme les autres, et le compilateur détermine les types tout seul.

## Nommer des choses

```ocaml
let x = 42
let nom = "Hypatie"
let pi = 3.14159
```

`let` introduit un nom. Ce n'est pas une affectation : `x` vaut 42, et vaudra toujours 42. Si vous écrivez `let x = 43` ensuite, vous avez créé un *nouveau* `x` qui cache l'ancien, ce qui n'est pas du tout la même chose : tout ce qui avait capturé le premier voit toujours 42.

Les fonctions utilisent le même mot :

```ocaml
let double n = 2 * n
let somme a b = a + b
```

`double` prend un argument, `somme` en prend deux, et on les appelle sans parenthèses ni virgules :

```ocaml
let quatre = double 2
let sept = somme 3 4
```

Les parenthèses ne servent qu'à grouper : `somme 3 (double 2)` en a besoin, `somme 3 4` non. Tout le monde s'y fait prendre une fois.

!!! tip "À essayer"
    Mettez cela dans le bac à sable et regardez l'onglet **Types**. Vous n'avez écrit `int` nulle part : il l'a trouvé seul.

## Les types, sans les écrire

```console
$ python -m ocaml --types tour.ml
val double : int -> int
val somme : int -> int -> int
```

Lisez `int -> int` comme « prend un `int`, rend un `int` ». `somme` est `int -> int -> int`, ce qui paraît bizarre jusqu'à ce qu'on sache qu'une fonction à deux arguments est en réalité une fonction qui prend un argument et rend une fonction attendant le suivant. C'est pour cela que `somme 3` tout seul est légal, et vaut une fonction qui ajoute 3.

Le compilateur a déduit tout cela de `2 * n` et de `a + b`, parce que `*` et `+` sont des opérateurs entiers. Si vous aviez écrit `2. *. n`, il aurait dit `float -> float`.

**Les flottants ont leurs propres opérateurs**. C'est la surprise numéro un en OCaml :

```ocaml
let aire r = 3.14159 *. r *. r
```

`+.`, `-.`, `*.`, `/.` pour les flottants ; `+`, `-`, `*`, `/` pour les entiers. Les mélanger est une erreur, pas une conversion. `float_of_int` et `int_of_float` convertissent quand on le veut.

## Décider

```ocaml
let signe n = if n > 0 then "positif" else "négatif"
```

`if` est une *expression* : elle a une valeur, comme le `a if c else b` de Python et non comme son `if` instruction. Les deux branches doivent avoir le même type, puisque le tout n'en a qu'un.

Dès qu'il y a plus de deux cas, on utilise le **filtrage** :

```ocaml
let classe n =
  match n with
  | 0 -> "zéro"
  | 1 -> "un"
  | k when k < 0 -> "négatif"
  | _ -> "grand"
```

Chaque `|` est un cas. `_` filtre n'importe quoi, et `when` ajoute une condition. Les cas sont essayés de haut en bas.

## Les listes

Une liste s'écrit avec des `;` entre les éléments, pas des `,` :

```ocaml
let premiers = [ 2; 3; 5; 7; 11 ]
```

La virgule construit un *n-uplet*, ce qui est autre chose : `(1, "un")` est un couple formé d'un `int` et d'une `string`.

Les listes sont bâties à partir de deux morceaux : la liste vide `[]`, et `::` qui colle un élément devant. Donc `[1; 2; 3]` est vraiment `1 :: (2 :: (3 :: []))`. C'est pour cela que la façon canonique de travailler sur une liste est de filtrer ces deux formes :

```ocaml
let rec longueur l =
  match l with
  | [] -> 0
  | _ :: reste -> 1 + longueur reste
```

`let rec` et non `let`, parce que la fonction s'appelle elle-même. OCaml veut que vous le disiez.

Ce schéma, filtrer sur `[]` et sur `t :: q`, occupe l'essentiel du premier semestre. Voici la somme :

```ocaml
let rec somme_liste l =
  match l with
  | [] -> 0
  | t :: q -> t + somme_liste q
```

!!! tip "À essayer"
    Collez cela dans le bac à sable et ouvrez **Noms**. Vous verrez que `t` et `q` n'existent qu'à l'intérieur du second cas. C'est ce que fait un motif : il démonte la valeur et nomme les morceaux, pour ce cas-là seulement.

La bibliothèque contient déjà les fonctions usuelles :

```ocaml
List.length [ 1; 2; 3 ]              (* 3 *)
List.map double [ 1; 2; 3 ]          (* [2; 4; 6] *)
List.filter (fun n -> n > 2) l       (* les éléments supérieurs à 2 *)
List.fold_left ( + ) 0 [ 1; 2; 3 ]   (* 6 *)
```

`fun n -> n > 2` est une fonction sans nom. `( + )` est l'addition prise comme valeur, ce à quoi servent les parenthèses.

## Vos propres types

Deux sortes, et elles couvrent presque tout.

Un **type somme** énumère les formes qu'une valeur peut prendre :

```ocaml
type couleur = Trefle | Carreau | Coeur | Pique

type forme =
  | Cercle of float
  | Rectangle of float * float
```

Chaque nom commençant par une majuscule est un *constructeur*. `Cercle 2.0` est une `forme`, et `Rectangle (3.0, 4.0)` aussi. On les démonte par filtrage :

```ocaml
let aire f =
  match f with
  | Cercle r -> 3.14159 *. r *. r
  | Rectangle (l, h) -> l *. h
```

C'est ce qu'OCaml fait bien et Python maladroitement. Le compilateur connaît la liste des formes, donc il peut vous signaler celle que vous avez oubliée.

Un **type enregistrement** est ce que Python appellerait un petit objet à champs nommés :

```ocaml
type point = { x : float; y : float }

let origine = { x = 0.0; y = 0.0 }
let abscisse p = p.x
```

Les champs se lisent avec `.`, comme en Python. Un champ marqué `mutable` peut être modifié :

```ocaml
type compteur = { mutable valeur : int }

let incremente c = c.valeur <- c.valeur + 1
```

`<-` est l'affectation, légale seulement sur un champ `mutable`. Tout le reste est immuable.

## Des types qui contiennent n'importe quoi

```ocaml
type 'a arbre =
  | Feuille
  | Noeud of 'a arbre * 'a * 'a arbre
```

`'a` est une *variable de type* : un arbre de n'importe quoi. `int arbre` est un arbre d'entiers, `string arbre` un arbre de chaînes, et vous n'écrivez le code qu'une fois.

Le compilateur les met tout seul. Écrivez une fonction sur les arbres qui ne regarde jamais les valeurs : il vous dira qu'elle marche pour tous les arbres :

```console
$ python -m ocaml --types arbre.ml
val hauteur : 'a arbre -> int
```

Ce `'a` n'était écrit nulle part. Il a été déduit.

## Quand il faut vraiment modifier

La plupart du temps, ce n'est pas nécessaire. Quand il le faut :

```ocaml
let compteur = ref 0        (* une référence *)
let () = compteur := 5      (* écrire *)
let n = !compteur           (* lire *)
```

`ref` crée une case modifiable, `:=` y écrit, `!` la lit. Les tableaux sont l'autre chose modifiable :

```ocaml
let t = [| 1; 2; 3 |]
let premier = t.(0)
let () = t.(0) <- 99
```

`[| ... |]` pour les tableaux, `t.(i)` pour indexer. Attention : `[ ... ]` est une liste et `[| ... |]` un tableau, ce sont deux types différents avec des coûts différents.

Les deux boucles existent aussi :

```ocaml
let () =
  for i = 1 to 5 do
    print_int i
  done

let () =
  let n = ref 10 in
  while !n > 0 do
    n := !n - 1
  done
```

Le corps d'une boucle a le type `unit`, le « rien à dire » d'OCaml, l'équivalent du `None` de Python. Il s'écrit `()`.

## Enchaîner

```ocaml
let () =
  print_string "réponse : ";
  print_int 42;
  print_newline ()
```

`;` enchaîne : fais ceci, puis cela. La valeur est celle du dernier.

`let () = ...` en tête de fichier est l'idiome pour « exécute ceci ». Cela se lit comme un filtrage contre `()`, ce que c'est exactement.

## Les exceptions

```ocaml
exception Vide

let premier l =
  match l with
  | [] -> raise Vide
  | t :: _ -> t

let sur l = try premier l with Vide -> 0
```

Déclarées avec `exception`, levées avec `raise`, rattrapées par `try ... with` suivi de cas, exactement comme un `match`.

## Ce qui n'y est pas

Il n'y a ni modules à vous, ni objets, ni foncteurs. `Printf`, `Hashtbl` et `Stack` sont là. L'[aide-mémoire](reference.md) donne la liste complète de ce qui existe, y compris toutes les fonctions de la bibliothèque avec leur type.

## Ensuite

- [Le bac à sable](playground.md), pour tirer parti des six vues.
- [Comment marche le compilateur](../compiler/index.md), si vous voulez maintenant savoir comment tout cela est possible.
