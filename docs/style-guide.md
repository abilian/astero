# Writing style

For the prose in `docs/src/`, in `README.md`, and in the examples' own documentation. It covers one failure that shows up in every draft here, in six shapes, and the way facts in prose go stale.

Guidance for the code is in [the developer guide](src/guides/developer-guide.md). This file is not published: `docs_dir` is `src/`.

## The test

**Delete the sentence and read on.** If the point still lands, the sentence was scaffolding and can go.

It almost always lands, because the sentence that carries the point sits right after the one that promised it. A promise is not information. A heading has usually made the same promise already.

## Six sentences that fail the test

Each of these was in this repository and has been removed. What replaced it is struck through below, and in most of them nothing replaced it.

### 1. Announcing what the next sentence says

> ~~The obligation on them is stated as equality rather than as a threshold.~~ Every concrete production of the grammar is reached by one of them, and `test_the_corpus_reaches_every_production` fails otherwise.

The second sentence states the obligation. The first only says one is coming. Same shape: *the contrast is the point, so it is worth taking them in that order*; *the routing is the part to read*.

### 2. Restating the sentence before

> …so a production nothing writes does not belong in the subset. ~~That test is also the argument for where the subset stops.~~

Reaching for a second phrasing usually means the first one worked.

### 3. Negating a reading nobody would have had

> ~~This is not tidiness.~~ In OCaml a record label `x` and a variable `x` are unrelated, so a pass renaming the variable must not touch `r.x`.

No reader was going to take the namespace argument for tidiness. Where a contrast is real, keep it; the test is whether someone given the positive claim alone would land on the negated reading.

### 4. Grading your own material

> ~~Two details are worth the reading.~~ **A function value is a Python callable of one argument**, because…

A reader told a passage is worth reading either reads it because the passage earned that, or does not because it did not. "Worth defending", "worth knowing", "the part to read" and "the honest edge of the idea" are the same certificate. Cut it and let the claim stand.

Where the sentence is carrying a count, keep the count and drop the grade: *some of those are choices worth defending* becomes *two of those are decisions*.

### 5. A judgement with nothing to check

> All three are rejections rather than silent errors~~, which is the cheapest failure for a corpus to catch and the one that matters least~~.

The tail cannot be verified, and it talked the finding down on its way past. State what happened and let the reader weigh it.

### 6. "Whole" and "entire" as emphasis

> ~~That is the whole declaration:~~ **The declaration is** sixteen roles and five scope layers.

Also *the entire Names view*, *the entire toolchain*, *the whole difficulty of printing*. The word adds emphasis and no information. Delete it, and if the sentence needed the emphasis, the sentence was making a weak claim.

## Assert the consequence, not the importance

The repair for most of the above is the same move:

> ~~Both back ends use this file. That is the decision the whole back end rests on:~~ **Both back ends use this file, which is what made the second one cheap:** it cost an emitter and nothing else.

"The decision the whole back end rests on" claims that something matters. "Which is what made the second one cheap" says what it did. The second is checkable and shorter.

## What earns its place

Not every orienting sentence is scaffolding. These stay:

- **A page thesis**, when the page then argues it. *"This compiler does both, and the arrangement is the point"* opens a page whose last section is the evidence.
- **A signpost carrying a count and a distinction.** *"Three things it decides that the interpreter never has to"* tells you how many and what separates them from the paragraph above.
- **A transition into a heading**, kept to one clause.
- **A negation that a reader would otherwise get wrong.** *"`(* a (* b *) c *)` is one comment"* needs its second half, because the first `*)` is exactly where a reader expects it to end.

The difference is whether the sentence carries something the next one does not.

## Facts in prose go stale

Everything above is about sentences that never had content. The other failure is a sentence whose content was true once.

Recently, in this repository: "eighteen programmes" after the corpus reached forty-one, "seven divergences" after it reached eleven, "239 tests" after 410, "129 KB" after 166, and a code sample printing `{q, t}` beside a transcript printing `{rest, t}` because the sample had been renamed and the prose had not.

The repository's rule for tables applies to prose: **nothing derived is ever authored**. In descending order of preference:

1. **Generate it.** The reference card's operator, keyword and standard-library tables are read off the compiler at build time. Nobody can forget to update them.
2. **Gate it with a test.** Code blocks tagged with a `title=` are asserted verbatim against the file they name, and console transcripts are asserted to be what the command prints. A sample that drifts fails the build.
3. **Write it and expect it to rot.** A count in a sentence is this, and it is why counts belong in prose only when they carry the argument. *"About 3,500 lines"* survives a change that *"3,487 lines"* does not.

When a number does earn a place in prose, grep for it before claiming the change is finished. `eighteen` was in ten files, across two languages and three spellings.

## Checking it

Nothing in this repository lints prose. The structural failures above need a reader; the lexical ones (`worth …`, `the whole …`, `it is worth noting that`) are a grep away, and a pass over a page you have just written catches most of them, because the shapes cluster in fresh drafts.

The drift is enforced. `test_the_tutorial_quotes_the_source_exactly` and `test_the_tutorial_transcripts_are_what_it_prints` run over every documentation root, and the reference cards are built rather than written.
