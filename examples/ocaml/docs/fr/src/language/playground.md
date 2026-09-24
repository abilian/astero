# Le bac à sable

[Ouvrez-le](../play/), et revenez ici quand quelque chose vous intrigue.

La liste **Programme** charge n'importe lequel des soixante exemples et l'exécute aussitôt. Modifiez le source : les vues s'estompent, parce qu'elles décrivent l'ancienne version. Cliquez sur **Exécuter**, ou appuyez sur <kbd>Ctrl</kbd> ou <kbd>⌘</kbd> + <kbd>Entrée</kbd>, pour les mettre à jour. **Exécuter** reste grisé tant qu'il n'y a rien de nouveau à exécuter.

Tout se passe dans votre navigateur. La page n'envoie ni ne stocke rien, et n'a besoin d'aucun OCaml à l'autre bout : le compilateur est écrit en Python, qui tourne dans votre onglet.

## Les six vues

### Exécution

Cette vue montre ce que le programme affiche.

Un programme sans `let () = ...` n'affiche rien, sans que ce soit un échec : beaucoup d'exemples ne font que définir des fonctions. Pour voir quelque chose, ajoutez une ligne :

```ocaml
let () = print_int (fact 5)
```

La ligne d'état, en haut à droite, indique **les deux exécutions concordent** quand tout s'est bien passé. Voici pourquoi.

