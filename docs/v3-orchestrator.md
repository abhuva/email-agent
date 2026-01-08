# V3 Orchestrator Module

**Status:** ✅ Complete (Tasks 14.1-14.6)  
**Module:** `src/orchestrator.py`  
**Integration:** `src/cli_v3.py`

## Overview

The V3 orchestrator module provides high-level business logic orchestration for the email processing pipeline. It coordinates all components (IMAP, LLM, decision logic, note generation, logging) into a cohesive end-to-end processing flow with comprehensive error handling, performance optimizations, and detailed logging.

## Architecture

The orchestrator implements a **Pipeline** class that coordinates:

1. **Email Retrieval** - Fetches emails from IMAP (by UID or all unprocessed)
2. **LLM Classification** - Sends emails to LLM for spam/importance scoring
3. **Decision Logic** - Applies thresholds to determine email categorization
4. **Note Generation** - Generates Markdown notes using Jinja2 templates
5. **File Writing** - Writes notes to Obsidian vault
6. **IMAP Flag Setting** - Marks emails as processed
7. **Logging** - Records processing results to both logging systems

### Key Components

- **Pipeline**: Main orchestration class
- **ProcessOptions**: Configuration for pipeline execution (UID, force_reprocess, dry_run)
- **ProcessingResult**: Result of processing a single email
- **PipelineSummary**: Summary statistics for a pipeline execution

## Usage

### Command-Line

```bash
# Process all unprocessed emails
python main.py process

# Process specific email by UID
python main.py process --uid 12345

# Force reprocess (ignore processed flags)
python main.py process --force-reprocess

# Dry-run mode (preview without side effects)
python main.py process --dry-run
```

### Programmatic Usage

```python
from src.orchestrator import Pipeline, ProcessOptions
from src.settings import settings

# Initialize settings
settings.initialize('config/config.yaml', '.env')

# Create pipeline
pipeline = Pipeline()

# Process emails
options = ProcessOptions(
    uid=None,  # Process all unprocessed emails
    force_reprocess=False,
    dry_run=False
)
summary = pipeline.process_emails(options)

print(f"Processed {summary.successful} emails successfully")
print(f"Failed: {summary.failed}")
print(f"Total time: {summary.total_time:.2f}s")
```

## Pipeline Flow

### Email Processing Stages

1. **Retrieval** (`_retrieve_emails`)
   - Single email by UID, or
   - All unprocessed emails (respects `max_emails_per_run`)
   - Supports `force_reprocess` to ignore processed flags

2. **Classification** (`_classify_email`)
   - Extracts email content (subject, from, body)
   - Truncates body if needed (`max_body_chars`)
   - Builds prompt using prompt renderer
   - Calls LLM client for classification

3. **Decision Logic** (`decision_logic.classify`)
   - Applies thresholds (`importance_threshold`, `spam_threshold`)
   - Generates classification result

4. **Note Generation** (`_generate_note`)
   - Uses note generator with Jinja2 template
   - Includes email data and classification results

5. **File Writing** (`_write_note`)
   - Writes to Obsidian vault
   - Generates unique, timestamped filenames
   - Respects dry-run mode

