# Spécification

Cette page définit le langage que ce compilateur accepte, appelé **caml-prépa** là où il faut le distinguer d'OCaml. L'[aide-mémoire](reference.md) en est la version courte, pour tous les jours ; celle-ci est la version longue, pour savoir exactement ce que veut dire une construction, ou pourquoi le compilateur l'a refusée.

caml-prépa, c'est OCaml tel qu'on l'enseigne en classes préparatoires (MPSI/MP, MPI, PCSI et l'option informatique) : le sous-ensemble qu'un élève écrit au tableau. Il est choisi par un seul critère : un programme de première ou de deuxième année s'en sert-il ? Cela admet `let rec`, le filtrage, les listes, les tableaux, les enregistrements, les types sommes, les références, les boucles et les exceptions, ainsi que `Printf`, `Hashtbl` et `Stack` dans la bibliothèque standard.

La référence, c'est le vrai OCaml. Là où cette page et OCaml ne disent pas la même chose, la section [Différences avec OCaml](#differences-avec-ocaml) donne le cas, avec sa raison et la façon d'en sortir.

## Ce qui est laissé de côté

Ne font pas partie du sous-ensemble, ni ne sont prévus : les modules et les foncteurs (`module`, `sig`, `struct`, `open`, `include`, `let open`, les fichiers `.mli`) ; les objets et les classes ; les variants polymorphes (`` `Tag ``) ; les GADT et les types existentiels ; les arguments étiquetés et optionnels (`~x`, `?x`) ; les modules de première classe et les modules récursifs ; `lazy` ; les variants extensibles ; les attributs et les nœuds d'extension (`[@...]`, `[%...]`) ; les opérateurs définis par l'utilisateur ; `when` sur un `let` ; `Format`, `Seq` et `Bytes` ; `external` ; `nonrec` ; `function` à plus d'un paramètre.

Peuvent raisonnablement être ajoutés, dans cet ordre :

1. Les motifs d'intervalle, `'a' .. 'z'`.
2. `open`, limité aux modules de la bibliothèque standard listés [plus bas](#la-bibliotheque-standard).
3. L'égalité physique, `==` et `!=`.

## Structure lexicale

Le texte est d'abord découpé en lexèmes, sur lesquels travaille ensuite la grammaire. Deux des règles lexicales d'OCaml demandent du code qu'une grammaire rendrait illisible : les commentaires s'imbriquent, et `'a'` est un caractère là où `'a` est une variable de type.

### Blancs et commentaires

L'espace, la tabulation, le retour chariot et le saut de ligne séparent les lexèmes et sont ignorés par ailleurs.

Les commentaires s'écrivent `(*` ... `*)`. Ils **s'imbriquent** : `(* a (* b *) c *)` est un seul commentaire. Une chaîne littérale à l'intérieur d'un commentaire n'est pas analysée, alors qu'OCaml l'analyse ; voir [Différences avec OCaml](#differences-avec-ocaml).

### Littéraux

| lexème | forme |
| --- | --- |
| `INT` | `[0-9][0-9_]*`, `0x[0-9A-Fa-f_]+`, `0o[0-7_]+`, `0b[01_]+` |
| `FLOAT` | `[0-9][0-9_]*` suivi de `.` et/ou d'un exposant `[eE][+-]?[0-9]+` : `1.`, `1.5`, `1e10`, `1.5e-3` |
| `CHAR` | `'c'`, `'\n'`, `'\t'`, `'\r'`, `'\b'`, `'\\'`, `'\''`, `'\"'`, `'\065'` (décimal), `'\x41'` (hexadécimal) |
| `STRING` | `"..."` avec les mêmes échappements, plus un `\` en fin de ligne pour la continuer |

`1.` et `1.0` sont des flottants, `1` est un entier. Il n'y a pas de conversion implicite : `1 + 1.0` est une erreur de type, comme en OCaml.

### Identificateurs

| lexème | forme | ce qu'il nomme |
| --- | --- | --- |
| `LID` | `[a-z_][A-Za-z0-9_']*` | valeurs, noms de types, champs d'enregistrement |
| `UID` | `[A-Z][A-Za-z0-9_']*` | constructeurs, exceptions, modules de la bibliothèque standard |
| `TYVAR` | `'` suivi de `[a-z][A-Za-z0-9_']*` | variables de type |

`_` seul est le motif universel, pas un `LID`.

L'analyseur lexical essaie `CHAR` avant `TYVAR`. Un caractère littéral a toujours une apostrophe fermante et une variable de type jamais, si bien qu'un seul choix ordonné tranche. `'ab'` est une erreur lexicale.

### Mots-clés

```
and  as  begin  do  done  downto  else  end  exception  false  for  fun  function
if  in  let  match  mod  mutable  of  rec  then  to  true  try  type  when
while  with
land  lor  lxor  lsl  lsr  asr
```

Chaque nom de [la bibliothèque standard](#la-bibliotheque-standard), `not` et `raise` compris, est un nom ordinaire, lié avant que le programme commence, comme en OCaml.

### Symboles

```
->  <-  :=  ::  ;;  ;  ,  :  |  ||  &&  =  <>  <  <=  >  >=
+  -  *  /  +.  -.  *.  /.  **  ^  @  !  _
(  )  [  ]  [|  |]  {  }  .  .(  .[
```

L'analyseur lexical prend la plus longue suite de caractères de symbole possible sans traverser de blanc : `a < -1` fait trois lexèmes, `a <-1` en fait deux.

## Expressions de type

Les grammaires de cette page sont écrites comme des règles PEG : `/` est un choix ordonné, `?` rend facultatif, `*` signifie « autant qu'on veut », `+` « au moins un ».

```peg
type        <- tuple_type ("->" type)?           # associatif à droite
tuple_type  <- app_type ("*" app_type)*
app_type    <- atom_type type_name*              # int list, int list array
atom_type   <- TYVAR
             / "(" type ("," type)* ")"
             / type_name
type_name   <- UID "." LID / LID                 # Hashtbl.t, list
```

Un constructeur de type appliqué après son argument lie le plus fort, puis `*`, puis `->` : `int -> int list * bool` se lit `int -> ((int list) * bool)`.

Une liste parenthésée de deux types ou plus n'est valide que comme argument d'un constructeur de type, comme dans `(int, string) Hashtbl.t`. La grammaire accepte `(int, string)` seul, le vérificateur de types le rejette.

Les déclarations de types :

```peg
typedef     <- type_params? LID "=" type_rhs
type_params <- TYVAR / "(" TYVAR ("," TYVAR)+ ")"
type_rhs    <- variants / record_type / type
variants    <- "|"? variant ("|" variant)*
variant     <- UID ("of" tuple_type)?
record_type <- "{" field_decl (";" field_decl)* ";"? "}"
field_decl  <- "mutable"? LID ":" type
```

Un constructeur prend zéro ou un argument : `of int * string` déclare un seul argument, qui est un couple, comme en OCaml. Une déclaration dont le membre droit est un type, `type mot = char list`, est une **abréviation** : `mot` et `char list` sont le même type. Le compilateur affiche le nom que vous avez écrit.

## Motifs

```peg
pattern      <- or_pat ("as" LID)*
or_pat       <- tuple_pat ("|" tuple_pat)*
tuple_pat    <- cons_pat ("," cons_pat)*
cons_pat     <- app_pat ("::" cons_pat)?         # associatif à droite
app_pat      <- UID atom_pat? / atom_pat
atom_pat     <- "_"
              / LID
              / pat_literal
              / "(" pattern (":" type)? ")"
              / "(" ")"
              / "[" (pattern (";" pattern)* ";"?)? "]"
              / "[|" (pattern (";" pattern)* ";"?)? "|]"
              / "{" field_pat (";" field_pat)* ";"? "}"
field_pat    <- LID ("=" pattern)?
pat_literal  <- INT / FLOAT / CHAR / STRING / "true" / "false"
              / "-" INT / "-" FLOAT
```

`as` lie le plus faiblement, puis `|`, puis `,`, puis `::`, puis un constructeur appliqué à son argument. Un motif d'enregistrement peut ne nommer qu'une partie des champs. `{ x }` abrège `{ x = x }`.

Chaque alternative d'un motif « ou » doit lier les mêmes noms, aux mêmes types. C'est le vérificateur de types qui le garantit, pas la grammaire.

## Expressions

### Priorités

Les niveaux vont de la priorité la plus forte à la plus faible. La table est celle d'OCaml, restreinte aux opérateurs du sous-ensemble.

| niveau | formes | associativité |
| --- | --- | --- |
| 1 | `!e` | préfixe |
| 2 | `e.l`, `e.(i)`, `e.[i]` | postfixe, à gauche |
| 3 | `f x`, `C x` | à gauche |
| 4 | `-e`, `-.e` | préfixe |
| 5 | `**` `lsl` `lsr` `asr` | à droite |
| 6 | `*` `/` `*.` `/.` `mod` `land` `lor` `lxor` | à gauche |
| 7 | `+` `-` `+.` `-.` | à gauche |
| 8 | `::` | à droite |
| 9 | `@` `^` | à droite |
| 10 | `=` `<>` `<` `<=` `>` `>=` | à gauche |
| 11 | `&&` | à droite |
| 12 | `\|\|` | à droite |
| 13 | `,` | n-aire |
| 14 | `:=` `<-` | à droite |
| 15 | `if` `while` `for` | préfixe, s'étend à droite |
| 16 | `;` | à droite |
| 17 | `let ... in`, `fun`, `function`, `match`, `try` | s'étend à droite |

Deux conséquences surprennent les élèves :

* `-x ** 2` se lit `(-x) ** 2` : le moins préfixe lie plus fort que `**`.
* `1 + 2 :: l @ m` se lit `((1 + 2) :: l) @ m` : `::` lie plus fort que `@` et plus faiblement que `+`.

Les niveaux 5 à 12 sont une seule table dans le compilateur, `LEVELS` dans `front/parser.py`. L'analyseur syntaxique en construit ses règles et l'afficheur en déduit ses parenthèses, si bien que les deux ne peuvent pas diverger.

### Grammaire

```peg
seq_expr   <- expr (";" expr)* ";"?
expr       <- let_expr / fun_expr / function_expr / match_expr / try_expr
            / if_expr / while_expr / for_expr / assign_expr

let_expr      <- "let" "rec"? binding ("and" binding)* "in" seq_expr
fun_expr      <- "fun" atom_pat+ "->" seq_expr
function_expr <- "function" cases
match_expr    <- "match" seq_expr "with" cases
try_expr      <- "try" seq_expr "with" cases
if_expr       <- "if" seq_expr "then" expr ("else" expr)?
while_expr    <- "while" seq_expr "do" seq_expr "done"
for_expr      <- "for" LID "=" seq_expr ("to" / "downto") seq_expr
                 "do" seq_expr "done"

cases      <- "|"? case ("|" case)*
case       <- pattern ("when" seq_expr)? "->" seq_expr
binding    <- pattern atom_pat* (":" type)? "=" seq_expr

assign_expr <- tuple_expr ((":=" / "<-") assign_expr)?
tuple_expr  <- or_expr ("," or_expr)*
or_expr     <- and_expr ("||" and_expr)*
and_expr    <- cmp_expr ("&&" cmp_expr)*
cmp_expr    <- concat_expr (cmp_op concat_expr)*
concat_expr <- cons_expr (("@" / "^") concat_expr)?
cons_expr   <- add_expr ("::" cons_expr)?
add_expr    <- mul_expr (add_op mul_expr)*
mul_expr    <- pow_expr (mul_op pow_expr)*
pow_expr    <- neg_expr (pow_op pow_expr)?
neg_expr    <- ("-" / "-.") neg_expr / apply_expr
apply_expr  <- access_expr access_expr*
access_expr <- prefix_expr postfix*
postfix     <- "." LID / ".(" seq_expr ")" / ".[" seq_expr "]"
prefix_expr <- "!" prefix_expr / atom_expr

atom_expr  <- INT / FLOAT / CHAR / STRING / "true" / "false"
            / "(" ")"
            / UID "." LID                         # List.map
            / UID                                 # un constructeur
            / LID
            / "(" seq_expr (":" type)? ")"
            / "begin" seq_expr "end"
            / "[" (expr (";" expr)* ";"?)? "]"
            / "[|" (expr (";" expr)* ";"?)? "|]"
            / "{" record_expr "}"
record_expr <- seq_expr "with" field_bind (";" field_bind)* ";"?
             / field_bind (";" field_bind)* ";"?
field_bind  <- LID ("=" expr)?
```

Les corps de `let ... in`, de `fun`, d'un cas de `match`, de `while` et de `for` sont des `seq_expr` : dans `match n with 0 -> f (); g () | _ -> ()`, les deux appels sont dans le premier cas. Les branches d'un `if` sont des `expr` : `if c then a; b` se lit `(if c then a); b`, et dans `if a then if b then c else d`, le `else` va au `if` intérieur. Ce sont les trois lectures d'OCaml. Elles sortent de la grammaire sans aucune déclaration de priorité : une répétition PEG prend tout ce qu'elle peut, tandis que ses choix sont essayés dans l'ordre.

### L'arbre

L'analyseur syntaxique construit des dataclasses Python ordinaires, définies dans `src/ocaml/syntax.py` :

```
Expr    = Int | Float | Char | Str | Bool | Unit
        | Var(name)                              # x, List.map
        | Construct(name, args)                  # Some x, None
        | Tuple(items) | ListLit(items) | ArrayLit(items)
        | Record(fields, base)                   # { r with x = 1 }
        | Apply(fn, args)                        # f x y
        | BinOp(op, left, right) | UnOp(op, value)
        | If(cond, then, otherwise)
        | Seq(items)
        | LetIn(recursive, bindings, body)
        | Fun(params, body) | Function(cases)
        | Match(scrutinee, cases) | Try(body, cases)
        | While(cond, body) | For(var, start, stop, down, body)
        | GetField(value, label) | SetField(value, label, rhs)
        | ArrayGet(array, index) | ArraySet(array, index, rhs)
        | StringGet(value, index)
        | Constraint(value, annot)

Pattern = PWild | PVar(name) | PLit(value) | PTuple(items) | PList(items)
        | PArray(items) | PConstruct(name, args) | PRecord(fields)
        | POr(alternatives) | PAlias(pattern, name) | PConstraint(pattern, annot)

TypeExpr = TVar(name) | TCon(name, args) | TFun(arg, result) | TTuple(items)

Item    = LetItem(recursive, bindings) | TypeItem(defs) | ExnItem(name, args)
        | ExprItem(value)
```

`Apply` prend tous ses arguments d'un coup. Un `Binding` garde ses paramètres : `let f x y = e` n'est pas réécrit en `let f = fun x y -> e`. Les deux conservent le nombre d'arguments écrit dans le source, ce qui permet au back-end Python de traduire `f a b` en un appel direct `f(a, b)`.

## Programmes

```peg
structure   <- ";;"? (item ";;"?)* EOF
item        <- "let" "rec"? binding ("and" binding)*
             / "type" typedef ("and" typedef)*
             / "exception" UID ("of" tuple_type)?
             / seq_expr
```

`;;` est facultatif partout et ne change rien. Un `let` de premier niveau sans `in` définit ses noms pour toute la suite du programme.

## Noms

À quelle définition renvoie un nom, c'est ce que le compilateur déduit d'une courte déclaration dans `middle/grammar.py`, sans que rien n'en soit écrit à la main : [Comprendre ce qu'il veut dire](../compiler/meaning.md) montre comment.

### Cinq sortes de noms

Le compilateur sépare les mêmes cinq sortes de noms qu'OCaml :

| espace de noms | introduit par | utilisé par |
| --- | --- | --- |
| `vals` | une variable dans un motif | une variable |
| `cons` | un constructeur de variant, une `exception` | `Some x`, `h :: t`, un motif constructeur |
| `fields` | une déclaration de champ d'enregistrement | `r.x`, `r.x <- v`, `{ x = 1 }`, `{ x }` |
| `types` | une déclaration `type` | un nom de type |
| `tyvars` | les paramètres d'une déclaration, et `'a` dans une annotation | `'a` |

Un champ d'enregistrement `x` et une variable `x` n'ont rien à voir : renommer l'un ne touche jamais l'autre.

Constructeurs et exceptions partagent un espace de noms parce qu'OCaml le partage : `exception E` déclare un constructeur de type `exn`, qui masque un constructeur de variant `E` déclaré plus tôt.

### Où un nom est visible

Toute variable d'un motif est liée, quelle que soit sa profondeur : dans `match l with h :: t -> ...`, `h` comme `t`. Chacune de ces constructions ouvre une portée, avec les parties indiquées à l'intérieur :

| construction | dans sa portée |
| --- | --- |
| `fun p1 p2 -> e` | les paramètres et le corps |
| un cas de `match` ou de `try` | le motif, la garde et le corps |
| `let f p1 p2 = e` | les paramètres et le membre droit |
| `for i = a to b do e done` | la variable de boucle et le corps |
| `let ... in b` | les liaisons et le corps |

`let x = e` sans paramètre n'ouvre pas de portée propre : il ne lie rien au-dessus de `e`. Les noms que définit un `let` de premier niveau sont visibles dans tout ce qui le suit.

Dans une annotation de type sur une valeur, `(l : 'a list)`, une variable de type s'introduit elle-même, comme en OCaml. Dans une déclaration de type ou d'exception, `type t = 'a list` est une erreur : toute variable de type doit être l'un des paramètres de la déclaration.

### Où le modèle est approché

**`let` voit son propre nom.** En OCaml, `let x = x + 1 in ...` lit le `x` *extérieur* ; seul `let rec` rend le nom visible dans son propre membre droit. Le modèle de portées du compilateur traite les deux de la même façon, si bien que la vue Noms montre le `x` intérieur comme visible dans le membre droit d'un `let` simple. Le vérificateur de types et les deux back-ends traitent ce cas correctement : seuls les arbres de portées sont approchés. La déclaration dit quelles parties d'une construction sont dans sa portée. Le motif d'une liaison et son membre droit forment une seule partie de `let ... in`, si bien qu'ils sont à l'intérieur ensemble ou à l'extérieur ensemble.

**Les variables de type valent pour tout le programme dans les arbres de portées.** Les paramètres d'une déclaration ne sont pas placés dans une portée à eux. Le vérificateur de types applique la règle ci-dessus ; la vue Noms ne la montre pas.

### Ce qui est vérifié

* Chaque nom renvoie à une définition dans une portée englobante, sinon il est signalé comme non lié.
* Un constructeur est appliqué à autant d'arguments qu'à sa déclaration.
* Chaque alternative d'un motif « ou » lie les mêmes noms.
* Un motif ou une expression d'enregistrement ne nomme que des champs déclarés.

## Typage

Le système de types est celui de Hindley–Milner, avec les parties de celui d'OCaml sur lesquelles s'appuie un cours de classe préparatoire :

* **L'inférence.** Aucune annotation n'est nécessaire. Les types sont trouvés par unification, avec un test d'occurrence : `let rec f x = f` est rejeté comme type cyclique.
* **Le polymorphisme du `let`.** Une définition faite par `let`, au premier niveau ou à l'intérieur, est généralisée : `let id x = x` a le type `'a -> 'a` et peut servir à `int` à un endroit et à `string` à un autre.
* **La restriction aux valeurs.** `let r = ref []` ne doit pas être généralisé, sinon la même cellule pourrait être remplie avec un `int` et lue comme un `string`. Seule une valeur syntaxique est généralisée : un littéral, une variable, une fonction, un constructeur appliqué à des valeurs, un n-uplet ou une liste de valeurs. Une variable non généralisée s'affiche `'_weak1`, comme OCaml l'affiche.
* **La récursion.** À l'intérieur de son propre `let rec`, une fonction est monomorphe ; elle est généralisée ensuite. Un groupe relié par `and` est généralisé d'un bloc.
* **Les types.** `int`, `float`, `char`, `string`, `bool`, `unit` et `exn` ; `list`, `array`, `ref` et `option` ; `Stack.t` et `Hashtbl.t` ; vos variants, enregistrements et abréviations, avec leurs paramètres ; les fonctions et les n-uplets.
* **Enregistrements et variants sont nominaux.** Un nom de champ ou un constructeur détermine le type. Quand deux types d'enregistrement ont un champ de même nom, c'est le type déjà connu à l'endroit où le champ est utilisé qui décide, comme dans `(p : processor).id` ; sinon, la dernière déclaration qui contient tous les champs que nomme l'expression.
* **Les abréviations gardent leur nom.** Après `type solution = float array`, une fonction annotée comme renvoyant une `solution` a ce type dans sa signature, là où `float array` serait le même type écrit autrement. Une annotation donne le type qu'elle nomme, sur un paramètre, sur un résultat ou dans `(e : t)`.
* **Les formats.** `Printf.printf` a le type que lui donne OCaml, `('a, out_channel, unit) format -> 'a`. Une chaîne littérale qu'on lui passe est lue comme un format : `Printf.printf "%d: %s\n"` attend un `int` puis un `string`. Les directives sont `%d %i %u %x %X %o %s %c %f %F %e %E %g %G %b %B`, avec des drapeaux, une largeur et une précision, plus `%%` et `%!`.

Le sous-typage, le polymorphisme de rangée et les types de modules sont absents.

L'exhaustivité d'un `match` n'est pas vérifiée. En OCaml, c'est un avertissement.

## Évaluation

Les valeurs sont les entiers, les flottants, les caractères, les chaînes, les booléens, `()`, les n-uplets, les listes, les tableaux, les enregistrements, les valeurs construites, les fonctions et les exceptions.

* **La mutation.** Les listes, les n-uplets, les chaînes et les champs non déclarés `mutable` ne peuvent pas être modifiés. Les tableaux, les champs `mutable` et les cellules `ref` le peuvent.
* **`ref` est un enregistrement.** `'a ref` est `{ mutable contents : 'a }`, sur lequel `!`, `:=`, `incr` et `decr` sont des fonctions ordinaires.
* **L'égalité.** `=` est structurelle et descend jusqu'au bout. Comparer deux fonctions lève `Invalid_argument`. `<`, `<=`, `>` et `>=` ne s'appliquent qu'à `int`, `float`, `char` et `string`.
* **L'ordre.** Les arguments d'une application sont évalués de gauche à droite. OCaml laisse l'ordre non spécifié ; son compilateur va de droite à gauche.
* **Les exceptions.** `raise e` remonte jusqu'au `try ... with` englobant le plus proche qui a un cas correspondant. `Not_found`, `Failure of string`, `Invalid_argument of string`, `Division_by_zero`, `End_of_file`, `Exit` et `Assert_failure` sont prédéfinies. Une exception non rattrapée termine le programme avec un message et un code de sortie non nul.
* **Le filtrage.** Les cas sont essayés dans l'ordre. Le premier dont le motif correspond et dont la garde est vraie est retenu. Un `match` sans cas correspondant lève `Match_failure`.
* **La récursion.** OCaml exécute un appel en position terminale sans consommer de pile. Ici, chaque appel en consomme un peu, si bien qu'une boucle écrite comme une récursion peut l'épuiser : voir [Différences avec OCaml](#differences-avec-ocaml).

L'interpréteur, `back/interpret.py`, est la référence de cette section : là où les deux divergent, l'un des deux a tort. La façon dont les valeurs sont représentées en Python est décrite dans [L'exécuter, deux fois](../compiler/running.md).

## La bibliothèque standard

Liés avant que le programme commence, sans préfixe :

```
not  ref  !  :=  incr  decr  ignore  fst  snd  compare  min  max  abs  succ  pred
raise  failwith  invalid_arg  assert
print_int  print_float  print_char  print_string  print_newline  print_endline
read_int  read_float  read_line
string_of_int  int_of_string  string_of_float  float_of_string
string_of_bool  bool_of_string  float_of_int  int_of_float
char_of_int  int_of_char  truncate
sqrt  exp  log  sin  cos  tan  atan  floor  ceil  abs_float
infinity  neg_infinity  max_int  min_int
```

Avec un préfixe :

* `List` : `length hd tl nth rev append concat map rev_map iter mapi iteri fold_left fold_right filter exists find filter_map for_all mem assoc split combine sort init`
* `Array` : `length make init make_matrix get set copy sub append of_list to_list iter iteri map fold_left sort blit fill`
* `String` : `length get sub concat make init index contains uppercase_ascii lowercase_ascii split_on_char compare`
* `Char` : `code chr escaped lowercase_ascii uppercase_ascii`
* `Printf` : `printf sprintf`
* `Stack` : `create push pop top is_empty length`
* `Hashtbl` : `create add replace remove find find_opt mem length`, avec des clés comparées par leur structure, comme les compare OCaml
* `Random` : `int self_init init`
* `Float` : `pi exp cos sin tan`
* `Sys` : `argv`, qui contient le nom du programme et rien après

Il n'y a pas de système de modules : `List.map` est un seul nom qui contient un point, comme `Hashtbl.t` est un seul nom de type. L'[aide-mémoire](reference.md) les donne tous avec leur type, lu dans le compilateur au moment où la page est construite.

## Différences avec OCaml

Chacune est une décision, avec sa raison et la façon d'en sortir.

| différence | pourquoi | la façon d'en sortir |
| --- | --- | --- |
| `int` n'est pas borné, alors que celui d'OCaml a 63 bits et boucle | masquer chaque opération coûte un appel par opérateur dans le back-end Python, et aucun programme de classe préparatoire ne compte sur le bouclage | masquer au niveau des opérateurs arithmétiques |
| les arguments sont évalués de gauche à droite, alors qu'`ocamlc` va de droite à gauche | de gauche à droite ne coûte rien en Python, et OCaml laisse l'ordre non spécifié : aucun programme correct ne peut les distinguer | évaluer les arguments dans des temporaires, dans l'ordre choisi |
| une chaîne littérale dans un commentaire n'est pas analysée | ce qui compte, ce sont les commentaires imbriqués, et personne n'écrit `(* "*)" *)` en classe | analyser les chaînes dans l'analyseur des commentaires |
| un appel terminal consomme de la pile | Python n'élimine pas les appels terminaux ; la limite de récursion est portée à 10 000 cadres Python, quelques-uns par appel OCaml | transformer les appels terminaux autorécursifs en boucles, et utiliser un trampoline pour la récursion mutuelle si un programme en a besoin |
| `<` et ses semblables ne s'appliquent qu'à `int`, `float`, `char` et `string` | ordonner des fermetures et des valeurs cycliques demande une machinerie dont le sous-ensemble n'a pas besoin | implémenter l'ordre structurel d'OCaml |
| `==` et `!=` sont absents | l'égalité physique sur les valeurs immédiates dépend de l'implémentation ; les cours ne s'en servent pas | ajouter les deux, avec une réponse fixée pour les valeurs immédiates |
| l'exhaustivité d'un `match` n'est pas vérifiée | un avertissement en OCaml, et une procédure de décision ici | implémenter l'algorithme d'utilité des motifs |
| `C _` ne filtre pas un constructeur à plusieurs arguments | le vérificateur compte les motifs d'arguments ; un `_` seul en fait un | laisser un seul `_` tenir lieu de tous les arguments |
| `if` ne peut pas apparaître sans parenthèses à droite d'un opérateur binaire | les niveaux d'opérateurs s'arrêtent à une expression primaire, et `if` n'en est pas une | laisser le niveau le plus faible accepter `if`, `match`, `fun` et `try` à sa droite |
| la variable d'une boucle `for` ne peut pas être `_` | l'analyseur syntaxique y lit un identificateur | y lire un motif, et accepter `_` |
| `assert` est une fonction de type `bool -> unit`, donc `assert false` n'est pas de tous les types | l'`assert` d'OCaml est un mot-clé avec sa propre règle de typage, et le corpus n'affirme que des conditions | faire d'`assert` un mot-clé, et donner à `assert false` un type frais |
| un format doit être écrit là où il sert | une chaîne littérale n'est lue comme un format qu'en argument d'une fonction qui en attend un ; liée d'abord par un `let`, c'est un `string`, et OCaml l'accepte | lire un littéral comme un format partout où le type attendu le demande |
| `Random` tire d'autres nombres qu'OCaml, avec ou sans graine | c'est le générateur de Python | implémenter le générateur LXM d'OCaml |

## Comment c'est vérifié

Chaque étape est comparée à quelque chose qui n'est pas elle-même :

| étape | comparée à |
| --- | --- |
| lecture | l'arbre affiché puis relu, qui doit redonner le même arbre |
| noms | chaque programme du corpus se résout ; les arbres de portées sont comparés par leur forme |
| types | `ocamlc -i`, signature par signature |
| exécution | le vrai `ocaml`, sorties comparées |
| compilation | l'interpréteur, sur le même runtime |

Le corpus compte soixante programmes, chacun enregistré avec ce qu'il affiche et la signature qu'il infère. Chaque construction de la grammaire apparaît dans au moins l'un d'eux. Un test échoue sinon : une construction qu'aucun programme n'écrit n'a pas sa place dans le sous-ensemble. Avec OCaml 5.5.0 installé, `ocaml` affiche pour chacun ce qu'affichent les deux back-ends, et `ocamlc -i` infère les mêmes signatures, ligne pour ligne. [Premiers pas](../getting-started.md) présente le corpus.
