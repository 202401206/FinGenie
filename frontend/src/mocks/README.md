# Offline fixtures - Frontend team

The title page runs without any backend. For future feature work, copy the needed
synthetic JSON from `contracts/examples/` into this directory, then import it from
your feature (for example `import analysis from "../../mocks/financial-analysis.json"`
from a file directly inside `src/features/dashboard/`). Use local fixture data in
place of `apiRequest` while developing; no mock server or mocking package is needed.

Copy endpoint envelopes from `contracts/api/README.md` when needed. Keep local copies
aligned with the source contract in the same PR; do not add real financial documents.
No automatic mock mode or feature UI is implemented in this scaffold.
