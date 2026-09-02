title: security
trigger: when handling untrusted input, credentials, or anything crossing a trust boundary

Untrusted input must be validated or sanitized at the boundary where it enters trusted processing, not assumed safe because it happened to be well-formed on prior observation — command injection, SQL injection, and cross-site scripting are all instances of the same underlying failure: data from outside a trust boundary being interpreted as code or a control structure instead of as inert data.

A credential or secret must never be transmitted to a party it was not intended for, and must never be embedded in a location a party outside its intended scope can read — a request header, URL, log line, or committed file are all real transmission and storage channels that require the same scrutiny as an explicit "send this credential" action.

Security correctness has less legitimate stylistic variance than most other engineering concerns: a violation is objectively exploitable or it is not, independent of team or project style preference.
