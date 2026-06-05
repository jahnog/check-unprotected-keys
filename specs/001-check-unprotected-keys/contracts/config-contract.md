# Configuration Contract: Check Unprotected Keys

## File Location

`.find-unencrypted-keys.toml` in the execution root.

## Schema

```toml
[scan]
folder_patterns = [
  ".ssh",
  "config/**",
  "secrets/**"
]

filename_patterns = [
  "id_*",
  "*.ppk",
  ".env",
  ".env.*",
  "*_private.pem",
  "*_private.key"
]
```

## Field Rules

### `scan.folder_patterns`

- Required.
- Array of non-empty strings.
- Entries may be relative to the execution root or absolute filesystem paths.
- Entries define where the scanner may look for candidate files.

### `scan.filename_patterns`

- Required.
- Array of non-empty glob strings.
- Entries are applied unchanged whether or not `--start-folder` is provided.
- Entries define which filenames are eligible once a folder match has been
  reached.

## Validation Rules

- The configuration file MUST parse as TOML.
- Both arrays MUST contain at least one entry.
- Blank strings are invalid.
- Duplicate patterns are allowed but are collapsed during effective-scope
  resolution through canonical-path deduplication.

## Semantics

- The effective scope is the intersection of configured folder matches and
  configured filename matches.
- A start-folder override narrows only the reachable folder matches beneath the
  supplied path.
- Filename matching remains exactly the same after start-folder narrowing.