(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch06_Automates_Finis
   at commit 920fdb39e1c7:
   solutions/Grimaud_Automaton/Automaton.ml
   solutions/Grimaud_Automaton/Grimaud_automaton.ml
   GPL-3.0, see LICENSE in this directory.
   Changed: the two files are concatenated, with an empty line between, and
   the line `open Automaton` is removed. Automaton.mli is left out. *)

(** Type representing a symbol in the automaton. *)
type symbol = char

(** Epsilon transition symbol, represented by the character with ASCII value 255. *)
let eps = char_of_int 255

(** Type representing an automaton. *)
type automaton = {
  alphabet : symbol list;       (** List of symbols that make up the alphabet of the automaton. *)
  states : int list;            (** List of states in the automaton. *)
  init_state : int;             (** Initial state of the automaton. *)
  final_states : int list;      (** List of final (accepting) states of the automaton. *)
  transitions : (int * symbol * int) list  (** List of transitions in the automaton, 
                                              each represented as a tuple (current_state, symbol, next_state). *)
}

(** Empty automaton. *)
let empty_automaton = {
  alphabet = [];       (** No symbols in the alphabet. *)
  states = [];         (** No states in the automaton. *)
  init_state = -1;     (** No initial state. *)
  final_states = [];   (** No final states. *)
  transitions = []     (** No transitions. *)
}

(** Checks the validity of the automaton.
    - The initial state must be part of the list of states.
    - Each final state must be part of the list of states.
    - Each transition must have source and destination states that are part of the list of states
      and must use a symbol that is part of the alphabet.
    - Each symbol in the alphabet must be used in at least one transition. *)
let check_automaton automaton =
  let valid = 
    if not (List.mem automaton.init_state automaton.states) then
     (Printf.printf "Erreur : L'état initial ne fait pas partie de la liste des états.\n"; false) 
    else true
  in
  let valid = List.fold_left (fun acc final_state ->
    if not (List.mem final_state automaton.states) then 
      (Printf.printf "Erreur : L'état final %d ne fait pas partie de la liste des états.\n" final_state; false)
    else
      acc
    ) valid automaton.final_states
  in 
  let valid = List.fold_left (fun acc (from_state, symbol, to_state) ->
    if not (List.mem from_state automaton.states) then 
      (Printf.printf "Erreur : L'état source %d d'une transition ne fait pas partie de la liste des états.\n" from_state ;false)
    else if not (List.mem to_state automaton.states) then
      (Printf.printf "Erreur : L'état destination %d d'une transition ne fait pas partie de la liste des états.\n" to_state ;false)
    else if symbol<>eps && not (List.mem symbol automaton.alphabet) then (
      Printf.printf "Erreur : Le symbole '%s' utilisé dans une transition ne fait pas partie de l'alphabet.\n" (Char.escaped symbol);false
    ) else
      acc
    ) valid automaton.transitions
  in
  List.iter (fun symbol ->
    if not (List.exists (fun (_, s, _) -> s = symbol) automaton.transitions) then
      Printf.printf "Warning : Le symbole '%s' n'est pas utilisé dans les transitions."  (Char.escaped symbol)
    ) automaton.alphabet ;
  valid
  
(** Function to print a symbol (char). *)
let print_symbol s =
  if s = eps then
    print_string "eps"
  else
    print_char s

(** Function to print a list of symbols. *)
let print_symbol_list lst =
  print_string "[";
  List.iter (fun s -> print_symbol s; print_string " ") lst;
  print_string "]"

(** Function to print a list of integers. *)
let print_int_list lst =
  print_string "[";
  List.iter (fun s -> print_int s; print_string " ") lst;
  print_string "]"

(** Function to print transitions. *)
let print_transitions transitions =
  List.iter (fun (current_state, symbol, next_state) ->
    print_string "(";
    print_int current_state;
    print_string ", ";
    print_symbol symbol;
    print_string ", ";
    print_int next_state;
    print_string ")";
    print_newline ()
  ) transitions

