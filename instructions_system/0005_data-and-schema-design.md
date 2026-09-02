title: data-and-schema-design
trigger: when defining or changing how data is modeled, stored, or migrated

A schema constraint should encode a real invariant of the domain, not merely describe today's data shape — a constraint that cannot fail given valid input is not doing useful work, and a constraint that can fail on valid input is wrong.

Default a new field or column to NOT NULL with an explicit default rather than nullable. Nullability is a deliberate choice for a real third state the domain actually has, not a reflexive default; before making a field nullable, ask whether "no value" means something the type's own default value does not already mean.

A schema migration must be safe and reversible under real operating conditions, not merely correct against an idealized empty database: a migration that locks a large table, drops data irrecoverably, or cannot be rolled back is a design defect even when the resulting schema is otherwise correct. A structural change (renaming a column, renaming a table, changing a constraint) and a data change (backfilling, transforming existing values) are different kinds of migration with different risk profiles and should be verified accordingly — a structural change that silently fails to apply a related constraint (e.g., a foreign key dropped in the same step as a column rename) is a known failure mode worth an explicit verification step, not just an assumption that "the migration ran without error" is sufficient.
