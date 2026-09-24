# 3. L'exécuter, deux fois

L'arbre a une forme et un sens. Il faut maintenant que quelque chose se passe.

Il y a deux façons. Ce compilateur fait les deux.

## D'abord : qu'est-ce qu'une valeur ?

Avant l'une ou l'autre, il faut répondre à une question. Quand le programme manipule une liste, qu'est-ce que c'est *au juste*, en Python ?

`src/ocaml/back/runtime.py` tranche :

| OCaml | en Python |
| --- | --- |
| `int`, `float`, `bool`, `string` | le type Python correspondant |
| `char` | une `str` d'un caractère |
| `unit` | `None` |
| un n-uplet | un tuple Python |
| `'a list` | des cellules chaînées : `Value("::", (tête, queue))`, terminées par `Value("[]")` |
| `'a array` | une `list` Python |
| un enregistrement, donc `'a ref` aussi | `Record(fields)` |
| `Some x`, `Feuille`, une exception | `Value(tag, args)` |
| une fonction | un appelable Python à un argument |

Trois de ces lignes demandent une justification.

**Les listes sont des cellules chaînées.** En OCaml, `x :: l` ne coûte rien et partage `l` : la nouvelle liste *est* `x` pointant sur l'ancienne. Une liste Python devrait copier, ce qui donnerait le mauvais coût et, pire, le mauvais comportement quand deux listes partagent une queue.

**`ref` n'a droit à aucun traitement particulier.** En OCaml, `ref` n'est pas primitif : c'est un enregistrement à un champ mutable, et `!`, `:=`, `incr` et `decr` sont des fonctions ordinaires dessus. C'est donc un `Record` ici aussi, et la machinerie des enregistrements se trouve exercée par le programme le plus banal qui soit.

**Une fonction prend un argument.** Les fonctions d'OCaml sont curryfiées : `somme 3 4` est en réalité `(somme 3) 4`, et `somme 3` tout seul est une fonction parfaitement utilisable qui ajoute 3. Représenter toute fonction comme prenant un argument à la fois fait tomber cela tout seul, sans comptabilité.

## Première façon : parcourir l'arbre

`back/interpret.py` est la chose la plus simple qu'on puisse appeler exécuter un programme. Une fonction prend un nœud et un environnement, et rend une valeur :

```python title="src/ocaml/back/interpret.py"
        case s.BinOp(op=op, left=left, right=right):
            return BINARY_OPS[op](eval_expr(left, env), eval_expr(right, env))
```

On évalue la gauche, on évalue la droite, on applique l'opérateur. Puis :

```python title="src/ocaml/back/interpret.py"
        case s.If(cond=cond, then=then, otherwise=otherwise):
            if eval_expr(cond, env):
                return eval_expr(then, env)
            return eval_expr(otherwise, env) if otherwise is not None else None
```

Il y a un cas par sorte de nœud, si bien que tout le comportement du langage tient dans une fonction qui se lit de haut en bas. Le fichier fait 209 lignes de code.

Si vous vous êtes déjà demandé ce qu'est vraiment « un interpréteur », c'est cela. Il n'y a pas de tour de passe-passe.

## Deuxième façon : le traduire en Python

`back/compile.py` produit un programme Python qui fait la même chose :

```console
$ python -m ocaml --python corpus/fact.ml   # abrégé
from ocaml.back import runtime as _rt
print_int = _rt.ENV['print_int']
...
def fact(n):
    return 1 if _rt.BINARY_OPS['<='](n, 1) else n * fact(n - 1)
```

Vous pouvez enregistrer cela, le lancer avec `python`, et ne plus jamais faire intervenir ce compilateur.

Il doit décider trois choses que l'interpréteur n'a jamais à décider.

**Combien d'arguments.** L'interpréteur peut les prendre un par un sans s'en soucier. Un compilateur veut `def f(x, y)` et un appel direct `f(a, b)`, parce que `f(a)(b)` est plus lent et se lit moins bien. Il connaît le nombre parce que l'arbre l'a gardé, depuis l'instant où l'analyseur a vu `let f x y = ...`.

