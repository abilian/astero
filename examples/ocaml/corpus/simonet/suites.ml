(* Suites récurrentes.  D'après le TP 1 de Vincent Simonet (MPSI, 2001 et
   2002) : trois calculs de la suite de Fibonacci, de coût exponentiel,
   linéaire puis logarithmique, et deux familles de suites récurrentes. *)

(* Coût exponentiel : chaque appel en fait deux, et recalcule tout. *)
let rec fib_exponentiel n =
  if n < 2 then n else fib_exponentiel (n - 1) + fib_exponentiel (n - 2)

(* Coût linéaire : on garde les deux derniers termes et on avance. *)
let fib_lineaire n =
  let a = ref 0 and b = ref 1 in
  for i = 1 to n do
    let suivant = !a + !b in
    a := !b;
    b := suivant
  done;
  !a

(* Coût logarithmique : (F(2k), F(2k+1)) se déduit de (F(k), F(k+1)) sans
   passer par les termes intermédiaires. *)
let rec couple n =
  if n = 0 then (0, 1)
  else
    let a, b = couple (n / 2) in
    let c = a * ((2 * b) - a) and d = (a * a) + (b * b) in
    if n mod 2 = 0 then (c, d) else (d, c + d)

let fib_logarithmique n = fst (couple n)

(* Suites u_{n+1} = f(u_n) : n itérations de f à partir de u_0. *)
let rec itere f u n = if n = 0 then u else itere f (f u) (n - 1)

(* Suites récurrentes linéaires d'ordre 2 : u_{n+2} = a u_{n+1} + b u_n. *)
let lineaire_ordre2 a b u0 u1 n =
  let p = ref u0 and q = ref u1 in
  for i = 1 to n do
    let suivant = (a * !q) + (b * !p) in
    p := !q;
    q := suivant
  done;
  !p

(* Les termes u_0 à u_{n-1}, pour regarder une suite plutôt qu'un terme. *)
let premiers f n =
  let t = Array.make n 0 in
  for i = 0 to n - 1 do
    t.(i) <- f i
  done;
  t

let affiche t =
  Array.iter
    (fun v ->
      print_int v;
      print_char ' ')
    t;
  print_newline ()

let () =
  affiche (premiers fib_exponentiel 10);
  affiche (premiers fib_lineaire 10);
  affiche (premiers fib_logarithmique 10);
  print_int (fib_logarithmique 40);
  print_newline ();
  (* u_{n+1} = 3 u_n + 1, à partir de u_0 = 0. *)
  print_int (itere (fun u -> (3 * u) + 1) 0 5);
  print_char ' ';
  (* Lucas : u_{n+2} = u_{n+1} + u_n, u_0 = 2, u_1 = 1. *)
  print_int (lineaire_ordre2 1 1 2 1 10);
  print_newline ()
