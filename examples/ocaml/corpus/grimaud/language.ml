(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch01_Langages_Reguliers
   at commit 5a832f5e7fef:
   solutions/Grimaud_language.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

type symbol = A | T | C | G

type word = symbol list

type regexp =
  | Epsilon
  | Symbol of symbol
  | Union of regexp * regexp
  | Concat of regexp * regexp
  | Kleene of regexp

(* Function to split a list into two at a given position *)
let rec split_at n (w:word) : (word*word) =
  if n <= 0 then ([], w)
  else match w with
    | [] -> ([], [])
    | x :: xs -> 
        let (l1, l2) = split_at (n - 1) xs in
        (x :: l1, l2)

(* Function to split a list into two at each possible position *)
let split (w:word) =
  let rec aux i acc =
    if i > List.length w then acc
    else
      let (w1, w2) = split_at i w in
      aux (i + 1) ((w1, w2) :: acc)
  in
  aux 0 []

(* Evaluation function *)
let rec match_regexp re w =
  match re, w with
  | Epsilon, [] -> true
  | Epsilon, _ -> false
  | Symbol s, [c] -> s = c
  | Symbol _, _ -> false
  | Union (re1, re2), _ -> match_regexp re1 w || match_regexp re2 w
  | Concat (re1, re2), _ ->
    List.exists
      (fun (w1, w2) -> match_regexp re1 w1 && match_regexp re2 w2)
      (split w)
  | Kleene re, [] -> true
  | Kleene re, _ ->
    List.exists
      (fun (w1, w2) -> match_regexp re w1 && match_regexp (Kleene re) w2)
      (split w)


(* (A|T)*G *)
let e = Concat (Kleene (Union (Symbol A, Symbol T)), Symbol G)

let () =
  let test_word w =
    let result = match_regexp e w in
    Printf.printf "Word %s matches: %b\n"
      (String.concat "" (List.map (function A -> "A" | T -> "T" | C -> "C" | G -> "G") w))
      result
  in
  test_word [T; T; G];
  test_word [A; T; A; G];
  test_word [C; G];
  test_word [A; T; T; C]
