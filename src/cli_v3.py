"""
V3 Command-line interface for the email agent.

This module implements the V3 CLI using click as specified in the PDD.
Replaces the argparse-based CLI in cli.py.

CLI Structure:
    python main.py process [--uid <ID>] [--force-reprocess] [--dry-run]
    python main.py cleanup-flags
"""
import click
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from src.settings import settings
from src.config import ConfigError


@dataclass
class ProcessOptions:
    """Structured options for the process command."""
    uid: Optional[str]
    force_reprocess: bool
    dry_run: bool
    config_path: str
    env_path: str


@dataclass
class CleanupFlagsOptions:
    """Structured options for the cleanup-flags command."""
    config_path: str
    env_path: str


@click.group()
@click.version_option(version='3.0.0', prog_name='email-agent')
@click.option(
    '--config',
    type=click.Path(path_type=Path),
    default='config/config.yaml',
    help='Path to YAML configuration file (default: config/config.yaml)'
)
@click.option(
    '--env',
    type=click.Path(path_type=Path),
    default='.env',
    help='Path to .env secrets file (default: .env)'
)
@click.pass_context
def cli(ctx: click.Context, config: Path, env: Path):
    """
    Email-Agent: Headless IMAP AI Triage CLI
    
    Process emails using AI classification and generate Obsidian notes.
    Supports both V3 (single-account) and V4 (multi-account) processing modes.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Store config paths in context (don't validate existence here - let commands do it)
    ctx.obj['config_path'] = str(config)
    ctx.obj['env_path'] = str(env)
    ctx.obj['config_initialized'] = False


def _ensure_config_initialized(ctx: click.Context) -> None:
    """
    Lazy initialization of settings facade.
    Only loads config when actually needed (not for --help).
    
    Args:
        ctx: Click context object
        
    Raises:
        SystemExit: If config loading fails
    """
    if ctx.obj.get('config_initialized', False):
        return
    
    config_path = ctx.obj['config_path']
    env_path = ctx.obj['env_path']
    
    # Validate config file exists
    if not Path(config_path).exists():
        click.echo(f"Configuration error: Config file not found: {config_path}", err=True)
        sys.exit(1)
    
    # Initialize settings facade
    try:
        settings.initialize(config_path, env_path)
        ctx.obj['config_initialized'] = True
    except ConfigError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error loading configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--uid',
    type=str,
    help='Target a specific email by UID. If not provided, processes emails according to configured query.'
)
@click.option(
    '--force-reprocess',
    is_flag=True,
    default=False,
    help='Ignore existing processed_tag and reprocess emails even if already marked as processed.'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Output to console instead of writing files or setting IMAP flags. Useful for testing.'
)
@click.option(
    '--max-emails',
    type=int,
    help='Maximum number of emails to process (overrides config max_emails_per_run). Useful for testing with a limited number of emails.'
)
@click.option(
    '--debug-prompt',
    is_flag=True,
    default=False,
    help='Write the formatted classification prompt to a debug file in logs/ directory. Useful for debugging prompt construction.'
)
@click.option(
    '--account',
    type=str,
    help='Process a specific account by name (V4 multi-account mode). Mutually exclusive with --all.'
)
@click.option(
    '--all',
    'all_accounts',
    is_flag=True,
    default=False,
    help='Process all available accounts (V4 multi-account mode). Mutually exclusive with --account.'
)
@click.pass_context
def process(ctx: click.Context, uid: Optional[str], force_reprocess: bool, dry_run: bool, max_emails: Optional[int], debug_prompt: bool, account: Optional[str], all_accounts: bool):
    """
    Main command for bulk or single email processing.
    
    Processes emails using AI classification and generates Obsidian notes.
    By default, processes unprocessed emails according to the configured IMAP query.
    
    V4 Multi-Account Mode:
        Use --account <name> to process a specific account, or --all to process all accounts.
        These options are mutually exclusive and enable V4 multi-account processing.
    
    Examples:
        python main.py process                    # Process unprocessed emails (V3 mode)
        python main.py process --uid 12345       # Process specific email (V3 mode)
        python main.py process --force-reprocess # Reprocess all emails (V3 mode)
        python main.py process --dry-run         # Test without side effects
        python main.py process --max-emails 5    # Process only 5 emails
        python main.py process --uid 400 --debug-prompt  # Write prompt to debug file
        python main.py process --account work    # Process 'work' account (V4 mode)
        python main.py process --all             # Process all accounts (V4 mode)
        python main.py process --account work --dry-run  # Preview processing for 'work' account
    """
    # Validate account-related arguments (subtask 11.2)
    # Check if account is explicitly provided (not None, even if empty string)
    account_provided = account is not None
    
    if account_provided and all_accounts:
        click.echo("Error: --account and --all are mutually exclusive. Use only one.", err=True)
        sys.exit(1)
    
    # Validate account name if provided (even if empty, to catch empty strings)
    if account_provided:
        try:
            account = _validate_account_name(account)
        except click.BadParameter as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    # If account or all_accounts is specified, use V4 MasterOrchestrator
    if account_provided or all_accounts:
        # V4 multi-account processing path
        _process_v4_accounts(ctx, account, all_accounts, dry_run)
        return
    
    # V3 single-account processing path (existing behavior)
    # Initialize config (lazy loading)
    _ensure_config_initialized(ctx)
    
    # Create structured options object
    options = ProcessOptions(
        uid=uid,
        force_reprocess=force_reprocess,
        dry_run=dry_run,
        config_path=ctx.obj['config_path'],
        env_path=ctx.obj['env_path']
    )
    
    # Store in context for potential use by other functions
    ctx.obj['process_options'] = options
    
    # Validate UID format if provided
    if uid is not None:
        try:
            # UID should be a valid string (IMAP UIDs are typically numeric strings)
            if not uid.strip():
                raise click.BadParameter("UID cannot be empty")
            # Basic validation: UID should be non-empty and reasonable length
            if len(uid.strip()) > 100:
                raise click.BadParameter("UID is too long (max 100 characters)")
        except AttributeError:
            raise click.BadParameter("UID must be a valid string")
    
    # Set dry-run mode globally if enabled
    if dry_run:
        from src.dry_run import set_dry_run
        set_dry_run(True)
        try:
            from src.dry_run_output import DryRunOutput, Colors, _colorize
            click.echo(_colorize("[DRY RUN MODE] No files will be written or flags set", Colors.YELLOW, bold=True))
        except ImportError:
            click.echo("[DRY RUN MODE] No files will be written or flags set")
    
    # Initialize logging
    try:
        from src.logger import LoggerFactory
        from src.settings import settings
        log_file = settings.get_log_file()
        logger_instance = LoggerFactory.create_logger(
            name='email_agent',
            level='INFO',
            log_file=log_file,
            console=True
        )
        logging.getLogger('email_agent').info("Logging initialized")
    except Exception as e:
        click.echo(f"Warning: Could not initialize logging: {e}", err=True)
    
    # Create pipeline and process emails
    try:
        from src.orchestrator import Pipeline, ProcessOptions as PipelineProcessOptions
        
        # Create pipeline options
        pipeline_options = PipelineProcessOptions(
            uid=uid,
            force_reprocess=force_reprocess,
            dry_run=dry_run,
            max_emails=max_emails,
            debug_prompt=debug_prompt
        )
        
        # Create and run pipeline
        pipeline = Pipeline()
        summary = pipeline.process_emails(pipeline_options)
        
        # Display results
        if dry_run:
            try:
                from src.dry_run_output import DryRunOutput
                output = DryRunOutput()
                output.header("Processing Complete")
                output.info(f"Processed {summary.total_emails} email(s)")
                output.detail("Successful", summary.successful)
                output.detail("Failed", summary.failed)
                output.detail("Total time", f"{summary.total_time:.2f}s")
                if summary.total_emails > 0:
                    output.detail("Average time", f"{summary.average_time:.2f}s per email")
            except ImportError:
                click.echo(f"\nProcessing complete: {summary.successful} successful, {summary.failed} failed")
        else:
            click.echo(f"\nProcessing complete: {summary.successful} successful, {summary.failed} failed in {summary.total_time:.2f}s")
        
        # Exit with error code if any failures
        if summary.failed > 0:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error during processing: {e}", err=True)
        logger = logging.getLogger(__name__)
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        sys.exit(1)
    
    # Return options for programmatic use
    return options


@cli.command()
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Preview which flags would be removed without actually removing them.'
)
@click.pass_context
def cleanup_flags(ctx: click.Context, dry_run: bool):
    """
    Maintenance command to clean up application-specific IMAP flags.
    
    This command removes only application-specific flags (as defined in configuration)
    from emails in the IMAP server. Use this command if you need to reset the
    processing state or clean up flags.
    
    WARNING: This will remove application-specific flags from emails, which may
    cause them to be reprocessed on the next run. This action cannot be undone.
    
    This command requires explicit confirmation before execution (security requirement).
    """
    # Initialize config (lazy loading)
    _ensure_config_initialized(ctx)
    
    # Initialize logging
    try:
        from src.logger import LoggerFactory
        log_file = settings.get_log_file()
        logger_instance = LoggerFactory.create_logger(
            name='email_agent',
            level='INFO',
            log_file=log_file,
            console=True
        )
        logging.getLogger('email_agent').info("Logging initialized for cleanup-flags command")
    except Exception as e:
        click.echo(f"Warning: Could not initialize logging: {e}", err=True)
    
    # Create structured options object
    options = CleanupFlagsOptions(
        config_path=ctx.obj['config_path'],
        env_path=ctx.obj['env_path']
    )
    
    # Store in context for potential use by other functions
    ctx.obj['cleanup_options'] = options
    
    # Get application flags from settings
    try:
        application_flags = settings.get_imap_application_flags()
        flags_list = ', '.join(application_flags)
    except Exception as e:
        click.echo(f"Error: Failed to load application flags configuration: {e}", err=True)
        sys.exit(1)
    
    # Display warning message
    click.echo("\n" + "=" * 70, err=True)
    click.echo("WARNING: This command will remove application-specific flags from emails", err=True)
    click.echo("in your IMAP mailbox. This action cannot be undone.", err=True)
    click.echo("=" * 70 + "\n", err=True)
    
    click.echo(f"Application-specific flags to remove: {flags_list}")
    click.echo("\nThis may cause emails to be reprocessed on the next run.")
    
    if dry_run:
        click.echo("\n[DRY RUN MODE] No flags will actually be removed.")
    
    # Mandatory confirmation prompt (PDD requirement)
    if not dry_run:
        confirmation = click.prompt(
            "\nType 'yes' to confirm and proceed, or anything else to cancel",
            type=str,
            default='no'
        )
        
        if confirmation.lower().strip() != 'yes':
            click.echo("\nOperation cancelled. No flags were modified.", err=True)
            sys.exit(0)
    
    # Perform cleanup operation
    try:
        from src.cleanup_flags import CleanupFlags
        
        cleanup = CleanupFlags()
        cleanup.connect()
        
        try:
            # Scan for flags
            click.echo("\nScanning emails for application-specific flags...")
            scan_results = cleanup.scan_flags(dry_run=dry_run)
            
            if not scan_results:
                click.echo("\nNo emails with application-specific flags found.")
                cleanup.disconnect()
                return options
            
            # Display scan results
            formatted_results = cleanup.format_scan_results(scan_results)
            click.echo(formatted_results)
            
            # Remove flags
            if dry_run:
                click.echo("\n[DRY RUN] Preview of what would be removed:")
            else:
                click.echo("\nRemoving application-specific flags...")
            
            summary = cleanup.remove_flags(scan_results, dry_run=dry_run)
            
            # Display summary
            click.echo("\n" + "=" * 70)
            click.echo("Cleanup Summary:")
            click.echo(f"  Emails scanned: {summary.total_emails_scanned}")
            click.echo(f"  Emails with flags: {summary.emails_with_flags}")
            click.echo(f"  Flags removed: {summary.total_flags_removed}")
            click.echo(f"  Emails modified: {summary.emails_modified}")
            if summary.errors > 0:
                click.echo(f"  Errors: {summary.errors}", err=True)
            click.echo("=" * 70)
            
            if dry_run:
                click.echo("\n[DRY RUN] No flags were actually removed.")
            else:
                click.echo("\nCleanup complete!")
            
            cleanup.disconnect()
            
            # Exit with error code if there were errors
            if summary.errors > 0:
                sys.exit(1)
            
        except Exception as e:
            cleanup.disconnect()
            raise
        
    except Exception as e:
        click.echo(f"\nError during cleanup operation: {e}", err=True)
        logger = logging.getLogger(__name__)
        logger.error(f"Cleanup flags command failed: {e}", exc_info=True)
        sys.exit(1)
    
    # Return options for programmatic use
    return options


@cli.command()
@click.option(
    '--start-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    help='Start date for backfill (YYYY-MM-DD). If not provided, processes all emails from the beginning.'
)
@click.option(
    '--end-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    help='End date for backfill (YYYY-MM-DD). If not provided, processes all emails up to now.'
)
@click.option(
    '--folder',
    type=str,
    help='IMAP folder to process (default: INBOX). Use folder names like "INBOX", "Sent", etc.'
)
@click.option(
    '--force-reprocess',
    is_flag=True,
    default=True,
    help='Reprocess emails even if already marked as processed (default: True for backfill).'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Preview mode: process emails but don\'t write files or set IMAP flags.'
)
@click.option(
    '--max-emails',
    type=int,
    help='Maximum number of emails to process (useful for testing). If not provided, processes all matching emails.'
)
@click.option(
    '--calls-per-minute',
    type=int,
    help='Maximum API calls per minute for throttling (default: from settings or 60).'
)
@click.pass_context
def backfill(
    ctx: click.Context,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    folder: Optional[str],
    force_reprocess: bool,
    dry_run: bool,
    max_emails: Optional[int],
    calls_per_minute: Optional[int]
):
    """
    Process all historical emails with the new classification system.
    
    This command processes all emails in the target mailbox, regardless of their
    current flag status. Useful for backfilling historical emails with the new
    V3 classification system.
    
    Supports date range filtering, folder selection, progress tracking, and
    API throttling to prevent rate limiting.
    
    Examples:
        python main.py backfill                                    # Process all emails
        python main.py backfill --start-date 2024-01-01            # From Jan 1, 2024
        python main.py backfill --start-date 2024-01-01 --end-date 2024-12-31  # Date range
        python main.py backfill --folder "Sent"                    # Specific folder
        python main.py backfill --max-emails 100                   # Limit to 100 emails
        python main.py backfill --dry-run                           # Preview mode
    """
    # Initialize config (lazy loading)
    _ensure_config_initialized(ctx)
    
    # Initialize logging
    try:
        from src.logger import LoggerFactory
        log_file = settings.get_log_file()
        logger_instance = LoggerFactory.create_logger(
            name='email_agent',
            level='INFO',
            log_file=log_file,
            console=True
        )
        logging.getLogger('email_agent').info("Logging initialized for backfill command")
    except Exception as e:
        click.echo(f"Warning: Could not initialize logging: {e}", err=True)
    
    # Convert datetime to date if provided
    start_date_obj = start_date.date() if start_date else None
    end_date_obj = end_date.date() if end_date else None
    
    # Validate date range
    if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
        click.echo(f"Error: Start date ({start_date_obj}) must be before end date ({end_date_obj})", err=True)
        sys.exit(1)
    
    # Display backfill configuration
    click.echo("\n" + "=" * 70)
    click.echo("BACKFILL OPERATION")
    click.echo("=" * 70)
    click.echo(f"Start date: {start_date_obj or 'All time'}")
    click.echo(f"End date: {end_date_obj or 'All time'}")
    click.echo(f"Folder: {folder or 'Default (INBOX)'}")
    click.echo(f"Force reprocess: {force_reprocess}")
    click.echo(f"Dry run: {dry_run}")
    click.echo(f"Max emails: {max_emails or 'Unlimited'}")
    click.echo(f"Throttling: {calls_per_minute or 'From settings'}")
    click.echo("=" * 70 + "\n")
    
    if dry_run:
        click.echo("[DRY RUN MODE] No files will be written and no IMAP flags will be set.\n")
    
    # Confirm before proceeding (for large backfills)
    if not dry_run and (not max_emails or max_emails > 100):
        click.echo("Warning: This will process all matching emails, which may take a long time.")
        confirmation = click.prompt(
            "Type 'yes' to proceed, or anything else to cancel",
            type=str,
            default='no'
        )
        
        if confirmation.lower().strip() != 'yes':
            click.echo("\nOperation cancelled.", err=True)
            sys.exit(0)
    
    # Perform backfill operation
    try:
        from src.backfill import BackfillProcessor
        
        processor = BackfillProcessor(calls_per_minute=calls_per_minute)
        
        summary = processor.backfill_emails(
            start_date=start_date_obj,
            end_date=end_date_obj,
            folder=folder,
            force_reprocess=force_reprocess,
            dry_run=dry_run,
            max_emails=max_emails
        )
        
        # Display summary
        click.echo("\n" + "=" * 70)
        click.echo("BACKFILL SUMMARY")
        click.echo("=" * 70)
        click.echo(f"Total emails found: {summary.total_emails}")
        click.echo(f"  ✓ Successfully processed: {summary.processed}")
        click.echo(f"  ✗ Failed: {summary.failed}")
        click.echo(f"  ⊘ Skipped: {summary.skipped}")
        click.echo(f"Total time: {summary.total_time:.2f}s")
        click.echo(f"Average time per email: {summary.average_time:.2f}s")
        if summary.processed > 0:
            success_rate = (summary.processed / summary.total_emails) * 100
            click.echo(f"Success rate: {success_rate:.1f}%")
        click.echo(f"Start time: {summary.start_time}")
        click.echo(f"End time: {summary.end_time}")
        click.echo("=" * 70)
        
        if dry_run:
            click.echo("\n[DRY RUN] No files were written and no IMAP flags were set.")
        else:
            click.echo("\nBackfill complete!")
        
        # Exit with error code if there were failures
        if summary.failed > 0:
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"\nError during backfill operation: {e}", err=True)
        logger = logging.getLogger(__name__)
        logger.error(f"Backfill command failed: {e}", exc_info=True)
        sys.exit(1)


def get_process_options(ctx: click.Context) -> ProcessOptions:
    """
    Extract process command options from click context.
    
    Args:
        ctx: Click context object
        
    Returns:
        ProcessOptions dataclass with parsed values
        
    Raises:
        RuntimeError: If called outside of process command context
    """
    if 'process_options' not in ctx.obj:
        raise RuntimeError("get_process_options() must be called within process command context")
    return ctx.obj['process_options']


def get_cleanup_options(ctx: click.Context) -> CleanupFlagsOptions:
    """
    Extract cleanup-flags command options from click context.
    
    Args:
        ctx: Click context object
        
    Returns:
        CleanupFlagsOptions dataclass with parsed values
        
    Raises:
        RuntimeError: If called outside of cleanup-flags command context
    """
    if 'cleanup_options' not in ctx.obj:
        raise RuntimeError("get_cleanup_options() must be called within cleanup-flags command context")
    return ctx.obj['cleanup_options']


def _validate_account_name(account_name: str) -> str:
    """
    Validate account name format and return normalized name.
    
    Args:
        account_name: Account name to validate
        
    Returns:
        Normalized account name (stripped)
        
    Raises:
        click.BadParameter: If account name is invalid
    """
    if not account_name:
        raise click.BadParameter("Account name cannot be empty")
    
    account_name = account_name.strip()
    
    if not account_name:
        raise click.BadParameter("Account name cannot be empty or whitespace only")
    
    # Validate length (reasonable limit)
    if len(account_name) > 100:
        raise click.BadParameter("Account name is too long (max 100 characters)")
    
    # Validate characters (alphanumeric, dash, underscore)
    if not all(c.isalnum() or c in ('-', '_') for c in account_name):
        raise click.BadParameter(
            "Account name contains invalid characters. "
            "Only alphanumeric characters, dashes, and underscores are allowed."
        )
    
    return account_name


def _process_v4_accounts(
    ctx: click.Context,
    account: Optional[str],
    all_accounts: bool,
    dry_run: bool
) -> None:
    """
    Process accounts using V4 MasterOrchestrator.
    
    This function handles multi-account processing by:
    1. Building argv for MasterOrchestrator
    2. Creating and running MasterOrchestrator
    3. Displaying results
    
    Args:
        ctx: Click context object
        account: Account name to process (already validated, None if processing all)
        all_accounts: Whether to process all accounts
        dry_run: Whether to run in dry-run mode
    """
    import logging
    from pathlib import Path
    from src.orchestrator import MasterOrchestrator
    
    # Build argv for MasterOrchestrator
    argv = []
    if account:
        argv.extend(['--account', account])
    elif all_accounts:
        argv.append('--all-accounts')
    
    if dry_run:
        argv.append('--dry-run')
    
    # Get config directory from context
    config_dir = ctx.obj.get('config_path', 'config/config.yaml')
    # Extract directory from config path
    if config_dir.endswith('.yaml') or config_dir.endswith('.yml'):
        config_base_dir = str(Path(config_dir).parent)
    else:
        config_base_dir = config_dir
    
    # Override if config_dir is different from default
    if config_base_dir != 'config':
        argv.extend(['--config-dir', config_base_dir])
    
    # Initialize logging
    logger = logging.getLogger('email_agent')
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    try:
        # Create MasterOrchestrator
        orchestrator = MasterOrchestrator(
            config_base_dir=config_base_dir,
            logger=logger
        )
        
        # Run orchestration
        result = orchestrator.run(argv)
        
        # Display results
        click.echo("\n" + "=" * 70)
        click.echo("Processing Summary")
        click.echo("=" * 70)
        click.echo(f"Total accounts: {result.total_accounts}")
        click.echo(f"  ✓ Successful: {result.successful_accounts}")
        click.echo(f"  ✗ Failed: {result.failed_accounts}")
        click.echo(f"Total time: {result.total_time:.2f}s")
        
        if result.failed_accounts > 0:
            click.echo("\nFailed accounts:")
            for account_id, (success, error) in result.account_results.items():
                if not success:
                    click.echo(f"  - {account_id}: {error}", err=True)
            click.echo("=" * 70)
            sys.exit(1)
        else:
            click.echo("=" * 70)
            
    except Exception as e:
        click.echo(f"Error during multi-account processing: {e}", err=True)
        logger.error(f"MasterOrchestrator execution failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--account',
    type=str,
    required=True,
    help='Account name to show configuration for (required)'
)
@click.option(
    '--format',
    type=click.Choice(['yaml', 'json'], case_sensitive=False),
    default='yaml',
    help='Output format (default: yaml)'
)
@click.option(
    '--with-sources',
    is_flag=True,
    default=False,
    help='Include source fields in JSON output (only applies to JSON format)'
)
@click.option(
    '--no-highlight',
    is_flag=True,
    default=False,
    help='Disable highlighting of overridden values (show plain config)'
)
@click.pass_context
def show_config(
    ctx: click.Context,
    account: str,
    format: str,
    with_sources: bool,
    no_highlight: bool
):
    """
    Display merged configuration for a specific account.
    
    Shows the merged configuration (global config + account-specific overrides)
    for the specified account. Overridden values are highlighted to show which
    values come from account-specific config vs global defaults.
    
    In YAML format, overridden values are marked with inline comments:
        server: account.com  # overridden from global
    
    In JSON format, use --with-sources to include __source fields, or check
    the header comment for a list of overridden keys.
    
    Examples:
        python main.py show-config --account work
        python main.py show-config --account work --format json
        python main.py show-config --account work --format json --with-sources
        python main.py show-config --account personal --no-highlight
    """
    from pathlib import Path
    from src.config_loader import ConfigLoader, ConfigurationError
    from src.config_display import AnnotatedConfigMerger, ConfigFormatter
    
    # Validate account name
    try:
        account = _validate_account_name(account)
    except click.BadParameter as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    # Get config directory from context
    config_dir = ctx.obj.get('config_path', 'config/config.yaml')
    # Extract directory from config path
    if config_dir.endswith('.yaml') or config_dir.endswith('.yml'):
        config_base_dir = str(Path(config_dir).parent)
    else:
        config_base_dir = config_dir
    
    try:
        # Load configurations separately (global and account)
        loader = ConfigLoader(
            base_dir=config_base_dir,
            enable_validation=True
        )
        
        # Load global config
        global_config = loader.load_global_config()
        
        # Load account config (returns {} if missing)
        account_config = loader.load_account_config(account)
        
        # Create annotated merged config if highlighting is enabled
        if not no_highlight:
            merger = AnnotatedConfigMerger()
            annotated_config = merger.merge_with_annotations(global_config, account_config)
        else:
            # Just use plain merged config
            annotated_config = loader.load_merged_config(account)
        
        # Format output
        formatter = ConfigFormatter()
        if format.lower() == 'json':
            output = formatter.format_json(
                annotated_config,
                show_sources=not no_highlight,
                include_source_fields=with_sources
            )
        else:  # yaml
            output = formatter.format_yaml(
                annotated_config,
                show_sources=not no_highlight
            )
        
        # Display configuration
        click.echo(f"\nConfiguration for account: {account}")
        if not no_highlight:
            click.echo("(Values marked with '# overridden from global' come from account-specific config)")
        click.echo("=" * 70)
        click.echo(output)
        click.echo("=" * 70)
        
    except FileNotFoundError as e:
        click.echo(f"Error: Configuration file not found: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        # Account name validation error
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ConfigurationError as e:
        click.echo(f"Error: Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Unexpected error loading configuration: {e}", err=True)
        import traceback
        if ctx.obj.get('debug', False):
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    cli()
