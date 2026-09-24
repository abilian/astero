# caml-prépa

**Un compilateur pour l'OCaml de prépa, que l'on peut regarder fonctionner.**

[Ouvrir le bac à sable](play/){ .md-button .md-button--primary }
[Commencer ici](getting-started.md){ .md-button }

---

## De quoi s'agit-il ?

C'est un vrai compilateur pour le sous-ensemble d'OCaml enseigné en classes préparatoires : `let rec`, filtrage, listes, tableaux, enregistrements, types sommes, références, boucles, exceptions.

Vous pouvez écrire un programme dans votre navigateur et l'exécuter. Jusque-là, rien d'extraordinaire : beaucoup de sites le font.

Celui-ci vous montre son travail. Tapez un programme : il vous dit, pour le même code, en même temps :

- **ce qu'il affiche**
- **quel type il a inféré** pour chaque définition, sans qu'on le lui dise
- **à quelle définition renvoie chaque nom**, sous forme d'arbre de portées
- **en quel Python il le compile**
- **comment il a lu ce que vous avez écrit**, réimprimé

Un compilateur, d'ordinaire, est une boîte noire : le source entre, un résultat sort, et avec un peu de chance un message d'erreur. Celui-ci vous laisse regarder à l'intérieur pendant qu'il travaille.

## Qu'est-ce que j'y gagne ?

**Si vous apprenez OCaml**, les deux choses sur lesquelles tout le monde bute sont les types et les portées. Ici, vous les voyez directement, avant tout message d'erreur.

Vous avez écrit une fonction et OCaml lui donne un type auquel vous ne vous attendiez pas ? Demandez quel type il a inféré, et pour quelle sous-expression. Vous ne savez plus à quel `x` renvoie le `x` de la ligne 12 ? L'arbre des portées le dit :

```
le programme entier          somme
  let somme · ligne 1        l
    cas de filtrage · ligne 3    —
    cas de filtrage · ligne 4    q, t
```

Autrement dit : le fichier définit `somme`, et `l` existe à l'intérieur. `q` et `t` existent dans le second cas du filtrage, et **là seulement**. Plus besoin de deviner.

**Si vous êtes curieux de savoir comment marche un compilateur**, celui-ci est assez petit pour se lire : environ 6 600 lignes de Python, organisées selon les trois parties que nomme n'importe quel cours de compilation. Un *front-end* transforme le texte en arbre, un *middle-end* détermine ce que l'arbre veut dire, et un *back-end* l'exécute. [Le second tutoriel](compiler/index.md) les parcourt toutes les trois en suivant un petit programme.

Si vous savez lire du Python, vous savez lire ce compilateur.

**Si vous voulez simplement essayer OCaml** sans rien installer, le bac à sable ne demande ni compte, ni installation, ni réseau une fois chargé. Rien de ce que vous tapez ne quitte votre navigateur.

## Ce que ce n'est pas

Ce n'est pas OCaml. C'est un compilateur *pédagogique* pour un sous-ensemble *pédagogique*, qui le dit là où il diffère. `int` est ici non borné, alors qu'il fait 63 bits dans le vrai. Un format de `Printf` doit être écrit là où il sert. Une récursion très profonde épuisera la pile là où OCaml tiendrait. L'[aide-mémoire](language/reference.md) en donne la liste complète.

Ce n'est pas non plus un éditeur : il ne complète pas votre code, ne le colore pas et ne souligne pas vos fautes. C'est une zone de texte et six réponses.

Si vous voulez le vrai OCaml pour vos TP, installez-le ; celui-ci sert à voir comment la chose fonctionne.

## Par où commencer

- **[Premiers pas](getting-started.md)**
  Lancer le bac à sable, l'installer chez vous, l'utiliser en ligne de commande.

- **[Visite guidée du langage](language/tour.md)**
  Ce que l'on peut écrire, de `let` au filtrage, pour quelqu'un qui connaît un peu Python.

- **[Le bac à sable](language/playground.md)**
  Ce que raconte chacun des six onglets, dont celui qui déroule une exécution pas à pas.

- **[Comment marche le compilateur](compiler/index.md)**
  Trois parties, un petit programme, suivi de bout en bout.


---

caml-prépa est un exemple complet construit sur [astero](https://astero.lab.abilian.com), une bibliothèque qui dérive d'une déclaration la façon dont un compilateur traite les noms. Le code est libre, sous licence Apache-2.0.