(** Function to print the automaton fields. *)
let print_automaton (a: automaton) =
  print_string "Alphabet: ";
  print_symbol_list a.alphabet;
  print_newline ();

  print_string "States: ";
  print_int_list a.states;
  print_newline ();

  print_string "Initial state: ";
  print_int a.init_state;
  print_newline ();

  print_string "Final states: ";
  print_int_list a.final_states;
  print_newline ();

  print_string "Transitions: \n";
  print_transitions a.transitions;
  print_newline ()


(** Adds a state to the automaton. If the state already exists, the automaton remains unchanged. *)
let add_state automaton state =
  if List.mem state automaton.states then
    automaton
  else
    { automaton with states = state :: automaton.states }

(** Adds a state to the list of final states of the automaton. 
    If the state is already a final state, the automaton remains unchanged. *)
let add_final_state automaton state =
  if List.mem state automaton.final_states then
    automaton
  else
    { automaton with final_states = state :: automaton.final_states }

(** Adds a transition to the automaton. If the transition already exists, 
    the automaton remains unchanged. *)
let add_transition automaton transition =
  if List.mem transition automaton.transitions then
    automaton
  else
    { automaton with transitions = transition :: automaton.transitions }

(** Removes a transition from the automaton. If the transition does not exist, 
    the automaton remains unchanged. *)
let remove_transition automaton transition =
  let new_transitions = List.filter (fun t -> t <> transition) automaton.transitions in
  { automaton with transitions = new_transitions }

(** Checks if the given automaton is deterministic. 
    An automaton is deterministic if:
    1. There are no epsilon transitions.
    2. There are no multiple transitions with the same symbol from a state. *)
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

(** Completes the automaton by adding a sink state and necessary transitions to ensure
    that every state has a transition defined for each symbol in the alphabet.
    The function assumes that the input automaton is deterministic. *)
let complete automaton =
  assert (is_deterministic automaton);
  (* Find a new sink state that is not currently used in the automaton *)
  let sink_state =
    let rec aux n =
      if List.mem n automaton.states then
        aux (n + 1)
      else
        n
    in
    aux 0
  in
  (* Add missing transitions to ensure each state has a transition for every symbol *)
  let add_missing_transitions transitions =
    List.fold_left (fun acc state ->
      List.fold_left (fun acc symbol ->
        if not (List.exists (fun (src, sym, _) -> src = state && sym = symbol) automaton.transitions) then
          (state, symbol, sink_state) :: acc
        else
          acc
      ) acc automaton.alphabet
    ) transitions automaton.states
  in
  (* Create transitions for the sink state that loop on itself for each symbol *)
  let sink_loops = List.map (fun symbol -> (sink_state, symbol, sink_state)) automaton.alphabet in
  (* Combine the new transitions with the existing ones and the sink loops *)
  let new_transitions = (add_missing_transitions automaton.transitions) @ sink_loops in
  (* Construct the new completed automaton *)
  {
    alphabet = automaton.alphabet;
    states = sink_state :: automaton.states; 
    init_state = automaton.init_state;
    final_states = automaton.final_states; 
    transitions = new_transitions
  }

(** Computes the list of states that are accessible from the initial state of the automaton. *)
let accessible_states automaton =
  (* Helper function to add the next states reachable from the current set of states *)
  let rec add_next_states transitions acc =
    match transitions with
    | [] -> acc
    | (i, _, j) :: tail when (List.mem i acc) && not (List.mem j acc) ->
      add_next_states tail (j :: acc)
    | _ :: tail -> add_next_states tail acc
  in
  (* Recursive function to keep expanding the set of accessible states until no new states are added *)
  let rec aux acc =
    let new_acc = add_next_states automaton.transitions acc in
    if new_acc = acc then
      acc
    else
      aux new_acc
  in
  aux [automaton.init_state]

(** Computes the list of states from which a final state is accessible in the automaton. *)
let coaccessible_states automaton =
  (* Helper function to add the previous states that can reach the current set of states *)
  let rec add_next_states transitions acc =
    match transitions with
    | [] -> acc
    | (i, _, j) :: tail when (List.mem j acc) && not (List.mem i acc) ->
      add_next_states tail (i :: acc)
    | _ :: tail -> add_next_states tail acc
  in
  (* Recursive function to keep expanding the set of coaccessible states until no new states are added *)
  let rec aux acc =
    let new_acc = add_next_states automaton.transitions acc in
    if new_acc = acc then
      acc
    else
      aux new_acc
  in
  aux automaton.final_states

