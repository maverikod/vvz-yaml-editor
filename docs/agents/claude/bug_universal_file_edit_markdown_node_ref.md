# BUG: universal_file_edit does not accept node_ref for markdown files

2026-05-23 Claude (session: paginated-search-results source

## Summary

universal_file_edit always rejects node_ref values for .md f

## Reproduction

- list_item: 
- list_item: 
- list_item: 
- list_item: 

## Observed behaviour

- list_item: 
- list_item: 
- list_item: 
- list_item: 

## Expected behaviour

node_ref values returned by universal_file_preview with sess

> operation_shapes.text_md_txt.note: node_ref is preferred ove

## Hypothesis

format_group="text" causes the edit handler to use a plain-t

## Impact

- list_item: 
- list_item: 
- list_item: 

## Workaround (requires user approval)

Use start_line/end_line in universal_file_edit after obtaini

## Suggested fix

Wire the markdown tree node registry into the edit handlers

Return format_group="markdown" for .md files and implementa
