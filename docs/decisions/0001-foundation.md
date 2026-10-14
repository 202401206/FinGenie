# 0001: A small shared foundation

Status: scaffold choices adopted from the user request; new data conventions are
proposals pending affected-team review.

## Source hierarchy

The supplied seven-page brainstorming PDF is the primary requirements source.
Its internal action items are project requirements, not authorization to install,
deploy, create services, collect real files or implement features during this task.
The user's explicit foundation scope and later refinements control conflicts.

| Source | What it establishes |
| --- | --- |
| PDF pp. 1-2 | User/document eligibility; CSV/XLSX; one Python backend; Supabase; exclusions |
| PDF pp. 3-4 | Validation before/after parsing; bank/balance-sheet JSON; `unmapped`, `source_row`, `unit_scale`; balance check; three tables |
| PDF p. 5 | KPIs, roughly 3+ months for projections, deterministic tools, AI numeric rejection/retry and disclaimer |
| PDF pp. 5-7 | Sprints, PR review/testing, three tracks, later Ollama/Groq note |
| User refinements | JSX/plain CSS; exact directory ownership and endpoint plan; Ruff handles formatting as well as linting; no installs/services/commits; health-only implementation |

## Deliberate choices

- One modular backend keeps Python analysis and AI in the same process.
- Only runnable foundation modules exist. Directory READMEs name future files.
- No Black: Ruff formats Python. No Axios: the browser's `fetch` is sufficient.
- `pydantic-settings` loads optional local settings; no custom configuration layer.
- Pandas/OpenPyXL appear in the required stack manifest but are unused until parsing.
- Supabase SDKs, multipart handling, RapidFuzz, slowapi, LangChain/LangGraph,
  Ollama/Groq integrations wait until their work is started. No speculative adapters.
- Dependency ranges are compatible baselines, not exact locks or latest-version
  claims. The user generates and reviews resolution artifacts after installing.

## Proposed conventions, not original PDF requirements

Snake-case enum values; ISO dates; 1-based physical source rows; source locations
for scalar fields; sheet metadata; `null` for missing values; exact-decimal money
handling; pagination; endpoint status/error shapes; calculation identifiers and
analysis metadata are additions described in `contracts/`. No parser or financial
Pydantic models enforce these yet. New conventions need affected-team review.

## Still open

First bank formats, roles within teams, exact rate limits and upload size limit,
multi-sheet policy, rounding/tolerances, precise projection coverage rule, data
retention/deletion and final provider/model choices. The PDF excludes projections
from a single balance sheet despite listing balance-sheet projections in a later
drop-order note; keep them outside V1. No new infrastructure is needed now.
