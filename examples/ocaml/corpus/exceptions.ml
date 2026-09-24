(* Exceptions: declared with and without a payload, raised, caught. *)

exception Not_a_number of string

exception Too_big of int * int

exception Stop

let parse_digit c =
  if c >= '0' && c <= '9' then int_of_char c - int_of_char '0'
  else raise (Not_a_number (String.make 1 c))

let checked limit n = if n > limit then raise (Too_big (n, limit)) else n

let safe_div a b = try Some (a / b) with Division_by_zero -> None

let describe c =
  try string_of_int (parse_digit c) with
  | Not_a_number s -> "not a digit: " ^ s
  | Failure m -> m

let first_over limit l =
  let answer = ref (-1) in
  try
    List.iter (fun n -> if n > limit then (answer := n; raise Stop)) l;
    !answer
  with Stop -> !answer

let () =
  print_string (describe 'x');
  print_newline ();
  print_int (first_over 3 [ 1; 5; 2 ]);
  print_newline ();
  (match safe_div 1 0 with Some n -> print_int n | None -> print_string "none")
