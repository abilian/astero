(* Records: mutable fields, functional update, type aliases, annotations. *)

type point = { x : float; y : float }

type 'a cell = { mutable value : 'a; mutable hits : int }

type position = point

type transform = point -> point

let origin : position = { x = 0.0; y = 0.0 }

let translate (dx : float) (dy : float) : transform =
  fun p -> { p with x = p.x +. dx; y = p.y +. dy }

let norm2 p = (p.x *. p.x) +. (p.y *. p.y)

let touch c =
  c.hits <- c.hits + 1;
  c.value

let store c v =
  c.value <- v;
  c.hits <- 0

let describe { x = a; y = b } = (a, b)

let is_origin p =
  match p with
  | { x = 0.0; y = 0.0 } -> true
  | _ -> false

let () =
  let c = { value = 3; hits = 0 } in
  store c 4;
  print_int (touch c);
  print_newline ();
  print_float (norm2 (translate 1.0 2.0 origin))
