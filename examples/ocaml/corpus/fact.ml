(* Factorial, three ways: recursive, tail-recursive, imperative. *)

let rec fact n = if n <= 1 then 1 else n * fact (n - 1)

let fact_tail n =
  let rec go acc k = if k <= 1 then acc else go (acc * k) (k - 1) in
  go 1 n

let fact_loop n =
  let r = ref 1 in
  for i = 2 to n do
    r := !r * i
  done;
  !r

let () =
  print_int (fact 5);
  print_newline ();
  print_int (fact_tail 5);
  print_newline ();
  print_int (fact_loop 5);
  print_newline ()