(** Prunes the automaton by removing states and transitions that are not useful.
    A state is considered useful if it is both accessible and coaccessible.
    The function assumes that the input automaton is deterministic. *)
let prune automaton =
  assert (is_deterministic automaton);
  (* Compute the accessible and coaccessible states *)
  let acc_states = accessible_states automaton in
  let coacc_states = coaccessible_states automaton in
  (* Filter the states that are both accessible and coaccessible *)
  let useful_states = List.filter (fun x -> List.mem x coacc_states) acc_states in
  (* Filter the transitions to only include those between useful states *)
  let new_transitions = List.filter (fun (src, _, dst) ->
      List.mem src useful_states && List.mem dst useful_states
    ) automaton.transitions in
  (* Construct the new pruned automaton *)
  {
    alphabet = automaton.alphabet;
    states = useful_states; 
    init_state = automaton.init_state;
    final_states = List.filter (fun x -> List.mem x useful_states) automaton.final_states;
    transitions = new_transitions
  }

(** Removes epsilon transitions from the automaton.
    This includes removing epsilon loops and cloning transitions where necessary. *)
let remove_epsilon_transitions automaton =
  (* Produces an automaton without epsilon loops *)
  let remove_epsilon_loop automaton =
    let is_epsilon_loop (source, symbol, dest) =
      symbol = eps && source = dest
    in
    let new_transitions = List.filter (fun t -> not (is_epsilon_loop t)) automaton.transitions in
    { automaton with transitions = new_transitions }
  in
  (* Returns an automaton where all transitions from `from_state` also exist as transitions from `to_state` *)
  let clone_transitions from_state to_state automaton =
    let add_cloned_transition automaton (source, symbol, dest) =
      if source = to_state then
        add_transition automaton (from_state, symbol, dest)
      else
        automaton
    in
    List.fold_left add_cloned_transition automaton automaton.transitions
  in
  (* Step 1: Remove epsilon loops *)
  let automaton = remove_epsilon_loop automaton in
  (* Function to process each state, transforming the given automaton into a new one *)
  let process_state automaton current_state =
    (* Find all epsilon transitions leading to current_state *)
    let epsilon_transitions_to_current = 
      List.filter (fun (from_state, symbol, to_state) -> symbol = eps && to_state = current_state) automaton.transitions 
    in
    (* Step 2a: Update final states *)
    let final_states =
      List.fold_left (fun acc (from_state, _, _) -> 
        if List.mem current_state automaton.final_states && not (List.mem from_state automaton.final_states) then 
          from_state :: acc 
        else 
          acc
      ) automaton.final_states epsilon_transitions_to_current
    in
    (* Step 2b: Remove epsilon transitions to current_state *)
    let automaton = 
      List.fold_left (fun acc transition -> 
        remove_transition acc transition
      ) automaton epsilon_transitions_to_current
    in
    (* Step 2c: Clone transitions *)
    let automaton = 
      List.fold_left (fun acc (from_state, s, d) ->
        clone_transitions from_state current_state acc
      ) automaton epsilon_transitions_to_current
    in
    { automaton with final_states = final_states }
  in
  (* Traverse all states of the automaton and transform it step by step *)
  List.fold_left process_state automaton automaton.states

    
(** Finds the list of output symbols for the given states in the automaton.
    An output symbol is one that appears in a transition originating from any of the given states. *)
let find_output_symbols automaton states =
   let add_output_symbol symbols (from_state, symbol, _) =
    if List.mem from_state states && not (List.mem symbol symbols) then
      symbol :: symbols
    else
      symbols
  in
  List.fold_left add_output_symbol [] automaton.transitions
  
(** Finds the list of output states for the given states and symbol in the automaton.
    An output state is a state that can be reached by a transition with the specified symbol
    originating from any of the given states. The resulting list of states is sorted. *)
