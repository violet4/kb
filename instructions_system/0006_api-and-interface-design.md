title: api-and-interface-design
trigger: when defining a contract another caller, internal or external, will depend on

A published contract — a public API, an inter-service interface, a library's public surface — should not break silently. A breaking change to a contract another party depends on requires either a deliberate versioning strategy or explicit, coordinated migration of every caller; it is never an incidental side effect of an unrelated change.

Error semantics must be explicit and part of the contract, not an implementation detail a caller discovers by trial and error: what happens on invalid input, what happens when a resource does not exist, and what happens on partial failure should be specified as clearly as the success path.

A CLI is a form of interface with the same obligation: it must be ergonomic and intuitive to someone who has never used it before, not merely to someone with muscle memory built up from repeated use. When a command's behavior diverges from the established shape its sibling commands would predict — for example, one subcommand requiring a flag where every sibling accepts a bare positional argument — fix the interface to match the established convention rather than only documenting the exception; a documented exception still costs every first-time caller the same surprise, and only gives them somewhere to look afterward.
