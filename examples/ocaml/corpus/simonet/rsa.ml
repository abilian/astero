(* Cryptographie à clef publique RSA.  D'après le TP 3 de Vincent Simonet
   (MPSI, 2002) : l'algorithme d'Euclide et son extension, la fabrication
   d'un couple de clefs, puis le codage et le décodage.

   Les nombres restent petits pour que le calcul tienne dans un entier :
   un vrai RSA travaille sur des centaines de chiffres. *)

let rec pgcd a b = if b = 0 then a else pgcd b (a mod b)

(* Euclide étendu : bezout a b rend (d, u, v) avec a u + b v = d = pgcd. *)
let rec bezout a b =
  if b = 0 then (a, 1, 0)
  else
    let d, u, v = bezout b (a mod b) in
    (d, v, u - (a / b * v))

exception Non_inversible

(* L'inverse de a modulo n, quand a et n sont premiers entre eux. *)
let inverse a n =
  let d, u, _ = bezout a n in
  if d <> 1 then raise Non_inversible else ((u mod n) + n) mod n

(* Exponentiation rapide modulaire : on carre au lieu de multiplier n fois,
   et on réduit à chaque étape pour que rien ne grossisse. *)
let rec puissance a k n =
  if k = 0 then 1
  else
    let c = puissance a (k / 2) n in
    let c2 = c * c mod n in
    if k mod 2 = 0 then c2 else c2 * a mod n

(* Une clef publique (n, e) et la clef secrète (n, d) associée.  p et q
   sont deux nombres premiers, et l'indicatrice d'Euler de n = p q vaut
   (p-1)(q-1) : c'est elle qui relie e et d. *)
type clefs = { n : int; e : int; d : int }

let fabrique p q e =
  let n = p * q in
  let phi = (p - 1) * (q - 1) in
  if pgcd e phi <> 1 then raise Non_inversible;
  { n; e; d = inverse e phi }

let code c m = puissance m c.e c.n
let decode c m = puissance m c.d c.n

(* Un message est une suite de codes de caractères, chacun plus petit que
   n pour rester lisible modulo n. *)
let code_texte c texte =
  List.map (fun i -> code c (Char.code texte.[i]))
    (List.init (String.length texte) (fun i -> i))

let decode_texte c codes =
  String.concat "" (List.map (fun m -> String.make 1 (Char.chr (decode c m))) codes)

let () =
  print_int (pgcd 1071 462);
  print_char ' ';
  let d, u, v = bezout 1071 462 in
  print_int d;
  print_char ' ';
  print_int ((1071 * u) + (462 * v));
  print_char ' ';
  print_int (inverse 17 3120);
  print_newline ();
  (* L'exemple canonique : p = 61, q = 53, e = 17. *)
  let c = fabrique 61 53 17 in
  print_int c.n;
  print_char ' ';
  print_int c.e;
  print_char ' ';
  print_int c.d;
  print_newline ();
  print_int (code c 65);
  print_char ' ';
  print_int (decode c (code c 65));
  print_newline ();
  let m = code_texte c "CAML" in
  List.iter
    (fun k ->
      print_int k;
      print_char ' ')
    m;
  print_newline ();
  print_string (decode_texte c m);
  print_char ' ';
  print_string (if decode_texte c m = "CAML" then "identique" else "different");
  print_newline ()