let find_output_states_for_symbol automaton states symbol =
  (* Helper function to add an output state if the transition matches the criteria *)
  let add_output_state output_states (from_state, transition_symbol, to_state) =
    if List.mem from_state states && transition_symbol = symbol && not (List.mem to_state output_states) then
      to_state :: output_states
    else
      output_states
  in
  (* Accumulate output states that can be reached by the specified symbol *)
  let output_states = List.fold_left add_output_state [] automaton.transitions in
  (* Sort and return the list of output states *)
  List.sort compare output_states
  

(** Determinizes the given automaton by removing epsilon transitions, 
    initializing the structures for the determinized automaton, 
    and processing the multiple successors. *)
let determinize automaton =
  (* Step 1: Remove epsilon transitions *)
  let awe = remove_epsilon_transitions automaton in
  (* Step 2: Initialize the structures for the determinized automaton *)
  let state_counter = ref 0 in
  let dt_automaton = {
    alphabet = awe.alphabet;
    states = [!state_counter];
    init_state = !state_counter;
    final_states = if List.mem awe.init_state awe.final_states then [!state_counter] else [];
    transitions = []
  } in
  let initial_state = [awe.init_state] in
  (* Step 3: Initialize the hash table *)
  let nsh = Hashtbl.create 100 in
  Hashtbl.add nsh initial_state !state_counter ;
  let get_state_for_states states =
    match (Hashtbl.find_opt nsh states) with
    | Some state -> (false, state)
    | None -> (incr state_counter ; Hashtbl.add nsh states !state_counter ; (true, !state_counter))
  in
  (* Step 4: Recursive processing of generated successors states *)
  let rec process_state dt_automaton states = 
    match states with
    | [] -> dt_automaton
    | _ -> ( 
      let (is_new, from_state) = get_state_for_states states in
      assert(not is_new) ; 
      let symbols = find_output_symbols awe states in
      let dt_automaton = List.fold_left (fun acc x -> 
        let to_states = find_output_states_for_symbol awe states x in
        let (is_new, to_state) = get_state_for_states to_states in
        if is_new then (
          let final_states = 
            if (List.filter (fun x -> List.mem x awe.final_states) to_states) <> [] then 
              to_state :: acc.final_states 
            else 
              acc.final_states 
          in
          let new_dt_automaton = 
            add_transition {acc with states = to_state :: acc.states ; final_states = final_states} (from_state, x, to_state) 
          in
          process_state new_dt_automaton to_states 
        ) else
          add_transition acc (from_state, x, to_state)
      ) dt_automaton symbols in
      dt_automaton )
  in
  (* Start the recursive processing with initial state alone *)
  process_state dt_automaton initial_state
















(* Automaton 1 - deterministic *)
(* Binary representation of even numbers *)
let automaton1 : automaton =
  {
    alphabet = ['0';'1'];
    states = [0; 1];
    init_state = 0; 
    final_states = [1];
    transitions = [(0,'0',1);(0,'1',0);(1,'0',1);(1,'1',0)]
  }

(* Automaton 2 - deterministic non pruned *)
(* Language a*b*(eps|c) *)
let automaton2 =
  {
    alphabet = ['a'; 'b'; 'c'];
    states = [0;1;2;3;4];
    init_state = 0;
    final_states = [0;1;2;3];
    transitions = [(0,'a',1);(0,'b',2);(0,'c',3);(1,'a',1);(1,'b',2);(1,'c',3);(2,'a',4);(2,'b',2);(2,'c',3);(3,'a',4);(3,'b',4);(3,'c',4)]
  }

(* Automaton 3 - deterministic pruned, not complet *)
(* Language a*b*(eps|c) *)
let automaton3 =
  {
    alphabet = ['a'; 'b'; 'c'];
    states = [0;1;2];
    init_state = 0;
    final_states = [0;1;2];
    transitions = [(0,'a',0);(0,'b',1);(0,'c',2);(1,'b',1);(1,'c',2)]
  }

