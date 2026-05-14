# Timeline Package

Builds semantic DocAgent projections from ACP events and workspace activity.

ACP events are now the canonical interaction log for the center timeline.
Semantic timeline events are retained for DocAgent cards, workspace
invalidation, reporting, and derived read endpoints.

Examples:

- file read in `examples/` -> analyze examples
- write `style_notes.md` -> extract style notes
- run `checkpoint.py` -> create draft version
- run `export_docx.py` -> export DOCX

## Projection Helpers

`docagent_timeline.map_raw_event(...)` converts simple runtime signals into `SemanticTimelineEvent` objects.

The mapper is path- and command-based and exists to build product projections.
New runtime integrations emit ACP updates first and attach projection metadata
when a DocAgent card or invalidation needs it. Runtime-specific payload handling
belongs in the runtime adapter or ACP shim, not in this package as an event
protocol.