**Comment tester un motif.** Le `match` doit devenir du contrôle de flux ordinaire. L'exemple plus haut en donne la forme : demander de quelle sorte est la valeur, et quand elle convient, en extraire les morceaux et leur donner les noms du motif.

**Comment appeler les choses.** Un identificateur OCaml peut contenir `'`, pas un identificateur Python. Pire, le `let` d'OCaml masque le nom antérieur là où une affectation Python l'écrase. Le premier exemple de la [page précédente](meaning.md) reposait sur cette différence. Donc chaque liaison reçoit un nom Python neuf :

```console
$ python -m ocaml --python shadow.ml
from ocaml.back import runtime as _rt
x = 1
def _fn2(_p1):
    if not _p1 == None:
        _rt.fail('Match_failure')
    return x
f = _fn2
x_2 = 2
y = _rt.apply(f, None)
```

La seconde liaison a pris le nom neuf `x_2`, si bien que la fermeture continue de lire le `x` qu'elle a capturé. C'est bien ce que veut dire OCaml.

Là où la sortie appelle `_rt.BINARY_OPS['/']`, les deux langages divergent réellement : la division entière d'OCaml tronque vers zéro et celle de Python arrondit vers le bas, donc `(-7) / 2` vaut `-3` d'un côté et `-4` de l'autre. Là où ils s'accordent, l'opérateur sort directement.

## À quoi servent deux back-ends

Les deux back-ends utilisent le même `runtime.py`. C'est tout l'intérêt du dispositif : parce qu'ils partagent leur idée de ce qu'est une valeur, exécuter un programme des deux façons et comparer la sortie est un test **du compilateur**. S'il s'agissait de deux implémentations séparées, une différence dirait seulement que deux programmes diffèrent.

Le bac à sable le fait à chaque exécution. La ligne d'état dit *les deux exécutions concordent*, et si jamais elle ne le dit pas, l'un des deux a un bug.

Elle en a trouvé deux, et aucun ne provoquait de plantage. Un plantage se remarque ; une réponse simplement fausse, non.

### La bibliothèque supposait comment une fonction était écrite

`List.fold_left` appelait son argument comme `f(a)(b)`, un argument à la fois, comme fonctionnent les fonctions de l'interpréteur. Les fonctions du compilateur prennent les deux d'un coup, donc dès qu'un programme du corpus a replié une fonction à deux arguments, cela a cassé.

Le correctif est une petite fonction, `apply`, qui demande à l'appelé combien d'arguments il veut. La leçon se généralise : une bibliothèque d'exécution partagée par deux back-ends ne doit supposer les conventions ni de l'un ni de l'autre, et avec un seul back-end rien ne vous l'apprend.

### Une fermeture voyait une liaison qu'elle n'aurait pas dû voir

Voici l'exemple de la page précédente :

```ocaml
let x = 1
let f = fun () -> x
let x = 2
let y = f ()
```

OCaml donne `y = 1`. L'interpréteur donnait **2**, parce qu'il modifiait la portée sur place, si bien que `f` voyait le changement. Une nouvelle liaison aurait dû créer une nouvelle portée.

La version compilée donnait 1, parce qu'un nom Python neuf rendait le masquage impossible à rater. Ils ont divergé dès la toute première exécution de la comparaison. L'interpréteur avait tort.

Tous les autres tests de la suite étaient d'accord avec l'interpréteur, parce que tous les autres tests le comparaient à lui-même.

## Ce que cela vous apporte

S'il faut retenir une seule idée de cette partie, retenez celle-là. Deux implémentations de la même chose, partageant tout ce qu'elles peuvent partager et se vérifiant mutuellement, valent mieux qu'une implémentation et cent tests que vous avez écrits vous-même. Vous ne pouvez tester que ce à quoi vous avez pensé. La seconde implémentation, elle, est en désaccord sur le reste.

---

C'est tout le compilateur. Si vous voulez le lire, `src/ocaml/` fait environ 6 600 lignes, et la page [Premiers pas](../getting-started.md) le clone en trois commandes.
