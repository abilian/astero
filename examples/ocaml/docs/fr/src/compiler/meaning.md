# 2. Comprendre ce qu'il veut dire

Après le front-end, le compilateur sait que le programme est bien formé. Il ne sait pas que le `t` de la ligne 4 est celui que le motif a introduit deux caractères plus tôt, ni que l'ajouter à une chaîne serait une faute.

Deux questions. Ce sont elles qui expliquent que les erreurs de type et les erreurs de portée soient les deux sortes d'erreurs qu'on rencontre vraiment.

## À quelle définition renvoie chaque nom ?

Considérez :

```ocaml
let x = 1
let f = fun () -> x
let x = 2
let y = f ()
```

Que vaut `y` ? En OCaml, **1**. La troisième ligne ne change pas `x` ; elle crée un *nouveau* `x` qui cache l'ancien, et `f` détient toujours celui qu'il a capturé. C'est facile de se tromper ; ce compilateur s'est trompé, comme le raconte la [page suivante](running.md).

Y répondre suppose de savoir, en tout point du programme, quels noms sont visibles. Cette structure s'appelle l'**arbre des portées**. Vous pouvez le regarder :

```console
$ python -m ocaml --names somme.ml   # abrégé: le premier des cinq arbres
── vals ──
module    top              {somme}
  binding                    {l}
    case                       {}
    case                       {q, t}
```

Le fichier entier lie `somme`. La fonction lie `l` à l'intérieur d'elle-même. Le second cas du filtrage lie `q` et `t`, qui n'existent nulle part ailleurs.

### Comment c'est calculé

`src/ocaml/middle/analyze.py`, qui produit tout cela, fait **52 lignes** et ne mentionne pas une seule sorte de nœud : il ne nomme ni `PVar` ni `Case`, et ne liste aucun des champs qui introduisent des noms.

Il pose la question. Les réponses viennent d'un fichier séparé de 43 lignes, `middle/grammar.py`, qui décrit l'arbre :

```python
ROLES = {
    # Un motif est ce qui introduit un nom de valeur.
    "PVar": {"name": defines(VALS)},
    "PAlias": {"name": defines(VALS)},
    "Var": {"name": uses(VALS)},
    # Constructeurs, partagés par les variants et les exceptions.
    "Variant": {"name": defines(CONS)},
    "ExnItem": {"name": defines(CONS)},
    ...
}
```

Chaque champ de chaque sorte de nœud reçoit un **rôle** : celui-ci introduit un nom, celui-là y renvoie, cet autre n'est qu'un sous-arbre. Une seconde table dit quels nœuds ouvrent une portée, et sur lesquelles de leurs parties :

```python
SCOPES: dict[str, tuple[Scope, ...]] = {
    "Fun": (Scope("fun", inside=("params", "body")),),
    "Case": (Scope("case", inside=("pattern", "guard", "body")),),
    ...
}
```

Lisez la ligne `Case` ainsi : un cas de `match` ouvre une portée ; son motif, sa garde et son corps sont tous *dedans*. Cette seule ligne explique que `q` et `t` apparaissent dans le bloc d'un cas et nulle part ailleurs.

De ces deux tables sortent l'arbre des portées, la détection des noms non définis, et le renommage sûr. Un compilateur qui écrirait ces listes dans chaque passe en aurait trois ou quatre à tenir à jour. Le bug classique est qu'un cas manque dans l'une d'elles : un renommeur qui traite les paramètres de fonction mais oublie les cas de `match` renomme la mauvaise chose, sans rien signaler.

La bibliothèque qui implémente cette idée s'appelle [astero](https://astero.lab.abilian.com). Ce compilateur en est l'exemple de référence.

### Cinq sortes de noms

OCaml sépare cinq sortes de noms. La description aussi :