Votre programme est exécuté *deux fois*. Une fois en parcourant l'arbre de syntaxe, et une fois en le compilant vers Python puis en exécutant ce Python. Les deux back-ends sont indépendants et partagent une seule bibliothèque d'exécution. La ligne dit s'ils ont affiché la même chose. C'est le test de correction du projet lui-même, appliqué à ce que vous venez de taper. Il a débusqué de vrais défauts ; voyez [L'exécuter, deux fois](../compiler/running.md).

### Types

Cette vue montre la signature inférée, dans la forme qu'affiche le vrai `ocamlc -i`. Rien dans votre source ne dit de quel type est quoi que ce soit ; tout a été déterminé.

Une variable de type écrite `'_weak1` n'a **pas** été généralisée. Ce n'est pas un bug. Essayez :

```ocaml
let r = ref []
```

Vous obtenez `'_weak1 list ref`. Si c'était `'a`, on pourrait mettre un `int` dans la case à un endroit et en relire une `string` à un autre, ce qui rendrait le système de types incohérent. Ce comportement s'appelle la *restriction aux valeurs* ; le vrai OCaml fait de même.

### Noms

Cette vue dessine l'arbre des portées, un par espace de noms. C'est la vue qu'aucun autre bac à sable OCaml ne propose.

Chaque ligne est une partie du programme qui ouvre une portée, avec la ligne où elle commence et les noms qu'elle y introduit :

| libellé | ce que c'est |
| --- | --- |
| le programme entier | le premier niveau du fichier |
| let `f` | les paramètres de la fonction `f` |
| cas de filtrage | un cas d'un `match`, d'un `function` ou d'un `try` |
| fun | les paramètres d'une fonction anonyme |
| let … in | le corps d'un `let ... in` |
| boucle for `i` | une boucle et son indice |

Cliquez sur une ligne pour la sélectionner dans le source.

Le lire répond aux questions sur lesquelles on bute vraiment. À quel `x` renvoie ce `x` ? Cet appel récursif se résout-il ? Ce paramètre s'échappe-t-il de la fonction ? L'arbre le dit, sans qu'on ait à le reconstituer de tête.

Il y a une section par sorte de nom, parce qu'OCaml en sépare cinq : valeurs, constructeurs, champs d'enregistrement, noms de types et variables de types. Un champ `x` et une variable `x` sont des noms sans rapport en OCaml, donc ils sont dans des sections différentes. Constructeurs et exceptions en partagent une, parce qu'OCaml la partage. Une section vide n'est pas affichée.

Ce que le compilateur n'a pas su trouver est listé au-dessus des arbres.

### Python

Cette vue montre ce qu'émet le second back-end. Le code est fait pour être lisible : `let f x y = ...` devient `def f(x, y)` ; un appel avec les deux arguments devient un appel direct.

Là où la sortie appelle `_rt.BINARY_OPS['/']`, les deux langages divergent. La division entière d'OCaml tronque vers zéro et celle de Python arrondit vers le bas, donc `(-7) / 2` vaut `-3` en OCaml et `-4` en Python. De même, `=` est l'égalité structurelle, qui diffère du `==` de Python. Là où ils s'accordent, l'opérateur est émis directement, ce qui explique que l'arithmétique se lise normalement.

Les noms sont renommés au besoin : un `let x = ...` qui en masque un autre ressort en `x_2`. C'est ce qui fait qu'une fermeture antérieure continue de lire le `x` qu'elle avait capturé.

### Réécrit

Cette vue réimprime votre source à partir de l'arbre que le compilateur a construit. C'est ainsi qu'on vérifie qu'il a lu ce que vous vouliez dire : si une parenthèse apparaît là où vous n'en aviez pas mis, le groupement n'était pas celui que vous imaginiez.

Essayez `1 + 2 * 3`, puis `1 + 2 :: l @ m`, et regardez où atterrissent les parenthèses.

### Pas à pas

Les cinq autres répondent à une question sur le programme entier. Celle-ci le démonte.

L'ouvrir exécute votre code une fois en enregistrant chaque évaluation ; ensuite vous parcourez cet enregistrement, avec les boutons ou avec <kbd>←</kbd> et <kbd>→</kbd>. Revenir **en arrière** marche parce que l'exécution a déjà eu lieu : on relit la liste par l'autre bout, on ne rembobine rien.

Chaque pas montre :

- **La sous-expression en cours d'évaluation**, surlignée dans la source. En jaune à l'aller, en vert au retour, quand elle a produit une valeur.
- **Les noms visibles**, portée la plus proche d'abord, et ce que chacun contient. Les fonctions sont reléguées à la fin, parce que les deux noms qui contiennent des données sont ceux que vous cherchez.
- **Les cases modifiables**, à part des noms. `let s = r` donne deux noms pour une seule case, et affecter à travers `r` change ce que lit `s`. Une seule ligne portant les deux noms, voilà à quoi cela ressemble.
- **La pile d'appels et la portée** : `top ▸ somme ▸ somme`, et `top ▸ binding ▸ case`. La seconde est le bloc que dessine la vue **Noms**, lu dans la même déclaration, donc les deux ne peuvent pas diverger.
- **Le Python émis**, au point le plus proche où il avait affiché autant. Les deux back-ends ne font pas les mêmes pas, sans correspondance exacte entre eux. Ils partagent l'affichage, qui sert donc à les aligner.
- **Ce qui a été affiché jusque-là.**

**↳** et **↰** entrent dans un *appel de fonction* et en sortent, en sautant les sous-expressions intermédiaires. C'est ce qu'un débogueur entend par là : ce qu'on veut quand c'est l'appel récursif que l'on suit. **Jusqu'au curseur** saute au premier pas situé dans ce que vous avez cliqué dans la source.

Une exécution longue arrête d'enregistrer au bout de cinq mille pas et le signale. Le programme va quand même à son terme ; seul l'enregistrement s'arrête.

## Partager

La barre d'adresse désigne toujours ce qui est dans la page. Un exemple tel quel a un lien court, comme `#example=fact`. Dès que vous le modifiez, l'adresse perd sa partie `#`, jusqu'à ce que vous cliquiez sur **Copier le lien** : il met tout votre programme dans l'URL après `#z=`, compressé, et le copie. Quiconque ouvre ce lien voit votre code.

Rien n'est stocké nulle part ; le programme voyage dans le lien lui-même, si bien qu'un long programme donne encore un long lien, d'environ un tiers de sa longueur en caractères.

## Quand quelque chose ne va pas

Les problèmes apparaissent dans un bandeau rouge au-dessus des vues, précédés de l'étape qui les a trouvés.

`syntax: 3:14: expected … found …`
:   L'analyseur s'est arrêté ligne 3, colonne 14, et énumère tout ce qui aurait pu venir ensuite. Le plus souvent, il manque un `in` ou un `->`, ou une `,` se trouve là où il fallait un `;`.

`names: 'foo' is not declared in vals`
:   Aucune définition ne porte ce nom. Vérifiez l'orthographe, puis que le `let` qui le définit vient bien *avant* dans le fichier : l'ordre compte au niveau global.

`types: TypingError: this has type … but … was expected`
:   Deux types devaient coïncider et ne coïncident pas. La cause la plus fréquente, et de loin, est le mélange de `int` et de `float` : OCaml a `+` et `+.`, deux opérateurs différents.

`interpreter: OCamlError: …`
:   Le programme a levé une exception que rien n'a rattrapée, exactement comme le vrai `ocaml` se serait arrêté.

Une étape qui échoue n'arrête pas les autres. Un programme qui ne type pas s'exécute quand même, et montre quand même ses portées. C'est souvent le moyen le plus rapide de comprendre : regardez **Noms** pour voir ce que le compilateur croit être en portée.

## Ce qu'il n'y a pas

Ce n'est pas un éditeur : rien ne complète, ne colore ni ne souligne votre code. C'est une zone de texte et six réponses.

Il manque les modules à vous, les objets et les foncteurs. L'[aide-mémoire](reference.md) dit ce qu'il y a.

Un programme qui tourne longtemps fige l'onglet, parce que tout s'exécute sur un seul fil. Rechargez la page pour l'arrêter.
