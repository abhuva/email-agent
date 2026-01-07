# Task 16: Configurable IMAP Query Filtering System - Proposed Solution

## Current State Analysis

### Hardcoded Tags
Currently, three idempotency tags are hardcoded in `src/imap_connection.py`:

1. **`AIProcessed`** - V1 tag for emails processed by AI classification
2. **`ObsidianNoteCreated`** - V2 tag for emails with successfully created notes
3. **`NoteCreationFailed`** - V2 tag for emails where note creation failed

### Current Implementation
```python
# In search_emails_excluding_processed()
final_query = (
    f'({user_query} '
    f'NOT KEYWORD "{processed_tag}" '
    f'NOT KEYWORD "{obsidian_note_created_tag}" '
    f'NOT KEYWORD "{note_creation_failed_tag}")'
)
```

### Issues with Current Approach
1. Tags are hardcoded as function parameters with defaults
2. No way for users to customize which tags to exclude
3. No way to add additional exclusion tags
4. Query building logic is inflexible
5. Cannot disable idempotency checks (though this might be intentional)

## Proposed Solution

### 1. Configuration Schema

Add new optional configuration section to `config.yaml`:

```yaml
# IMAP Query Configuration
imap_query_exclusions:
  # Tags to exclude from IMAP queries (for idempotency)
  # Default: ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']
  exclude_tags:
    - 'AIProcessed'                    # V1: Emails processed by AI
    - 'ObsidianNoteCreated'            # V2: Notes successfully created
    - 'NoteCreationFailed'             # V2: Note creation failed
  
  # Optional: Additional tags to exclude (beyond idempotency)
  # Example: ['Archived', 'ProcessedByOtherTool']
  additional_exclude_tags: []
  
  # Optional: Disable idempotency checks (NOT RECOMMENDED)
  # If true, only user_query is used (no exclusions)
  # Default: false
  disable_idempotency: false
```

### 2. Implementation Approach

#### Option A: Simple Configuration-Based (Recommended)
- Add `exclude_tags` list to config
- Default to current three tags if not specified
- Build query dynamically from config
- **Pros:** Simple, backward compatible, easy to understand
- **Cons:** Less flexible for complex scenarios

#### Option B: Strategy Pattern (Advanced)
- Create `IMAPQueryBuilder` class with pluggable strategies
- Different strategies for different query building approaches
- **Pros:** Very flexible, extensible
- **Cons:** Over-engineered for current needs, more complex

#### Option C: Hybrid Approach (Balanced)
- Configuration-based with builder class
- Simple builder for common cases
- Extensible for future needs
- **Pros:** Good balance of simplicity and flexibility
- **Cons:** Slightly more complex than Option A

### 3. Recommended Implementation (Option A - Simple)

#### Step 1: Update Config Schema

```python
# In src/config.py
class ConfigManager:
    def _build(self):
        # ... existing code ...
        
        # V2: IMAP query exclusions (Task 16)
        self.imap_query_exclusions = self.yaml.get('imap_query_exclusions', {})
        
        # Default exclude tags (backward compatible)
        default_exclude_tags = [
            'AIProcessed',
            'ObsidianNoteCreated', 
            'NoteCreationFailed'
        ]
        
        # Get exclude tags from config or use defaults
        exclude_tags = self.imap_query_exclusions.get('exclude_tags', default_exclude_tags)
        additional_tags = self.imap_query_exclusions.get('additional_exclude_tags', [])
        
        # Combine and validate
        self.exclude_tags = list(set(exclude_tags + additional_tags))  # Remove duplicates
        
        # Validate tags are strings and not empty
        if not all(isinstance(tag, str) and tag.strip() for tag in self.exclude_tags):
            raise ConfigFormatError("exclude_tags must be a list of non-empty strings")
        
        # Optional: Allow disabling idempotency (with warning)
        self.disable_idempotency = self.imap_query_exclusions.get('disable_idempotency', False)
        if self.disable_idempotency:
            logger.warning("Idempotency checks are disabled - emails may be reprocessed!")
```

#### Step 2: Create Query Builder Function

```python
# In src/imap_connection.py
def build_imap_query_with_exclusions(
    user_query: str,
    exclude_tags: List[str],
    disable_idempotency: bool = False
) -> str:
    """
    Build IMAP query combining user query with tag exclusions.
    
    Args:
        user_query: User-defined IMAP query (e.g., 'UNSEEN')
        exclude_tags: List of tags to exclude (e.g., ['AIProcessed', 'ObsidianNoteCreated'])
        disable_idempotency: If True, return only user_query (no exclusions)
    
    Returns:
        Combined IMAP query string
        
    Example:
        >>> build_imap_query_with_exclusions('UNSEEN', ['AIProcessed', 'ObsidianNoteCreated'])
        '(UNSEEN NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated")'
    """
    if disable_idempotency:
        return user_query
    
    if not exclude_tags:
        return user_query
    
    # Build NOT KEYWORD clauses for each tag
    exclusion_clauses = ' '.join(f'NOT KEYWORD "{tag}"' for tag in exclude_tags)
    
    # Combine: ({user_query} NOT KEYWORD "tag1" NOT KEYWORD "tag2" ...)
    final_query = f'({user_query} {exclusion_clauses})'
    
    return final_query
```

#### Step 3: Update search_emails_excluding_processed()