| espace de noms | introduit par | employé par |
| --- | --- | --- |
| `vals` | une variable de motif | une variable |
| `cons` | un variant, une exception | `Some x`, `h :: t` |
| `fields` | un champ d'enregistrement | `r.x`, `{ x = 1 }` |
| `types` | une déclaration `type` | une annotation |
| `tyvars` | les paramètres d'un type | `'a` |

Ce n'est pas du rangement. En OCaml, un champ `x` et une variable `x` n'ont aucun rapport, donc une passe qui renomme la variable doit laisser `r.x` tranquille. Avec un seul espace de noms elle ne le ferait pas, sans que rien s'en plaigne.

## Quel type a chaque chose ?

On n'écrit jamais de type en OCaml, et pourtant tout en a un. Les déterminer s'appelle l'**inférence de types**. La méthode est plus simple qu'elle n'en a l'air.

On commence par dire « je ne sais pas » : une *inconnue*. Puis, chaque fois que le programme se sert d'une valeur, on impose que son type soit compatible avec l'usage, avant de regarder ce à quoi les inconnues sont contraintes.

Pour `somme` :

- `somme` prend un argument `l`, donc elle est `?1 -> ?2` pour deux inconnues.
- `match l with [] -> ...` impose que `l` soit une liste de quelque chose : `?1 = ?3 list`.
- Un cas rend `0`, donc `?2 = int`.
- L'autre rend `t + somme q`. Comme `+` est l'addition entière, `t` est un `int` ; et `t` vient du motif `t :: q`, donc `?3 = int`.

Mis bout à bout : `somme : int list -> int`. C'est ce qu'affiche le compilateur, au terme exactement de ce raisonnement.

Rendre deux types compatibles s'appelle l'**unification** : c'est le cœur de `middle/unify.py`. Il faut aussi savoir *refuser*, car c'est de là que viennent vos messages d'erreur :

```console
types: TypingError: this has type bool but int was expected
```

Celui-ci surprend. `let rec f x = f` demanderait à `f` un type qui se contient lui-même, indéfiniment. C'est le **test d'occurrence** ; sans lui, le compilateur bouclerait sans jamais se plaindre.

### Deux subtilités qui attrapent tout le monde

**`let id x = x` reçoit `'a -> 'a`** et peut ensuite servir à `int` ici et à `string` là. Cela s'appelle le *polymorphisme de let* : une fonction devient réutilisable sans que vous écriviez quoi que ce soit.

**`let r = ref []`, non.** Essayez dans le bac à sable :

```ocaml
let r = ref []
```

Vous obtenez `'_weak1 list ref`, pas `'a list ref`. Si c'était `'a`, on pourrait mettre un `int` dans la case à un endroit et en relire une `string` à un autre, ce qui ferait mentir le système de types. Ce comportement est la **restriction aux valeurs** ; le vrai OCaml fait de même. Le `'_weak1` de votre message d'erreur n'est pas une bizarrerie : c'est le compilateur qui dit « un type précis, et je ne sais pas encore lequel ».

### Où la dérivation s'arrête

La partie « noms » de cette page est dérivée d'une description de 43 lignes. La partie « types » compte environ neuf cents lignes écrites à la main, que rien ne dérive.

C'est la limite de l'idée. Une déclaration peut dire où des noms sont introduits et où des portées s'ouvrent. Elle ne peut pas dire ce qu'est l'unification. C'est pour cette raison que `middle/infer.py`, `unify.py` et `prelude.py` forment la plus grosse partie du compilateur.

## Vérifier contre le vrai

Un moteur d'inférence qui est d'accord avec lui-même ne prouve rien. Donc, là où un vrai OCaml est installé, les tests lancent `ocamlc -i`, qui affiche les types que le vrai compilateur infère, et comparent ligne à ligne :

```console
$ python -m ocaml --types corpus/tree.ml
val insert : 'a -> 'a tree -> 'a tree
val height : 'a tree -> int
val min_elt : 'a tree -> 'a
val to_list : 'a tree -> 'a list
val summarise : int list -> stats
```

Chacune de ces lignes doit coïncider avec ce que `ocamlc -i` dit du même fichier.

---

Ensuite : [l'exécuter, deux fois](running.md).
