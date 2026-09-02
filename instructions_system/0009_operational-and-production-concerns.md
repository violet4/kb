title: operational-and-production-concerns
trigger: when a change affects what happens after deploy: observability, failure behavior, or rollout

A change that affects production behavior needs some path to observe whether it is working as intended after deployment, and some path to reverse it if it is not — a change with neither is a change made blind, regardless of how carefully it was reviewed before deploy.

Provide clear, unambiguous feedback about what an operation actually did, whether the surface is a CLI, a UI, or an API response — the caller should never have to guess whether an action succeeded, partially succeeded, or had no effect.
