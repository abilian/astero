(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Projet_Calculatrice
   at commit 4a063322aab4:
   solutions/Grimaud_sci_calculator3.ml
   GPL-3.0, see LICENSE in this directory.
   Changed: `session` and a `read_line` that shadows the standard one, with
   a comment of three lines above them, are inserted before the last
   `let () =`, so the loop reads a scripted session in place of standard
   input. The loop itself is unchanged. *)

(* Lexical error exception *)
exception LexicalError of string

(* Syntax error exception *)
exception SyntaxError of string

type binary_operation = Plus | Minus | Times | DividedBy
type unary_operation = Neg | Cos | Sin | Tan

type expression =
  | Number of string
  | ConstPi
  | ConstE
  | BinOp of expression * binary_operation * expression
  | UnOp of unary_operation * expression

type symbol = char
let eps = char_of_int 255

type automaton = {
  alphabet : symbol list;
  states : int list; 
  init_state : int;
  final_states : int list; 
  transitions : (int * symbol * int) list
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


let automaton_float =
  {
    alphabet = ['0'; '1'; '2'; '3'; '4'; '5'; '6'; '7'; '8'; '9'; '.'];
    states = [0; 1; 2; 3];
    init_state = 0;
    final_states = [1; 3];
    transitions = [(0,'0',1);(0,'1',1);(0,'2',1);(0,'3',1);(0,'4',1);(0,'5',1);(0,'6',1);(0,'7',1);(0,'8',1);(0,'9',1);(1,'0',1);(1,'1',1);(1,'2',1);(1,'3',1);(1,'4',1);(1,'5',1);(1,'6',1);(1,'7',1);(1,'8',1);(1,'9',1);(1,'.',2);(2,'0',3);(2,'1',3);(2,'2',3);(2,'3',3);(2,'4',3);(2,'5',3);(2,'6',3);(2,'7',3);(2,'8',3);(2,'9',3);(3,'0',3);(3,'1',3);(3,'2',3);(3,'3',3);(3,'4',3);(3,'5',3);(3,'6',3);(3,'7',3);(3,'8',3);(3,'9',3)]
  }

let rec read_token str =
  let n = String.length str in
  if n=0 then
    (None, str)
  else
    match str.[0] with
    | ' ' -> read_token (String.sub str 1 (n-1))
    | 'c' when n >= 3 && String.sub str 0 3 = "cos" ->
      (Some "cos", String.sub str 3 (n - 3))
    | 's' when n >= 3 && String.sub str 0 3 = "sin" ->
      (Some "sin", String.sub str 3 (n - 3))
    | 't' when n >= 3 && String.sub str 0 3 = "tan" ->
      (Some "tan", String.sub str 3 (n - 3))
    | 'p' when n >= 2 && String.sub str 0 2 = "pi" ->
      (Some "pi", String.sub str 2 (n - 2))
    | 'e' ->
      (Some "e", String.sub str 1 (n - 1))
    | '(' | ')' | '+' | '-' | '*' | '/' -> (Some (String.sub str 0 1), String.sub str 1 (n-1))
    | _ ->
      let position = ref (-1) in
      let get_char () =
        incr position;
        if !position >= String.length str then
          None
        else
          Some str.[!position]
      in
      if process_det_automaton automaton_float get_char then
        (Some (String.sub str 0 !position),
         String.sub str !position (n-(!position)))
      else
        let error_msg =
          if !position < n then
            Printf.sprintf "Unexpected symbol: %c" str.[!position]
          else
            Printf.sprintf "More symbol expected"
        in
        raise (LexicalError error_msg)

let parser str =
  let rec parserE str =
    let (term, tail_term) = parserT str in
    match term with
    | Some t ->
      let (token, tail_token) = read_token tail_term in
      begin
        match token with
        | Some "+" | Some "-" ->
          let (exp, tail_exp) = parserE tail_token in
          begin
            match exp with
            | Some e ->
              let op = if token = Some "+" then Plus else Minus in
              (Some (BinOp (t, op, e)), tail_exp)
            | None -> (None, tail_token)
          end 
        | _ -> (term, tail_term)
      end
    | None -> (None, str)
  and parserT str =
    let (fact, tail_fact) = parserF str in
    match fact with
    | Some f ->
      let (token, tail_token) = read_token tail_fact in
      begin
        match token with
        | Some "*" | Some "/" ->
          let (term, tail_term) = parserT tail_token in
          begin
            match term with
            | Some t ->
              let op = if token = Some "*" then Times else DividedBy in
              (Some (BinOp (f, op, t)), tail_term)
            | None -> (None, tail_token)
          end 
        | _ -> (fact, tail_fact)
      end;
    | None -> (None, str)
  and parserF str = 
    let (token, tail_token) = read_token str in
    match token with
    | Some "-" ->
      let (fact, tail_fact) = parserF tail_token in
      begin
        match fact with
        | Some f -> (Some (UnOp (Neg, f)), tail_fact)
        | None -> (None, str)
      end
    | Some "(" ->
      let (exp, tail_exp) = parserE tail_token in
      begin
        match exp with
        | Some e ->
          let (token_right, tail_token_right) = read_token tail_exp in
          if token_right = Some ")" then (exp, tail_token_right) else (None, str)
        | None -> (None, tail_exp)
      end;
    | Some "+" | Some "*" | Some "/" | Some ")" | None -> (None, str)  
    | Some "pi" -> (Some ConstPi, tail_token)
    | Some "e" -> (Some ConstE, tail_token)
    | Some "cos" | Some "sin" | Some "tan" ->
      let op =
        match token with
        | Some "cos" -> Cos
        | Some "sin" -> Sin
        | _ -> Tan
      in
      let (token_lpar, tail_lpar) = read_token tail_token in
      begin
        match token_lpar with
        | Some "(" ->
          let (exp, tail_exp) = parserE tail_lpar in
          begin
            match exp with
              | Some e ->
                let (token_rpar, tail_rpar) = read_token tail_exp in
                if token_rpar = Some ")" then (Some (UnOp (op, e)), tail_rpar)
                else (None, str)            
              | None -> (None, str)
          end
        | _ -> (None, str)
      end
    | Some number -> (Some (Number number), tail_token)
  in
  let (exp, tail) = parserE str in
  match exp with
  | Some e -> e
  | None ->
    let error_msg =
      Printf.sprintf "Remaining to process: %s" tail
    in
    raise (SyntaxError error_msg)

let rec eval exp =
  match exp with
  | Number str -> float_of_string str
  | ConstPi -> Float.pi
  | ConstE -> Float.exp 1.0
  | BinOp (e1, op, e2) ->
    begin 
      match op with
      | Plus -> eval e1 +. eval e2
      | Minus -> eval e1 -. eval e2
      | Times -> eval e1 *. eval e2
      | DividedBy -> eval e1 /. eval e2
    end
  | UnOp (op, e) ->
    begin 
      match op with
      | Neg -> -. (eval e)
      | Cos -> Float.cos (eval e)
      | Sin -> Float.sin (eval e)
      | Tan -> Float.tan (eval e)
    end

(*
let () =
  let calc = 
    if Array.length Sys.argv < 2 then
      "4+3.7*2.1"
    else
      Sys.argv.(1) in
  let exp = parser calc in
  let value = eval exp in
  Printf.printf "Result : %f\n" value
*)   

(* caml-prépa: what a user types at the prompt, scripted. This [read_line]
   shadows the standard one, echoes each line as a terminal would, and runs
   out the way standard input does. *)
let session = ref ["4+3.7*2.1"; "-2*(1+pi)"; "cos(0)+sin(pi/2)"; "e*e"; "3+"; "2 $ 3"; "quit"]

let read_line () =
  match !session with
  | [] -> raise End_of_file
  | line :: rest -> session := rest; print_endline line; line

let () =
  let rec loop () =
    Printf.printf "> ";
    let line = read_line () in
    if line = "quit" then
      ()
    else (
      (try
         let exp = parser line in
         let value = eval exp in
         Printf.printf "Result : %f\n" value
       with
       | LexicalError msg ->
         Printf.printf "Lexical error: %s\n" msg
       | SyntaxError msg ->
         Printf.printf "Syntax error: %s\n" msg);
      loop ()
    )
  in
  loop ()
