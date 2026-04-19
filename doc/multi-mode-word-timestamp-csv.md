# Multi-Mode Word Timestamp CSV Parsing

This project uses a word-timestamp text format that is historically called
"CSV", even though the file is actually space-delimited with a free-form third
field.

## Canonical Format

The current canonical producer is `src/asr_postprocess/exporters.py`.

Each line contains:

```text
<start_seconds> <end_seconds> <payload>
```

Examples:

```text
74.00 75.00 あ
75.00 75.18 " "
88.30 88.92 New York
```

Rules:

- Normal words are unquoted.
- Whitespace-only payloads stay quoted so they remain visible.
- The payload is allowed to contain spaces.

## Legacy-Compatible Input Modes

Parsers must accept all of the following:

1. Canonical unquoted payload

```text
74.00 75.00 あ
88.30 88.92 New York
```

2. Whitespace-only payload

```text
75.00 75.18 " "
```

3. Legacy fully-quoted payload

```text
74.00 75.00 "あ"
88.30 88.92 "New York"
```

## Parsing Algorithm

Consumers should parse lines in this order:

1. Parse the first two numeric fields as `start` and `end`.
2. Treat the remainder of the line as the raw payload.
3. If the payload is fully wrapped in double quotes, unwrap one outer layer.
4. If quoted payload contains doubled quotes, unescape `""` to `"`.
5. Otherwise keep the payload as-is.

This design keeps the parser compatible with both the current export format and
older quoted files, while preserving unquoted multi-word payloads.

## Normalized Output Convention

When a tool writes or rewrites `merged_word_timestamps.csv`-style content, it
should prefer the canonical form:

- Normal payloads: unquoted
- Whitespace-only payloads: quoted

Examples:

```text
74.00 75.00 あ
75.00 75.18 " "
88.30 88.92 New York
```

## Code Paths

Current parser/formatter code paths related to this convention:

- `src/scripts/rangetime.py`
- `src/scripts/sentence_rebuilder.py`
- `src/sentence_builder/context_formatter.py`
- `src/sentence_builder/reverse_dedup.py`
- `src/gui/sentence_builder_tab.py`
- `src/asr_postprocess/exporters.py`

## Why This Exists

The project originally had multiple assumptions about whether the third field
must always be quoted. That caused two classes of bugs:

- Some consumers failed on canonical unquoted normal words.
- Some prompt builders re-added quotes even though the source format no longer
  required them.

The multi-mode parser avoids breaking old files, while the normalized output
rule keeps newly produced data consistent.
