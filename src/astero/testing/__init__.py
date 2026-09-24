"""Fixtures a declared grammar generates for its own tests.

`generate` emits one program per declared binding position and reports which
positions no snippet reaches, which turns "every role is tested" from a claim
into a check.

The machinery is language-agnostic: `missing_coverage(grammar, scopes, ns)`
subtracts what a corpus exercises from what a grammar declares, and any
grammar answers. The corpus is not — `SNIPPETS` is Python source, because
Python is the language that ships with the library. A second language's corpus
would split `generate` in two along that line; one has not existed yet, and
inventing the seam before it does would be the speculation this library
otherwise argues against.
"""

from __future__ import annotations

from astero.testing.generate import combinations, missing_coverage, snippets

__all__ = ["combinations", "missing_coverage", "snippets"]
