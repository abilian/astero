(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch08_Automates_Finis_2
   at commit 0032feeccdef:
   solutions/Grimaud_automaton.ml
   GPL-3.0, see LICENSE in this directory.
   Changed: `let () =`, which read `Sys.argv`, is `let main argv =` and
   reads `argv`, with a comment of two lines above it; a new `let () =` at
   the end calls `main` on six command lines. *)

type symbol = char
let eps = char_of_int 255

type automaton = {
  alphabet : symbol list;
  states : int list; 
  init_state : int;
  final_states : int list; 
  transitions : (int * symbol * int) list
}

let automaton_even =
  {
    alphabet = ['0';'1'];
    states = [0; 1];
    init_state = 0;
    final_states = [1];
    transitions = [(0,'0',1);(0,'1',0);(1,'0',1);(1,'1',0)]
  }

let automaton_float =
  {
    alphabet = ['0'; '1'; '2'; '3'; '4'; '5'; '6'; '7'; '8'; '9'; '.'];
    states = [0; 1; 2; 3];
    init_state = 0;
    final_states = [1; 3];
    transitions = [(0,'0',1);(0,'1',1);(0,'2',1);(0,'3',1);(0,'4',1);(0,'5',1);(0,'6',1);(0,'7',1);(0,'8',1);(0,'9',1);(1,'0',1);(1,'1',1);(1,'2',1);(1,'3',1);(1,'4',1);(1,'5',1);(1,'6',1);(1,'7',1);(1,'8',1);(1,'9',1);(1,'.',2);(2,'0',3);(2,'1',3);(2,'2',3);(2,'3',3);(2,'4',3);(2,'5',3);(2,'6',3);(2,'7',3);(2,'8',3);(2,'9',3);(3,'0',3);(3,'1',3);(3,'2',3);(3,'3',3);(3,'4',3);(3,'5',3);(3,'6',3);(3,'7',3);(3,'8',3);(3,'9',3)]
  }

let is_deterministic automaton =
  (* Check that there are no epsilon transitions *)
  let no_epsilon_transitions =
    List.for_all (fun (_, s, _) -> s <> eps) automaton.transitions
  in
  (* Function to check that there are no multiple transitions with the same symbol from a state *)
  let unique_transitions transitions =
    let rec check seen = function
      | [] -> true
      | (src, sym, _) :: rest ->
        if List.exists (fun (s, sy) -> s = src && sy = sym) seen then
          false
        else
          check ((src, sym) :: seen) rest
    in
    check [] transitions
  in
  no_epsilon_transitions && unique_transitions automaton.transitions

let process_det_automaton (automaton:automaton) (get_char:unit -> char option) =
  assert (is_deterministic automaton);
  let get_dest_state transitions curr_src curr_sym =
  try
    let (_, _, dest) =
      List.find
        (fun (src, s, _) -> src = curr_src && s = curr_sym)
        transitions in
    Some dest
  with
  | Not_found -> None
  in 
  let get_symbol () =
    match get_char () with
    | Some c -> if (List.mem c automaton.alphabet) then Some c else None
    | None -> None 
  in
  let rec process_state current_state =
    match get_symbol() with
    | None -> List.mem current_state automaton.final_states
    | Some sym ->
      let state = get_dest_state automaton.transitions current_state sym in
      match state with
      | Some s -> process_state s 
      | None -> false
  in
  process_state automaton.init_state

  
(* caml-prépa: the command line is a parameter, and the runs below are
   what the corpus passes it. *)
let main argv =
  if Array.length argv <> 3 then
    Printf.printf "Usage: %s <string> <even|float>\n" argv.(0)
  else
    let word = argv.(1) in
    let prog = argv.(2) in
    let position = ref (-1) in
    let get_char () =
      incr position;
      if !position >= String.length word then
        None
      else
        Some word.[!position]
    in
    let is_in_language =
      match prog with
      | "even" -> process_det_automaton automaton_even get_char 
      | "float" -> process_det_automaton automaton_float get_char
      | _ -> failwith "Wrong argument."
    in
    let processed_word = String.sub word 0 !position in
    if is_in_language then
      Printf.printf "Word %s is accepted by the automaton.\n" processed_word
    else
      Printf.printf "Word %s is rejected by the automaton.\n" processed_word

let () =
  List.iter main [
    [| "automaton" |];
    [| "automaton"; "0110"; "even" |];
    [| "automaton"; "0111"; "even" |];
    [| "automaton"; "3.14"; "float" |];
    [| "automaton"; "3."; "float" |];
    [| "automaton"; "12a4"; "float" |];
  ]
