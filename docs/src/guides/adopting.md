# Adopting astero

The [tutorial](../tutorial.md) builds a compiler from scratch. This guide is the other case: you have a working compiler and you want to introduce astero into it without a rewrite.

The order below has been used to introduce astero into three existing compilers: Python to JavaScript, Python to WebAssembly, and typed Python to native. The pitfalls section lists the mistakes those three made, so you can avoid them.

## Step 1: run a derivation next to the table you already have

Before changing any behaviour, declare your grammar, derive the table your compiler currently writes by hand, and assert the two agree:

```python
def test_my_operand_table_matches_the_grammar():
    assert derived_from(MY_GRAMMAR) == MY_HAND_WRITTEN_TABLE
```

This is cheap and it cannot break anything, because nothing calls the derivation yet.

If they agree, you can now delete the hand-written table and keep the test, which will fail if the deletion was wrong. If they disagree, the assertion names the production. Check both sides: either a role in your declaration is wrong, or the hand-written table is missing a case. Every disagreement found this way so far has been the second.

## Step 2: adopt in this order

1. **`coverage`.** It is a test, it changes no behaviour, it finds handlers you never wrote. Start here.
2. **`grammar` queries.** Replace one hand-written table with a derivation, using the shadow test above.
3. **`rewriting`**, wherever you have `NodeTransformer` passes.
4. **`hygiene`**, if you inline, substitute or rename.
5. **`emit_rules`** last, one production at a time. Pass `fallback=` your existing generator; anything without a rule keeps working as before.

## Step 3: declare your grammar

If your AST subclasses or mirrors Python's, one line does it:

```python
MY_LANG = astero.python.build(module=my_ast_module, name="mylang")
```

Roles come from astero's declaration of Python, and only the productions your module actually defines appear.

If your IR is annotated dataclasses, `grammar.from_dataclasses` reads the names, sorts and shapes off the annotations, so you author only the roles.

Then call `MY_LANG.check()`, which returns a list of problems in the declaration and `[]` if it is sound.

## Pitfalls

These four mistakes are easy to make and hard to spot afterwards.

**Ask the scope first.** Two compilers looked a name up in a table of builtins *before* asking whether anything in the program bound it. In one, all 42 of its runtime-symbol names became unusable as variables: `map = 3; return map + 1` emitted the source text of a helper function. Python's rule is that any binding beats a builtin, so a table consulted first inverts it. If you have such a table, ask the scope first and the table second.

**A binding occurrence is not a use.** An inliner replaced every `Name` matching a parameter, so inlining `f(99)` into a body containing `[x for x in ...]` produced `[99 for 99 in ...]`, which does not parse. Only roles distinguish the two positions; `hygiene.substitute` uses them.

**Inserted code brings free names.** The same inliner, once that was fixed, still turned a call `g(k)` with body `[n + k for k in ...]` into `[k + k for k in ...]`: the *argument's* free `k` was captured by a binder inside the body. Guarding against the body rebinding a *parameter* does not catch this, because the collision is with a name the caller supplied. `hygiene.substitute(..., fresh=Fresh())` renames the capturing binder.

**Never re-parse your output.** A statement emitter built `elif` chains by emitting the nested `if` to a string and editing it: strip a leading `"if ("`, strip a trailing `"}"`, splice the pieces. It produced JavaScript that stopped parsing as soon as the inner test needed a declaration hoisted in front of it. If you are calling `startswith` on generated code, the information you want is still in the node.

## Two ways this kind of code fails

**Drift.** Two enumerations of the same thing, one of them stale. It is the loud failure: something eventually disagrees with something.

**Answering the wrong question.** Quieter, because nothing disagrees with anything: the table is correctly derived, it just answers a question next to the one you meant. Two examples from astero itself: `ident_slots()` reports every identifier while `ident_slots(ns)` reports variables, so a renamer built on the first rewrites `x.foo`. `SCOPES` reports what `symtable` calls a block while `BINDING_SCOPES` reports what a name binds over, and after PEP 709 those differ.

When two questions are close enough to confuse, make the grammar answer both and give them different names.

## What will not convert

The [tutorial](../tutorial.md#limits-what-you-write-yourself) gives the same list for someone building from scratch.

- **Lowering.** Turning a comprehension into a loop produces a variable number of statements, so no template describes it. Moving one into a rewrite pass cost lines, and lowering onto closures cost about 11% of the generated code's speed.
- **Statement layout.** Emitting documents in place of strings removes the plumbing and makes one class of bug impossible, but it is worth about 2% of a back end. Do it for the correctness. Size is not the point.
- **Name resolution.** Resolving against an FFI or a module system is your compiler's policy. A guard meaning "ask this other subsystem" is where the guard vocabulary stops being closed.
- **A cost model.** "Is this operand provably small?", "can this overflow?" decide a representation. No closed guard vocabulary reaches it.

**Statement control flow does convert.** A `{&label}` hole names a label unique to a node, so `while` and `if` are templates on a flat target as much as on a braced one. See [the tutorial](../tutorial.md#6-back-end-one-statements-labels-and-jumps).

## What to expect

Across the three compilers, roughly nine defects were found by a derivation disagreeing with a hand-written table. Rather more were found by differential testing against the source language, which needs no library at all.

So the claim is narrower than "it finds bugs". **Most such defects become unwritable.** You cannot write the wrong `ctx` against a grammar that derives `ctx`. You cannot omit a binding position from a table you did not write.

If your goal is fewer bugs this quarter, write a differential test harness first: run your compiler's output and the source language's own interpreter on the same programs and compare. Adopt astero when you want a class of bug to stop being possible at all.
