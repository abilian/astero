(* Strings and characters, and a while loop. *)

let upper s = String.uppercase_ascii s

let char_at s i = s.[i]

let count c s =
  let n = ref 0 in
  let i = ref 0 in
  while !i < String.length s do
    if s.[!i] = c then incr n;
    incr i
  done;
  !n

let reverse s =
  let n = String.length s in
  let out = Array.make n ' ' in
  for i = 0 to n - 1 do
    out.(i) <- s.[n - 1 - i]
  done;
  out

let words s = String.split_on_char ' ' s

let initials s =
  List.map (fun w -> if String.length w = 0 then '?' else w.[0]) (words s)

let () =
  print_string (upper "bonjour");
  print_newline ();
  print_int (count 'o' "bonjour");
  print_char (char_at "abc" 1)
