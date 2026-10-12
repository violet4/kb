title: type-safety
trigger: when writing typed code, choosing a language, or responding to a type checker error

Type all code strictly and explicitly, and run a static type checker (mypy or pyright for Python, `tsc --strict` for TypeScript) on every commit, from a project's first line rather than retrofitted later. Static type systems catch a measurable share of real defects before they ship: TypeScript and Flow each detect about 15% of the public bugs sampled from JavaScript projects (AB636). Choose a language that supports strict static typing.

Memory safety is the same tier of concern: choose a memory-safe language -- Rust where its overhead is justified, otherwise a strictly typed garbage-collected language. About 70% of the serious security vulnerabilities in large C/C++ codebases are memory-safety defects (AB633, AB634), and government security agencies recommend memory-safe languages on that basis (AB635).

When a type checker flags code that manual tracing judges safe, supply verifiable evidence -- a narrower type, an `isinstance` guard, a `TypeGuard`, a runtime assert -- instead of silencing the error. The checker's objection marks a gap in what the code proves.

An unchecked type assertion (`cast()` in Python, `as` in TypeScript, a type-ignore comment) is a last resort: it makes a claim with no runtime check, so a wrong assertion propagates a bad type to every downstream caller instead of failing where the mistake is. When the runtime type is narrower than the static type -- for example, objects returned by a shared base-class method, only some of which carry a mixin's fields -- narrow each value with `isinstance()` where it is used. That check holds per object at runtime; a cast asserts the narrower type for all of them at once.
