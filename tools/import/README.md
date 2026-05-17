# Import Tools

Fixed import tools convert external resources into the Markdown-only internal
workspace boundary. They keep originals, write converted Markdown when
conversion succeeds, and always write a conversion report.

Supported MVP inputs:

- `.md` and `.markdown`
- `.txt`
- `.html` and `.htm`
- `.docx`
- digital-text `.pdf`

Unsupported or failed conversions keep the original and produce a failed report
with no usable `markdown_path`.

```powershell
python tools/import/convert_to_markdown.py --source path/to/input.md --output-root path/to/workspace/inputs
python tools/import/convert_to_markdown.py --source path/to/input.docx --output-root path/to/workspace/inputs
python tools/import/convert_to_markdown.py --source path/to/input.pdf --output-root path/to/workspace/inputs
python tools/import/inspect_conversion.py --report path/to/workspace/inputs/reports/input.conversion.json
```