```python
# In src/imap_connection.py
def search_emails_excluding_processed(
    imap, 
    user_query: str, 
    exclude_tags: Optional[List[str]] = None,
    disable_idempotency: bool = False
) -> List[bytes]:
    """
    Search emails using user query combined with idempotency checks.
    
    Args:
        imap: IMAP connection object
        user_query: User-defined IMAP query string from config
        exclude_tags: List of tags to exclude (defaults to standard idempotency tags)
        disable_idempotency: If True, skip idempotency checks
    
    Returns:
        List of email UIDs (bytes)
    """
    # Default exclude tags for backward compatibility
    if exclude_tags is None:
        exclude_tags = ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']
    
    try:
        imap.select('INBOX')
        
        # Build query using new builder function
        final_query = build_imap_query_with_exclusions(
            user_query,
            exclude_tags,
            disable_idempotency
        )
        
        logging.debug(f"Executing IMAP query: {final_query}")
        
        # ... rest of function unchanged ...
```

#### Step 4: Update fetch_emails() and main_loop.py

```python
# In src/imap_connection.py - update fetch_emails() signature
def fetch_emails(
    host: str, user: str, password: str,
    user_query: str,
    exclude_tags: Optional[List[str]] = None,
    disable_idempotency: bool = False,
    max_retries: int = 3,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    # ... existing code ...
    ids = search_emails_excluding_processed(
        imap, 
        user_query, 
        exclude_tags=exclude_tags,
        disable_idempotency=disable_idempotency
    )
    # ... rest unchanged ...

# In src/main_loop.py - update call site
emails = fetch_emails(
    host=imap_params['host'],
    user=imap_params['username'],
    password=imap_params['password'],
    user_query=user_query,
    exclude_tags=config.exclude_tags,
    disable_idempotency=config.disable_idempotency
)
```

### 4. Backward Compatibility

**Default Behavior (No Config Changes):**
- If `imap_query_exclusions` is not in config, use default three tags
- Existing code continues to work without changes
- Function signatures maintain backward compatibility with optional parameters

**Migration Path:**
- Users can gradually adopt new config options
- Old configs work without modification
- New configs can customize as needed

### 5. Validation & Error Handling

```python
# In config.py validation
def validate_imap_query_exclusions(exclusions: Dict[str, Any]) -> None:
    """Validate imap_query_exclusions configuration."""
    if not isinstance(exclusions, dict):
        raise ConfigFormatError("imap_query_exclusions must be a dictionary")
    
    # Validate exclude_tags
    if 'exclude_tags' in exclusions:
        tags = exclusions['exclude_tags']
        if not isinstance(tags, list):
            raise ConfigFormatError("exclude_tags must be a list")
        if not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ConfigFormatError("exclude_tags must contain non-empty strings")
        # Warn if empty (no idempotency protection)
        if not tags and not exclusions.get('disable_idempotency'):
            logger.warning("exclude_tags is empty - idempotency may be compromised")
    
    # Validate disable_idempotency
    if 'disable_idempotency' in exclusions:
        if not isinstance(exclusions['disable_idempotency'], bool):
            raise ConfigFormatError("disable_idempotency must be a boolean")
```

### 6. Configuration Examples

**Example 1: Default (Backward Compatible)**
```yaml
# No imap_query_exclusions section = uses defaults
imap_query: 'UNSEEN'
```

**Example 2: Custom Exclusions**
```yaml
imap_query: 'UNSEEN'
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
    - 'CustomTag'  # Additional custom tag
```

**Example 3: Minimal Exclusions (Only V2 Tags)**
```yaml
imap_query: 'UNSEEN'
imap_query_exclusions:
  exclude_tags:
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
  # Note: AIProcessed not excluded (V1 emails can be reprocessed)
```

**Example 4: Additional Tags**
```yaml
imap_query: 'UNSEEN'
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
  additional_exclude_tags:
    - 'Archived'
    - 'ProcessedByOtherTool'
```

### 7. Testing Strategy

1. **Unit Tests:**
   - Test `build_imap_query_with_exclusions()` with various inputs
   - Test default behavior (backward compatibility)
   - Test empty exclude_tags list
   - Test disable_idempotency flag
   - Test query syntax validation

2. **Integration Tests:**
   - Test with actual IMAP server
   - Verify queries filter correctly
   - Test performance with large tag lists

3. **Configuration Tests:**
   - Test invalid configurations are rejected
   - Test default values when config missing
   - Test migration from old to new config

### 8. Documentation Updates

- Update `config/config.yaml.example` with new section
- Update `docs/COMPLETE_GUIDE.md` with configuration examples
- Add migration guide for users wanting to customize

## Benefits

1. **Flexibility:** Users can customize which tags to exclude
2. **Backward Compatible:** Default behavior unchanged
3. **Extensible:** Easy to add more exclusion criteria in future
4. **Safe:** Validation prevents invalid configurations
5. **Simple:** Not over-engineered, easy to understand

## Risks & Mitigations

1. **Risk:** Users might disable idempotency accidentally
   - **Mitigation:** Warning log when disabled, clear documentation

2. **Risk:** Invalid tag names break IMAP queries
   - **Mitigation:** Validation, IMAP error handling

3. **Risk:** Performance impact with many tags
   - **Mitigation:** IMAP handles multiple NOT clauses efficiently, test with large lists

## Implementation Estimate

- **Config changes:** 1-2 hours
- **Query builder function:** 1-2 hours
- **Update existing functions:** 1-2 hours
- **Tests:** 2-3 hours
- **Documentation:** 1 hour
- **Total:** ~6-10 hours

## Recommendation

**Proceed with Option A (Simple Configuration-Based)** because:
- Meets all requirements
- Maintains backward compatibility
- Easy to implement and test
- Can be extended later if needed
- Low risk of breaking existing functionality
