# Merge Overlaps - Converted Output Feature

## Overview

The **Merge Overlaps V2** task now includes an automatic **Converted Output** section that converts LLM responses (line number format) back to the original timestamp format in real-time during streaming.

## How It Works

### 1. Context Preparation (Sending to LLM)

When processing overlap regions, the system:
- Formats context with line numbers, source labels (A/B), and retimed timestamps
- Builds a **line number mapping**: `line_num → (original_start, original_end, word)`
- Sends formatted context to LLM

Example formatted context sent to LLM:
```
Line Source start(s) end(s)
1 A 9.12 ~ " "
2 A 10.70 ~ 例えば
3 B 10.70 11.22 例えば
4 A 11.22 ~ 極
```

### 2. LLM Response (Line Numbers Only)

The LLM responds with selected line numbers (no timestamps):
```
Time offset: -580s
1 " "
2 例えば
4 極
```

### 3. Real-Time Conversion (During Streaming)

As the LLM response streams in:
- Each chunk is incrementally converted using the line number mapping
- Line numbers are replaced with original timestamps
- Output appears in the **Converted Output** section below the raw response

Converted output:
```
Time offset: -580s
589.12 590.70 " "
590.70 591.22 例えば
591.22 591.74 極
```

## UI Behavior

### When Does It Appear?

- The **Converted Output** section is **hidden by default**
- It appears automatically when:
  1. A line number mapping is set (only for merge overlaps task)
  2. The first response chunk arrives (streaming begins)

### Does It Affect Other Task Cards?

**No.** The conversion feature is:
- Optional (requires `set_line_mapping()` to be called)
- Only enabled for **Merge Overlaps V2** task
- Other tasks (Cutpoint, Assemble) don't call `set_line_mapping()`, so they won't see the extra section

## Implementation Details

### Key Components

1. **`response_converter.py`**: Core conversion logic
   - `parse_context_to_line_mapping()`: Builds line_num → timestamp mapping
   - `convert_response_incremental_multiregion()`: Converts chunks during streaming (supports multiple regions)
   - Handles `~` symbol resolution (continuous speech marker)
   - **Multi-region support**: Uses `{offset: {line_num: (start, end, word)}}` structure to handle multiple regions with same line numbers

2. **`TaskPopupWindow`**: UI updates
   - Added `converted_display` QTextBrowser (initially hidden)
   - Modified `_on_chunk()` to convert and display incrementally
   - Added `set_line_mapping()` method to enable conversion
   - Tracks `_current_offset` to handle region switches during streaming

3. **`sentence_builder_tab.py`**: Integration
   - Calls `parse_context_to_line_mapping()` for each overlap context
   - Groups mappings by Time offset (extracted from context header)
   - Passes offset-grouped mappings to popup windows via `set_line_mapping()`

### Tilde (`~`) Symbol Handling

When the formatted context contains `~` (indicating continuous speech where `end_time == next_start_time`):
- The parser stores `None` as the end time
- Resolution happens by finding the next entry chronologically
- Original timestamps are restored correctly in the converted output

### Multi-Region Support (Fixed Issue)

When a single prompt contains **multiple overlap regions** with different Time offsets:
- Each region has line numbers starting from 1
- Line mappings are grouped by offset: `{offset: {line_num: (start, end, word)}}`
- During conversion, the current offset is tracked to select the correct mapping
- This prevents later regions from overwriting earlier regions' line number mappings

**Example:**
- Region 1: Line 1-147, offset -580s → timestamps 589.xx
- Region 2: Line 1-140, offset -1190s → timestamps 1190.xx
- Both regions can have "Line 1" without conflict

## Benefits

1. **Immediate Feedback**: See timestamp-restored output in real-time
2. **Verification**: Easily verify LLM selections against original data
3. **Copy-Paste Ready**: Converted output can be directly used downstream
4. **Non-Intrusive**: Only appears when needed, doesn't affect other tasks

## Example Workflow

1. User starts Merge Overlaps V2 task
2. System detects overlap regions and formats context
3. LLM receives formatted context with line numbers
4. User sees two output sections:
   - **LLM Response**: Raw line number format
   - **Converted Output**: Timestamp format (auto-converted)
5. User can copy either format as needed