(* Automaton 4 - non deterministic without eps-transitions *)
(* Language a*b*(eps|c) *)
let automaton4 =
  {
    alphabet = ['a'; 'b'; 'c'];
    states = [0;1;2;3;4;5;6;7;8;9;10;11];
    init_state = 0;
    final_states = [0;1;2;4;5;7;9;11];
    transitions = [(0,'a',5);(0,'a',6);(0,'a',8);(0,'b',2);(0,'b',3);(0,'c',1);(2,'b',2);(3,'b',3);(3,'c',4);(5,'a',5);(6,'a',6);(6,'c',7);(8,'a',8);(8,'b',9);(8,'b',10);(9,'b',9);(10,'b',10);(10,'c',11)]
  }

(* Automaton 5 - non deterministic with eps-transitions *)
(* Language a*b*(eps|c) *)
let automaton5 : automaton =
  {
    alphabet = ['a'; 'b'; 'c'];
    states = [0;1;2;3;4;5];
    init_state = 0;
    final_states = [0;1;2;5];
    transitions = [(0,eps,1);(0,eps,3);(1,'a',1);(1,'b',2);(2,'b',2);(3,'a',3);(3,'b',4);(3,'c',5);(4,'b',4);(4,'c',5)]
  }



let () =
  (* Automatons *)
  Printf.printf "check_automaton\n";
  Printf.printf "%B %B %B %B %B\n" (check_automaton automaton1) (check_automaton automaton2) (check_automaton automaton3) (check_automaton automaton4) (check_automaton automaton5);
  print_automaton automaton1;
  print_automaton automaton2;
  print_automaton automaton3;
  print_automaton automaton4;
  print_automaton automaton5;
  Printf.printf "is_deterministic\n";
  Printf.printf "%B %B %B %B %B\n" (is_deterministic automaton1) (is_deterministic automaton2) (is_deterministic automaton3) (is_deterministic automaton4) (is_deterministic automaton5);
  let automaton3_complete = complete automaton3 in
  print_automaton automaton3_complete;
  Printf.printf "\n Accessible states of automaton1 : ";
  List.iter (fun x -> Printf.printf "%d " x) (accessible_states automaton1);
  Printf.printf "\n Accessible states of automaton2 : ";
  List.iter (fun x -> Printf.printf "%d " x) (accessible_states automaton2);
  Printf.printf "\n Accessible states of automaton3 : ";
  List.iter (fun x -> Printf.printf "%d " x) (accessible_states automaton3);
  Printf.printf "\n Accessible states of automaton4 : ";
  List.iter (fun x -> Printf.printf "%d " x) (accessible_states automaton4);
  Printf.printf "\n Accessible states of automaton5 : ";
  List.iter (fun x -> Printf.printf "%d " x) (accessible_states automaton5);
  Printf.printf "\n Co-accessible states of automaton1 : ";
  List.iter (fun x -> Printf.printf "%d " x) (coaccessible_states automaton1);
  Printf.printf "\n Co-accessible states of automaton2 : ";
  List.iter (fun x -> Printf.printf "%d " x) (coaccessible_states automaton2);
  Printf.printf "\n Co-accessible states of automaton3 : ";
  List.iter (fun x -> Printf.printf "%d " x) (coaccessible_states automaton3);
  Printf.printf "\n Co-accessible states of automaton4 : ";
  List.iter (fun x -> Printf.printf "%d " x) (coaccessible_states automaton4);
  Printf.printf "\n Co-accessible states of automaton5 : ";
  List.iter (fun x -> Printf.printf "%d " x) (coaccessible_states automaton5);
  Printf.printf "\n";
  let automaton2_pruned = prune automaton2 in
  print_automaton automaton2_pruned;
  let automaton5_without_eps = remove_epsilon_transitions automaton5 in
  let automaton5_without_eps_determinized = determinize automaton5_without_eps in
  let automaton5_without_eps_determinized_complete = complete automaton5_without_eps_determinized in
  print_automaton automaton5_without_eps;
  print_automaton automaton5_without_eps_determinized;
  print_automaton automaton5_without_eps_determinized_complete
  
  
  
