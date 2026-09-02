title: dependency-management
trigger: when adding, upgrading, or removing an external dependency

Vet a dependency before adding it: its maintenance activity, its own dependency surface, and its license are all part of the actual cost of adding it, not just the functionality it provides. Remove a dependency once nothing in the codebase uses it — an unused dependency still carries its full security and maintenance surface with none of its benefit. Pin dependency versions for reproducibility, so a build or environment does not silently change behavior between two nominally identical runs.
