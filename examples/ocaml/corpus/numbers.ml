(* Integers and floats, the bitwise operators, and a downward loop. *)

let square x = x * x

let hypot a b = sqrt ((a *. a) +. (b *. b))

let is_even n = n mod 2 = 0

let double n = n lsl 1

let halve n = n asr 1

let mask n = n land 255

let flags a b = (a lor b) lxor 3

let power b e =
  let r = ref 1 in
  for _i = 1 to e do
    r := !r * b
  done;
  !r

let countdown n =
  for i = n downto 1 do
    print_int i;
    print_char ' '
  done

let float_bits = 2.0 ** 10.0

let compare_all a b = (a < b, a <= b, a > b, a >= b, a = b, a <> b)

(* An annotation on an expression, where the argument alone is ambiguous. *)
let widen n = (n : int) + 0

let () =
  countdown 3;
  print_newline ();
  print_int (power 2 8);
  print_newline ();
  print_float (hypot 3.0 4.0);
  print_newline ();
  print_float float_bits

(* A bare expression as a structure item. `;;` is what ends the one
   before it: without it juxtaposition would read this as its argument. *)
;;
print_newline ()
