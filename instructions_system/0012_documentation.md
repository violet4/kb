title: documentation
trigger: when a decision, interface, or non-obvious behavior needs to be discoverable by someone other than the author

Document the reasoning behind a decision — why this approach and not an obvious alternative — not a restatement of what the code already says through its own structure and naming. A comment or doc that only re-describes what a reader could see directly from the code adds a maintenance burden without adding information; a comment that captures a non-obvious constraint, a rejected alternative and why, or a workaround for a specific external limitation earns its place because the reader cannot recover that information from the code alone.
