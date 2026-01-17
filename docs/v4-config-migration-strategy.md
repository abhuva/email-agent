# V4 Configuration Migration Strategy

**Task:** 22.5 - Migrate Configuration from V3 Settings to V4 ConfigLoader  
**Date:** 2026-01-17  
**Status:** In Progress

---

## Overview

This document outlines the strategy for migrating from V3's `settings` facade (singleton pattern) to V4's `ConfigLoader` (per-account configuration).

---

## Current State

### V3 Pattern (Settings Facade)
```python
from src.settings import settings

# Global singleton, initialized once
settings.initialize('config/config.yaml', '.env')

# Access anywhere
server = settings.get_imap_server()
api_key = settings.get_openrouter_api_key()
```

### V4 Pattern (ConfigLoader)
```python
from src.config_loader import ConfigLoader

# Per-account configuration
loader = ConfigLoader(base_dir='config')
account_config = loader.load_merged_config('work')

# Direct access
server = account_config['imap']['server']
api_key = os.environ.get(account_config['openrouter']['api_key_env'])
```

---

## Migration Challenges

### 1. Component Initialization

**Problem:** Components like `LLMClient`, `NoteGenerator`, `DecisionLogic` are created as shared instances in `MasterOrchestrator`, but they use the global `settings` facade.

**Current:**
```python
# MasterOrchestrator._initialize_shared_services()
self.llm_client = LLMClient()  # Uses settings facade internally
self.note_generator = NoteGenerator()  # Uses settings facade internally
```

**Solution Options:**
- **Option A:** Make components accept config in `__init__` (requires API changes)
- **Option B:** Make components accept config per-call (requires method signature changes)
- **Option C:** Create components per-account (more instances, but cleaner)

**Recommendation:** Option A - Update components to accept config dict in `__init__`

### 2. Shared vs Per-Account Components

**Current:** Components are shared across accounts (stateless assumption)

**Reality:** Some components need account-specific config:
- `LLMClient` - may have different models per account
- `NoteGenerator` - may have different templates per account
- `DecisionLogic` - may have different thresholds per account

**Solution:** Create components per-account with account-specific config

### 3. Environment Variable Access

**V3:** `settings.get_imap_password()` handles env var lookup
**V4:** Need to handle env vars manually: `os.environ.get(config['imap']['password_env'])`

**Solution:** Create helper function or update components to handle this

---

## Migration Strategy

### Phase 1: Update Component APIs

1. **LLMClient**
   - Change `__init__(self)` → `__init__(self, config: Dict[str, Any])`
   - Remove `_load_config()` method
   - Extract config values directly from dict

2. **NoteGenerator**
   - Change `__init__(self)` → `__init__(self, config: Dict[str, Any])`
   - Update template loading to use config dict

3. **DecisionLogic**
   - Change `classify()` to accept thresholds as parameters
   - Or: `__init__(self, config: Dict[str, Any])`

4. **ImapClient**
   - Already has `create_imap_client_from_config()` factory
   - This is already V4-compatible

### Phase 2: Update MasterOrchestrator

1. **Remove shared component initialization**
   - Don't create shared `llm_client`, `note_generator`, `decision_logic`
   - Create them per-account in `create_account_processor()`

2. **Pass account config to components**
   ```python
   llm_client = LLMClient(account_config)
   note_generator = NoteGenerator(account_config)
   decision_logic = DecisionLogic(account_config)
   ```

### Phase 3: Update Other Modules

1. **Modules used by AccountProcessor:**
   - `summarization.py` - Update to use config dict
   - `email_summarization.py` - Update to use config dict
   - `prompt_renderer.py` - Update to use config dict

2. **Modules used by cleanup/backfill:**
   - `cleanup_flags.py` - Update to use ConfigLoader
   - `backfill.py` - Update to use AccountProcessor (not Pipeline)

### Phase 4: Remove Settings Facade

1. Delete `src/settings.py`
2. Delete `src/config_v3_loader.py`
3. Delete `src/config_v3_schema.py`
4. Remove all `from src.settings import settings` imports

---

## Module Migration Priority

### High Priority (Used by V4 AccountProcessor)
1. ✅ `LLMClient` - Core component
2. ✅ `NoteGenerator` - Core component
3. ✅ `DecisionLogic` - Core component
4. `summarization.py` - Used by AccountProcessor
5. `email_summarization.py` - Used by AccountProcessor
6. `prompt_renderer.py` - Used by AccountProcessor

### Medium Priority (Used by cleanup/backfill)
7. `cleanup_flags.py` - Needs V4 migration for CLI
8. `backfill.py` - Needs V4 migration for CLI

### Low Priority (Only used by Pipeline - will be removed)
9. `orchestrator.py::Pipeline` - Will be deleted
10. Other Pipeline-only modules - Will be deleted

---

## Migration Pattern

### Before (V3)
```python
class LLMClient:
    def __init__(self):
        self._api_key = None  # Lazy load from settings
    
    def _load_config(self):
        self._api_key = settings.get_openrouter_api_key()
        self._model = settings.get_classification_model()
```

### After (V4)
```python
class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        """Initialize with account-specific configuration."""
        openrouter_config = config.get('openrouter', {})
        classification_config = config.get('classification', {})
        
        # Get API key from environment
        api_key_env = openrouter_config.get('api_key_env', 'OPENROUTER_API_KEY')
        self._api_key = os.environ.get(api_key_env)
        if not self._api_key:
            raise ConfigError(f"API key env var '{api_key_env}' not set")
        
        self._api_url = openrouter_config.get('api_url')
        self._model = classification_config.get('model')
        self._temperature = classification_config.get('temperature')
```

---

## Helper Functions Needed

### Environment Variable Helper
```python
def get_env_var(config_path: List[str], config: Dict[str, Any], default: Optional[str] = None) -> str:
    """
    Get environment variable value from config path.
    
    Args:
        config_path: Path to env var name in config (e.g., ['imap', 'password_env'])
        config: Configuration dictionary
        default: Default value if not found
        
    Returns:
        Environment variable value
        
    Raises:
        ConfigError: If env var is not set and no default provided
    """
    # Navigate config path
    value = config
    for key in config_path:
        value = value.get(key, {})
    
    if not value:
        if default is None:
            raise ConfigError(f"Config path {config_path} not found and no default provided")
        return default
    
    # Get env var
    env_value = os.environ.get(value)
    if not env_value:
        raise ConfigError(f"Environment variable '{value}' is not set")
    return env_value
```

---

## Testing Strategy

1. **Unit Tests:** Update all component tests to pass config dict instead of mocking settings
2. **Integration Tests:** Verify components work with account-specific configs
3. **E2E Tests:** Verify full pipeline works with V4 config system

---

## Rollout Plan

1. **Week 1:** Update component APIs (LLMClient, NoteGenerator, DecisionLogic)
2. **Week 2:** Update MasterOrchestrator to create components per-account
3. **Week 3:** Update supporting modules (summarization, etc.)
4. **Week 4:** Update cleanup/backfill modules
5. **Week 5:** Remove settings facade and V3 config modules

---

## Notes

- **Backward Compatibility:** None - we're removing V3 completely
- **Breaking Changes:** All components will require config parameter
- **Migration Complexity:** High - affects many modules
- **Risk:** Medium - components are well-tested, but API changes are significant

---

**End of Strategy Document**