6. **IMAP Flag Setting** (`_set_imap_flags`)
   - Sets processed tag on successful processing
   - Comprehensive error handling (failures don't crash pipeline)
   - Respects dry-run mode (logs what would be set)
   - Detailed logging of all flag operations

7. **Logging** (`_log_email_processed`)
   - Logs to operational logs (agent.log)
   - Logs to structured analytics (analytics.jsonl)
   - Records success/failure with scores
   - Comprehensive summary logging with statistics

8. **Summary Generation** (`process_emails`)
   - Detailed statistics (total, successful, failed)
   - Performance metrics (total time, average time)
   - Success rate calculation
   - Performance requirement verification
   - Error details for failed emails

## Error Handling

The pipeline implements **per-email error isolation** with comprehensive error handling:

- **Isolated Processing**: Errors in processing one email don't affect others
- **Result Tracking**: Each email's processing result is tracked independently
- **Detailed Logging**: Failures are logged with full error details and context
- **Graceful Continuation**: Pipeline continues processing remaining emails after failures
- **Partial Results**: Returns partial results if errors occur mid-batch
- **Flag Setting Resilience**: IMAP flag setting failures don't crash the pipeline

### Error Types

- **IMAPClientError**: IMAP connection or operation failures
  - Handled gracefully with connection retry logic
  - Partial results returned if connection fails mid-batch
- **LLMClientError**: LLM API failures (handled with retry logic)
  - Automatic retry with exponential backoff
  - Fallback to error response (-1, -1) if all retries fail
- **TemplateRenderError**: Note generation failures
  - Fallback template used if primary template fails
- **FileWriteError**: File system errors
  - Detailed error messages with file paths
  - Directory creation handled automatically
- **ConfigError**: Configuration loading failures
  - Validated at pipeline initialization

## Performance

The pipeline is designed to meet strict performance requirements:

- **Local operations < 1s**: File operations and local processing are optimized
  - Performance metrics tracked and logged
  - Warnings issued if average processing time exceeds 1s
- **No memory leaks**: Comprehensive resource cleanup
  - IMAP connections properly disconnected in finally block
  - Email data references explicitly cleared after processing
  - Progress logging for large batches (every 10 emails)
- **Batch processing**: Handles multiple emails efficiently
  - Sequential processing prevents memory accumulation
  - Memory management optimizations for large batches
  - Resource cleanup after each email

### Performance Monitoring

The pipeline tracks and reports:
- Total pipeline execution time
- Average time per email
- Success rate percentage
- Performance requirement compliance (< 1s per email)

## Configuration

All configuration access is through the `settings.py` facade:

- `settings.get_max_emails_per_run()` - Limit emails per execution
- `settings.get_max_body_chars()` - Body truncation limit
- `settings.get_importance_threshold()` - Importance threshold
- `settings.get_spam_threshold()` - Spam threshold
- `settings.get_obsidian_vault()` - Obsidian vault path
- `settings.get_imap_processed_tag()` - Processed flag name

## Integration Points

### CLI Integration (`src/cli_v3.py`)

The CLI command `process` creates a Pipeline instance and calls `process_emails()`:

```python
from src.orchestrator import Pipeline, ProcessOptions as PipelineProcessOptions

pipeline_options = PipelineProcessOptions(
    uid=uid,
    force_reprocess=force_reprocess,
    dry_run=dry_run
)
pipeline = Pipeline()
summary = pipeline.process_emails(pipeline_options)
```

### Module Dependencies

- **IMAP Client** (`src/imap_client.py`): Email retrieval and flag management
- **LLM Client** (`src/llm_client.py`): Email classification
- **Decision Logic** (`src/decision_logic.py`): Threshold-based classification
- **Note Generator** (`src/note_generator.py`): Markdown note generation
- **V3 Logger** (`src/v3_logger.py`): Dual logging system
- **Dry Run** (`src/dry_run.py`): Dry-run mode support

## Testing

Tests mock the Pipeline class to avoid actual IMAP/LLM connections:

```python
@patch('src.orchestrator.Pipeline')
def test_process_command(mock_pipeline_class, runner, temp_config_file):
    mock_pipeline = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline
    mock_summary = MagicMock()
    mock_summary.total_emails = 0
    mock_summary.successful = 0
    mock_pipeline.process_emails.return_value = mock_summary
    
    result = runner.invoke(cli, ['--config', temp_config_file, 'process'])
    assert result.exit_code == 0
```

## Architecture Details

### State Management

The Pipeline class manages state throughout the processing lifecycle:

- **Component Initialization**: All components (IMAP, LLM, decision logic, note generator, logger) initialized in `__init__`
- **Connection Management**: IMAP connection established at start, disconnected in finally block
- **Result Tracking**: ProcessingResult objects track each email's outcome
- **Error Context**: Full error context preserved for logging and debugging

### Error Propagation Strategy

The pipeline uses a **graceful degradation** approach:

1. **Per-Email Isolation**: Each email processed in try-except block
2. **Error Logging**: All errors logged with full context
3. **Result Tracking**: Success/failure tracked per email
4. **Partial Results**: If batch fails mid-processing, partial results returned
5. **Resource Cleanup**: Cleanup always executed in finally block

### Performance Optimizations

1. **Memory Management**:
   - Email data references cleared after processing
   - Explicit del statements for large objects
   - Progress logging prevents memory accumulation

2. **Resource Cleanup**:
   - IMAP disconnection in finally block
   - Connection state verified before cleanup
   - Debug logging for cleanup verification

3. **Batch Processing**:
   - Sequential processing prevents memory leaks
   - Progress indicators for large batches
   - Early termination on critical errors (with partial results)

## Summary Logging

The pipeline provides comprehensive summary logging:

```
============================================================
EMAIL PROCESSING SUMMARY
============================================================
Total emails processed: 15
  ✓ Successful: 14
  ✗ Failed: 1
Total pipeline time: 12.34s
Average time per email: 0.82s
Average processing time (per email): 0.75s
Success rate: 93.3%
⚠ 1 email(s) failed processing - check logs for details
============================================================
```

## Future Enhancements

- Parallel email processing (with rate limiting)
- Enhanced error recovery strategies (automatic retry for transient failures)
- Performance profiling and optimization
- Real-time progress indicators for long-running operations
- Metrics export for monitoring systems

---

**See Also:**
- [V3 CLI](v3-cli.md) - Command-line interface
- [V3 IMAP Client](v3-imap-client.md) - Email retrieval
- [V3 LLM Client](v3-llm-client.md) - AI classification
- [V3 Decision Logic](v3-decision-logic.md) - Classification logic
- [V3 Note Generator](v3-note-generator.md) - Note generation
