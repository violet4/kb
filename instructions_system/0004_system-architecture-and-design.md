title: system-architecture-and-design
trigger: when designing or restructuring how components or services communicate or depend on each other

Uncontrolled coupling between components causes change amplification: a change to one component forces changes in others that should have been independent. Dependency direction matters and should be chosen deliberately, not left to accumulate from whichever module happened to need which other module first.

A late or deferred import guarded specifically to dodge a circular import is a code smell, not an acceptable pattern: it signals two modules each want to be depended on by the other, a real dependency-direction problem. Fix the actual shape — extract the shared foundation both sides need into its own module — rather than papering over the cycle.

When integrating a third-party dependency or subsystem, evaluate whether confining it to a single layer behind a thin, well-defined API would reduce complexity for the rest of the system. Layer boundaries should work like a network protocol stack: each layer needs to know only the interface of the layer directly above and below it, not that layer's internal implementation — this lets any one layer be swapped or reimplemented without the others noticing, provided the interface is held fixed.

When designing a system that resembles an already well-established category (scheduling, inventory, project tracking, and similar recurring problem shapes), examine how mature, widely-used systems in that category solve the same problem before inventing a novel structure. Most design problems worth solving have already been solved well by something; the value of prior art here is in the category-level shape of the solution, not in copying implementation detail wholesale.

The line between this hub and code-level implementation is the compiler/runtime unit boundary: a change resolvable by reasoning about one file or function in isolation is code-level; a change that requires reasoning about how two or more separately-deployable or separately-owned components depend on or communicate is architecture. API and interface design (a separate hub) is a stricter special case of this same boundary, specifically for contracts another party depends on.
