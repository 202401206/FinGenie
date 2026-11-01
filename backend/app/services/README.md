# Services - Backend team

Coordination between API, parsing, persistence, analysis and AI belongs here.
Keep calculation logic in `analysis/`; do not make calculation functions query storage.
No service layer is necessary for the health endpoint.

Private source helpers now live in `source_storage.py`, with internal models,
safe errors and an authenticated dependency. See [source upload integration](source-uploads.md)
for their interface, the required reservation migration and their limitations.
The complete upload orchestration and atomic parsed-data save are still upcoming work.
