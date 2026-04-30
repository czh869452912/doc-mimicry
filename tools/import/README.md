# Import Tools

Planned scripts:

- `convert_to_markdown.py`: convert DOCX/PDF/PPTX/images/HTML/text resources into Markdown plus assets and conversion reports.
- `inspect_conversion.py`: summarize warnings and detected document features.

The import path should keep originals, converted Markdown, assets, and reports.

## Phase 0 Support

The first converter only normalizes `.md`, `.markdown`, and `.txt` files. Unsupported files produce a failed conversion report instead of silently pretending conversion worked.

```powershell
python tools/import/convert_to_markdown.py --source path/to/input.md --output-root path/to/workspace/inputs
python tools/import/inspect_conversion.py --report path/to/workspace/inputs/reports/input.conversion.json
```

