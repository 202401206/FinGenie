# Services - Backend team

Coordination between API, parsing, persistence, analysis and AI belongs here.
Keep calculation logic in `analysis/`; do not make calculation functions query storage.
No service layer is necessary for the health endpoint.

Private source helpers now live in `source_storage.py`, with internal models,
safe errors and an authenticated dependency. See [source upload integration](source-uploads.md)
for their interface, the required reservation migration and their limitations.
Atomic parsed-data saving now has a separate authenticated repository; see
[parsed persistence](../db/parsed-documents.md). See [upload orchestration and parser handoff](upload.md) for the tested service
and unmounted router factory. Activation awaits the real parser.
