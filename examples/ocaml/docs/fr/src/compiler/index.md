# La forme d'un compilateur

Vous savez ce que fait un compilateur : du source entre, quelque chose d'exécutable sort. Cette partie parle du *comment*, avec un compilateur que vous pouvez lire.

Aucune connaissance préalable n'est supposée. Si vous savez lire du Python, vous savez lire celui-ci.

## Le problème

Voici toute la difficulté en une ligne :

```ocaml
let rec somme l = match l with [] -> 0 | t :: q -> t + somme q
```

Pour une machine, ce sont 62 caractères : une suite d'octets, où `t` est l'octet 44. La fonction et le `match` que vous y lisez, elle ne les voit pas. Tout ce que fait un compilateur consiste à transformer cela en quelque chose qui a une structure et un sens.

Cela se passe en trois étapes, et tout compilateur que vous rencontrerez les a, quel que soit le nom qu'il leur donne.

<div class="grid cards" markdown>

- **[1. Lire le texte](reading.md)**

    Des octets, puis des mots, puis un arbre. Quelle est la *forme* de ce programme ?

- **[2. Comprendre ce qu'il veut dire](meaning.md)**

    À quelle définition renvoie chaque nom, et quel type a chaque chose ?

- **[3. L'exécuter, deux fois](running.md)**

    Parcourir l'arbre et faire ce qu'il dit, ou le traduire en un autre langage.

</div>

## Suivre une ligne

Prenons cette ligne et regardons-la traverser le compilateur. Vous pouvez tout refaire vous-même, dans [le bac à sable](../play/) ou en ligne de commande.

### Elle devient une liste de mots

La première passe, l'**analyseur lexical**, découpe le texte en les plus petits morceaux qui ont un sens à eux seuls, les **lexèmes** :

```
kw:let  kw:rec  lid:somme  lid:l  sym:=  kw:match  lid:l  kw:with
sym:[  sym:]  sym:->  int:0  sym:|  lid:t  sym:::  lid:q  sym:->  ...
```

`lid` désigne un identificateur minuscule, `kw` un mot-clé, `sym` un symbole. Plus rien ensuite ne regarde un caractère : c'est pour cela que les espaces et les commentaires cessent d'exister ici.

### Elle devient un arbre

La deuxième passe, l'**analyseur syntaxique**, détermine la forme. `t + somme q` n'est pas quatre lexèmes à la suite : c'est une addition dont le membre gauche est `t` et le membre droit est un appel. Cela fait un arbre :

```
LetItem(recursive=True, bindings=[
  Binding(pattern=PVar('somme'), params=[PVar('l')], value=
    Match(scrutinee=Var('l'), cases=[
      Case(pattern=PList([]),                       body=Int(0)),
      Case(pattern=PConstruct('::', [PVar('t'), PVar('q')]),
           body=BinOp('+', Var('t'), Apply(Var('somme'), [Var('q')]))),
    ]))])
```

Tout compilateur travaille sur un arbre de ce genre, appelé **arbre de syntaxe abstraite**. Ici les nœuds sont de simples dataclasses Python, listées dans `src/ocaml/syntax.py` : il y en a soixante-six sortes.

On peut voir l'arbre indirectement, en demandant au compilateur de le réimprimer :

```console
$ python -m ocaml --printed somme.ml
let rec somme l = match l with [] -> 0 | t :: q -> t + somme q;;
```

Si une parenthèse apparaît là où vous n'en aviez pas mis, l'arbre n'a pas la forme que vous croyiez.

### Elle prend un sens

L'arbre est une forme. Il ne sait toujours pas que le `t` du corps est celui que le motif a introduit, ni que `somme` rend un `int`.

Les noms d'abord :

```console
$ python -m ocaml --names somme.ml   # abrégé: le premier des cinq arbres
── vals ──
module    top              {somme}
  binding                    {l}
    case                       {}
    case                       {q, t}
```

Puis viennent les types, déduits de rien d'autre que la façon dont les valeurs sont employées :

```console
$ python -m ocaml --types somme.ml
val somme : int list -> int
```

Personne n'a écrit `int` nulle part. `0` et `+` ont suffi.

### Elle s'exécute

Soit en parcourant l'arbre et en faisant ce que dit chaque nœud, soit en la traduisant en Python :

```console
$ python -m ocaml --python somme.ml
from ocaml.back import runtime as _rt
def somme(l):
    _s1 = l
    _ok3 = False
    _m2 = None
    if not _ok3 and _s1.tag == '[]':
        _m2 = 0
        _ok3 = True
    if not _ok3 and _s1.tag == '::':
        t = _s1.args[0]
        q = _s1.args[1]
        _m2 = t + somme(q)
        _ok3 = True
    if not _ok3:
        _rt.fail('Match_failure')
    return _m2
```

Le `match` est devenu une suite de tests. C'est ce qu'*est* le filtrage, une fois qu'on regarde dessous : demander de quelle sorte est la valeur, et quand elle convient, en extraire les morceaux et les nommer.

## L'organisation

Chaque étape est un répertoire, de sorte que le code est rangé comme le sont les idées :

```
src/ocaml/
  syntax.py     l'arbre, dont parlent les trois parties
  front/        le texte entre, l'arbre sort
  middle/       ce que l'arbre veut dire
  back/         deux façons de l'exécuter
```

Le compilateur compte environ 6 600 lignes de Python, commentaires compris.

## Pourquoi deux back-ends

La plupart des compilateurs n'en ont qu'un. Celui-ci en a deux, qui partagent leur idée de ce qu'*est* une valeur, ce qui fait qu'exécuter un programme des deux façons et comparer est un test du compilateur lui-même.

Cela a débusqué deux vrais défauts, et aucun des deux ne provoquait de plantage : ils donnaient des réponses fausses, avec lesquelles tous les autres tests étaient d'accord. [La troisième page](running.md) raconte l'histoire.

---

Commencez par [lire le texte](reading.md).
