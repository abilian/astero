# 1. Lire le texte

Cette partie répond à deux questions, dans l'ordre : quels sont les mots, et quelle forme prennent-ils ?

## Les mots : l'analyseur lexical

`let x = 42`, ce sont quatre morceaux :

| morceau | ce que c'est |
| --- | --- |
| `let` | un mot-clé |
| `x` | un identificateur minuscule |
| `=` | un symbole |
| `42` | un entier |

Ce sont des **lexèmes**. Les produire est la première chose que fait un compilateur. `src/ocaml/front/lexer.py` fait 152 lignes de code, pour l'essentiel une seule expression régulière avec un groupe nommé par sorte de lexème.

Le bénéfice, c'est que plus rien ensuite ne pense en caractères. Les espaces, les retours à la ligne et les commentaires disparaissent ici, si bien que la grammaire de la section suivante n'a jamais à les mentionner.

Deux règles d'OCaml demandent du vrai code : ce sont elles qui justifient un fichier à part.

**Les commentaires s'imbriquent.** `(* a (* b *) c *)` est un seul commentaire, qui ne s'arrête pas au premier `*)`. Aucune expression régulière ne sait dire cela, donc une petite fonction compte les paires.

**`'a'` est un caractère et `'a` une variable de type.** Les deux commencent pareil, donc l'ordre dans lequel les motifs sont essayés *est* la règle :

```python
    | (?P<char>  ' (?: {escape} | [^\\'] ) ' )
    | (?P<tyvar> ' [a-z_][A-Za-z0-9_']* )
```

Le motif du caractère vient d'abord, parce qu'un littéral caractère a toujours une apostrophe fermante et qu'une variable de type n'en a jamais. Échangez ces deux lignes et `'a'` devient une variable de type suivie d'une apostrophe égarée.

Une bonne part d'un compilateur, ce sont des décisions de ce genre, où la règle est un ordre.

## La forme : l'analyseur syntaxique

Étant donné les lexèmes, quelle est la structure ? C'est la partie qui a une réputation. Elle la mérite moins qu'elle ne l'a.

Le moteur est `front/peg.py`, 125 lignes. Un analyseur est une fonction qui prend une position dans la liste de lexèmes et rend soit un résultat et une nouvelle position, soit `None` pour « ça ne correspond pas ». Tout se construit à partir de quatre d'entre elles :

```python
def seq(*parsers): ...      # a, puis b, puis c
def alt(*parsers): ...      # essaie a ; si ça rate, essaie b
def many(parser): ...       # autant qu'il y en a
def opt(parser): ...        # un, ou zéro
```

C'est tout le moteur. Vous pourriez l'écrire vous-même en une après-midi. La grammaire est alors une description du langage écrite avec ces morceaux :

```python title="src/ocaml/front/parser.py"
if_expr = act(
    seq(lit("if"), seq_expr, lit("then"), expr, opt(seq(lit("else"), expr))),
    lambda v: s.If(v[1], v[3], v[4][1] if v[4] else None),
)
```

Lisez : reconnaître `if`, puis une expression, puis `then`, puis une expression, puis facultativement `else` et une autre. Construire ensuite un nœud `If` avec les éléments reconnus aux rangs 2, 4 et 5.

`src/ocaml/front/parser.py` fait 391 lignes de cela, une règle par forme du langage.

### Pourquoi ce style convient à OCaml

On appelle cela une **PEG**, pour *parsing expression grammar*. Elle a deux propriétés. `alt` essaie ses alternatives **dans l'ordre** et garde la première qui marche. `many` est **gourmand** et en prend autant qu'il peut.

Ces deux propriétés se trouvent être exactement ce dont OCaml a besoin, parce que le langage est plein de formes qui s'étendent aussi loin que possible vers la droite :

```ocaml
let x = 1 in a; b            (* le corps du let est `a; b`, pas juste `a` *)
match n with 0 -> a; b       (* le corps du cas est `a; b` *)
if a then if b then c else d (* le `else` va avec le `if` intérieur *)
fun x -> a; b                (* le corps de la fonction est `a; b` *)
```

La répétition gourmande obtient les quatre en ne s'arrêtant pas trop tôt. Les générateurs d'analyseurs plus anciens y arrivent aussi, mais seulement une fois qu'on leur a écrit une table de priorités, et se tromper dans cette table est une source classique de bugs silencieux.

### Les priorités, à partir d'une seule table

`1 + 2 * 3` vaut 7 et non 9, parce que `*` est plus prioritaire que `+`. OCaml a dix niveaux de ce genre. Écrire dix règles presque identiques marcherait et offrirait dix occasions de se tromper, donc les niveaux sont des données :

```python title="src/ocaml/front/parser.py"
LEVELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("||",), "right"),
    (("&&",), "right"),
    (("=", "<>", "<", "<=", ">", ">="), "left"),
    (("@", "^"), "right"),
    (("::",), "right"),
    (("+", "-", "+.", "-."), "left"),
    (("*", "/", "*.", "/.", "mod", "land", "lor", "lxor"), "left"),
    (("**", "lsl", "lsr", "asr"), "right"),
)
```

La table va du moins prioritaire au plus prioritaire ; les règles en sont engendrées. Ajoutez un opérateur à une ligne et l'analyseur le connaît.

Cette table sert une seconde fois, ce qui est l'objet de la section suivante.

## En sens inverse : réimprimer

`front/emit.py` transforme un arbre en texte. Il a deux usages, dont le second est celui qui compte.

Il vous montre ce que le compilateur a cru que vous écriviez. Tapez `1 + 2 * 3` dans le bac à sable et regardez **Réécrit** ; les parenthèses vous disent comment il a groupé.

C'est aussi ainsi que l'analyseur est *vérifié*. Réimprimer un arbre, relire le texte, comparer les arbres :

```python
assert parse(unparse(parse(source))) == parse(source)
```

Si l'analyseur groupe quelque chose de travers, ceci l'attrape. Un test écrit à la main n'attrape que les cas auxquels quelqu'un a pensé.

Les parenthèses sont la difficulté de la réimpression ; aucune n'est décidée à la main. La règle tient en une phrase : un fils a besoin de parenthèses quand il est moins prioritaire que la place où il se trouve. La table dont elle a besoin est `LEVELS`, les lignes mêmes dont l'analyseur se sert déjà :

```python title="src/ocaml/front/emit.py"
OPERATOR_LEVEL: dict[str, Level] = {
    op: Level(BINARY_BASE + index, ASSOC[assoc])
    for index, (ops, assoc) in enumerate(LEVELS)
    for op in ops
}
```

Une seule déclaration, deux usages : elle groupe à l'aller et parenthèse au retour. Ils ne peuvent pas diverger, puisqu'il n'y en a qu'une.

Cela a trouvé un vrai défaut dès le premier essai. Les arguments de constructeur et les éléments de liste partageaient une fonction auxiliaire, si bien que `C (a, b)` se réimprimait `C (a; b)`. Quatre programmes s'analysaient, se résolvaient et s'exécutaient parfaitement ; seule la réimpression suivie de la relecture était en désaccord.

---

Ensuite : [comprendre ce qu'il veut dire](meaning.md).
