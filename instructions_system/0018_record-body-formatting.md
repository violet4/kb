title: record-body-formatting
trigger: when writing or editing any free-text body/description/notes field on a kb entity (Note/Todo/Goal/Journal) longer than a couple of sentences

Structure a long-form body with markdown headings and lists, not as one dense prose block. A stored body is read cold, later, out of the conversational context that produced it -- skimmability at read time matters more than compactness at write time. Use `##` headings to separate distinct sub-questions or facets (overview, mechanism, why-it-matters, cross-references), and bullet lists for anything that is really an enumeration (a set of features, reasons, or steps) rather than a continuous argument.

Reserve an unbroken paragraph for a body that is genuinely one idea end to end and does not exceed a few sentences -- a short Note or a Todo's description does not need headings it has no content to fill. The test is structural, not length alone: if the body covers more than one facet of the topic, or contains a list dressed up as prose ("X, Y, and also Z, which in turn..."), split it into headed sections/bullets even if the total length would otherwise look short enough to leave as one paragraph.

This governs the internal shape of a record's own body text -- distinct from root's Tone section, which governs conversational replies to the user, a different audience read in a different context.
