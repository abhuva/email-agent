# IMAP KEYWORDS vs FLAGS: Technical Explanation

## Overview

IMAP servers support two mechanisms for tagging/labeling emails:
1. **FLAGS** - Standard IMAP flags (RFC 3501)
2. **KEYWORDS** - IMAP extension for custom keywords (RFC 3501 extension, not widely supported)

## FLAGS (Standard - Always Available)

**What they are:**
- Standard IMAP feature, supported by ALL IMAP servers
- System flags: `\Seen`, `\Flagged`, `\Deleted`, `\Draft`, `\Answered`
- Custom flags: Any flag name WITHOUT a leading backslash (e.g., `Urgent`, `Spam`, `[AI-Processed]`)

**Syntax:**
```python
# Add custom flags
imap.uid('STORE', uid, '+FLAGS', '(Urgent Spam [AI-Processed])')

# Search by flags
imap.uid('SEARCH', None, 'FLAGGED')  # System flag
imap.uid('SEARCH', None, 'KEYWORD Urgent')  # Custom flag (note: uses KEYWORD keyword!)
```

**Limitations:**
- Custom flags are case-sensitive
- Some servers limit flag names (no spaces, special chars)
- Flags are stored as-is (no validation)

**Search syntax:**
- `FLAGGED` - emails with \Flagged system flag
- `KEYWORD flag-name` - emails with custom flag (note: uses "KEYWORD" keyword in search, but it's searching FLAGS!)
- `NOT KEYWORD flag-name` - exclude emails with custom flag

## KEYWORDS (Extension - Rarely Supported)

**What they are:**
- IMAP extension (not part of base RFC 3501)
- Requires server to advertise `KEYWORDS` capability
- Designed specifically for custom user-defined keywords
- More structured than custom FLAGS

**Syntax:**
```python
# Check capability
status, caps = imap.capability()
if b'KEYWORDS' in caps:
    # Server supports KEYWORDS
    
# Add keywords (similar to flags)
imap.uid('STORE', uid, '+KEYWORDS', '(Urgent Spam)')

# Search by keywords
imap.uid('SEARCH', None, 'KEYWORD "Urgent"')
```

**Advantages:**
- Explicitly designed for custom tags
- Better semantic meaning
- Some servers provide better indexing

**Disadvantages:**
- **Not widely supported** (Gmail, many corporate servers don't support it)
- Requires capability check
- More complex implementation

## The Confusing Part

**IMAP Search Syntax:**
- `KEYWORD flag-name` in SEARCH actually searches **FLAGS**, not KEYWORDS!
- This is confusing naming in the IMAP spec
- To search KEYWORDS extension, you'd use the same syntax but server must support KEYWORDS capability

**Our Current Code:**
- We use `KEYWORD "tag"` in SEARCH (which searches FLAGS)
- We use `+FLAGS` in STORE (which stores as FLAGS)
- We check for KEYWORDS capability (which is unnecessary if we're using FLAGS!)

## Solution: Use FLAGS Instead of KEYWORDS

Since your server doesn't support KEYWORDS extension, we should:

1. **Remove KEYWORDS capability check** - Not needed for FLAGS
2. **Keep using FLAGS in STORE** - Already correct: `+FLAGS (tag1 tag2)`
3. **Keep using KEYWORD in SEARCH** - This searches FLAGS anyway (confusing name!)
4. **Rename for clarity** - Use "flags" terminology instead of "keywords" in code

## Testing FLAGS Approach

We need to verify:
1. Can we add custom flags? (`+FLAGS (Urgent)`)
2. Can we search by custom flags? (`KEYWORD Urgent`)
3. Can we exclude by custom flags? (`NOT KEYWORD "[AI-Processed]"`)
4. Do flags persist after reconnection?
5. Are flags visible in email clients?

## Migration Plan

1. **Test FLAGS support** (create test script)
2. **Remove KEYWORDS capability check** from `safe_imap_operation`
3. **Update search function** to use FLAGS syntax (already correct, just rename)
4. **Update documentation** to use "flags" terminology
5. **Update error messages** to reflect FLAGS usage
6. **Test with real server** to verify everything works
