# Export Tools

Fixed export tools convert internal Markdown drafts into external artifacts.

```powershell
python tools/export/export_docx.py --source path/to/workspace/draft/draft.md --output path/to/workspace/artifacts/draft.docx
python tools/export/export_pdf.py --source path/to/workspace/draft/draft.md --output path/to/workspace/artifacts/draft.pdf
```

These tools are boundary converters. They do not make DOCX or PDF editable
workspace formats.
