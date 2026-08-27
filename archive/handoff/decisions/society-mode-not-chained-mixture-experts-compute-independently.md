# Society mode (SOCIETY=1), not chained mixture — experts compute independently — SETTLED [USER framing + fix]

**Decision:** every expert maps the SAME shared base hidden state to its own output, with no chaining between experts;
the router blends outputs once at the end. The chained-mixture fabric (`SOCIETY=0`, legacy port) is rejected.
**Why:** in mixture mode each step's blended hidden state fed the next step, so every expert's gradient flowed through
every other — entangling the population, degrading the base model's stand-alone quality the more the fabric absorbed,
and helping break generation. Independence is also what bounds how much is forgotten when an expert is removed.
**Source:** context export Phase 6 + §6 vocabulary; `../GLOSSARY.md`.
