"""
V4 Command-line interface for the email agent.

This module implements the V4 CLI using Click, replacing cli_v3.py.
All commands use V4 components (MasterOrchestrator, ConfigLoader) exclusively.

CLI Structure:
    python main.py process [--account <name>] [--all] [--dry-run] [--uid <ID>] [--force-reprocess]
    python main.py cleanup-flags [--account <name>] [--dry-run]
    python main.py backfill [--account <name>] [--dry-run]
    python main.py show-config [--account <name>] [--format <format>]
"""
import click
import sys
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime

from src.orchestrator import MasterOrchestrator
from src.config_loader import ConfigLoader
from src.logging_config import init_logging
from src.dry_run_output import DryRunOutput


@click.group()
@click.version_option(version='4.0.0', prog_name='email-agent')
@click.option(
    '--config-dir',
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default='config',
    help='Base directory for configuration files (default: config)'
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    default='INFO',
    help='Set logging level (default: INFO)'
)
@click.pass_context
def cli(ctx: click.Context, config_dir: Path, log_level: str):
    """
    Email-Agent V4: Multi-account email processing CLI
    
    Process emails using AI classification and generate Obsidian notes.
    Supports multi-account processing with account-specific configuration.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Store config directory in context
    ctx.obj['config_dir'] = str(config_dir.resolve())
    ctx.obj['log_level'] = log_level.upper()
    ctx.obj['config_loader'] = None  # Lazy initialization
    
    # Initialize logging early
    try:
        log_overrides = {'level': log_level.upper()}
        init_logging(overrides=log_overrides)
    except Exception as e:
        click.echo(f"Warning: Could not initialize logging: {e}", err=True)


def _get_config_loader(ctx: click.Context) -> ConfigLoader:
    """
    Get or create ConfigLoader instance for the context.
    
    Args:
        ctx: Click context object
        
    Returns:
        ConfigLoader instance
    """
    if ctx.obj.get('config_loader') is None:
        config_dir = ctx.obj['config_dir']
        ctx.obj['config_loader'] = ConfigLoader(
            base_dir=config_dir,
            enable_validation=True
        )
    return ctx.obj['config_loader']


def _get_orchestrator(ctx: click.Context) -> MasterOrchestrator:
    """
    Get or create MasterOrchestrator instance for the context.
    
    Args:
        ctx: Click context object
        
    Returns:
        MasterOrchestrator instance
    """
    if ctx.obj.get('orchestrator') is None:
        config_dir = ctx.obj['config_dir']
        logger = logging.getLogger('email_agent')
        ctx.obj['orchestrator'] = MasterOrchestrator(
            config_base_dir=config_dir,
            logger=logger
        )
    return ctx.obj['orchestrator']


def _format_orchestration_result(result, use_formatted_output: bool = True) -> None:
    """
    Format and display orchestration results.
    
    Args:
        result: OrchestrationResult from MasterOrchestrator
        use_formatted_output: Whether to use DryRunOutput formatting
    """
    if use_formatted_output:
        try:
            output = DryRunOutput()
            output.header("Processing Summary", level=1)
            output.info(f"Total accounts: {result.total_accounts}")
            output.detail("Successful", result.successful_accounts)
            output.detail("Failed", result.failed_accounts)
            output.detail("Total time", f"{result.total_time:.2f}s")
            
            if result.failed_accounts > 0:
                output.warning("Some accounts failed processing")
                for account_id, (success, error) in result.account_results.items():
                    if not success:
                        output.error(f"{account_id}: {error}")
            else:
                output.success("All accounts processed successfully")
        except Exception:
            # Fallback to plain output if DryRunOutput fails
            _format_orchestration_result(result, use_formatted_output=False)
    else:
        # Plain output
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


@cli.command()
@click.option(
    '--account',
    type=str,
    help='Process a specific account by name. Mutually exclusive with --all.'
)
@click.option(
    '--all',
    'all_accounts',
    is_flag=True,
    default=False,
    help='Process all available accounts. Mutually exclusive with --account.'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Run in preview mode (no side effects, no file writes, no IMAP flag changes)'
)
@click.option(
    '--uid',
    type=str,
    help='Target a specific email by UID. If not provided, processes emails according to configured query. (Note: UID processing requires account to be specified)'
)
@click.option(
    '--force-reprocess',
    is_flag=True,
    default=False,
    help='Ignore existing processed_tag and reprocess emails even if already marked as processed.'
)
@click.option(
    '--max-emails',
    type=int,
    help='Maximum number of emails to process (overrides config max_emails_per_run). Useful for testing with a limited number of emails.'
)
@click.pass_context
def process(
    ctx: click.Context,
    account: Optional[str],
    all_accounts: bool,
    dry_run: bool,
    uid: Optional[str],
    force_reprocess: bool,
    max_emails: Optional[int]
):
    """
    Main command for email processing.
    
    Processes emails using AI classification and generates Obsidian notes.
    Supports multi-account processing with account-specific configuration.
    
    Examples:
        python main.py process --account work              # Process 'work' account
        python main.py process --all                       # Process all accounts
        python main.py process --account work --dry-run    # Preview processing
        python main.py process --account work --uid 12345  # Process specific email
        python main.py process --account work --force-reprocess  # Reprocess all emails
    """
    # Validate account selection
    if account and all_accounts:
        click.echo("Error: --account and --all are mutually exclusive. Use only one.", err=True)
        sys.exit(1)
    
    if not account and not all_accounts:
        click.echo("Error: Must specify either --account <name> or --all to process accounts.", err=True)
        click.echo("Usage: python main.py process --account <name> OR python main.py process --all", err=True)
        sys.exit(1)
    
    # Validate UID if provided
    if uid is not None:
        if not uid.strip():
            click.echo("Error: UID cannot be empty", err=True)
            sys.exit(1)
        if len(uid.strip()) > 100:
            click.echo("Error: UID is too long (max 100 characters)", err=True)
            sys.exit(1)
        if all_accounts:
            click.echo("Error: --uid cannot be used with --all. Specify a single account with --account.", err=True)
            sys.exit(1)
    
    # Build argv for MasterOrchestrator
    argv = []
    if account:
        argv.extend(['--account', account])
    elif all_accounts:
        argv.append('--all-accounts')
    
    if dry_run:
        argv.append('--dry-run')
    
    # Note: UID, force_reprocess, and max_emails are not yet supported by MasterOrchestrator
    # These will need to be added to AccountProcessor or passed through somehow
    # For now, we'll log a warning if they're used
    if uid or force_reprocess or max_emails:
        click.echo("Warning: --uid, --force-reprocess, and --max-emails options are not yet fully supported in V4.", err=True)
        click.echo("These features will be added in a future update.", err=True)
        # TODO: Implement these features in AccountProcessor
    
    try:
        # Get orchestrator from context
        orchestrator = _get_orchestrator(ctx)
        
        # Run orchestration
        result = orchestrator.run(argv)
        
        # Format and display results
        _format_orchestration_result(result, use_formatted_output=True)
        
        # Exit with error code if any failures
        if result.failed_accounts > 0:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error during processing: {e}", err=True)
        logger = logging.getLogger('email_agent')
        logger.error(f"Processing failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--account',
    type=str,
    help='Account name for cleanup operation. If not specified, uses default account.'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Preview which flags would be removed without actually removing them.'
)
@click.pass_context
def cleanup_flags(ctx: click.Context, account: Optional[str], dry_run: bool):
    """
    Maintenance command to clean up application-specific IMAP flags.
    
    This command removes only application-specific flags (as defined in configuration)
    from emails in the IMAP server. Use this command if you need to reset the
    processing state or clean up flags.
    
    WARNING: This will remove application-specific flags from emails, which may
    cause them to be reprocessed on the next run. This action cannot be undone.
    
    This command requires explicit confirmation before execution (security requirement).
    """
    # TODO: Migrate cleanup_flags module to use V4 ConfigLoader instead of settings facade
    click.echo("Error: cleanup-flags command is not yet fully migrated to V4.", err=True)
    click.echo("This command will be available in a future update.", err=True)
    click.echo("For now, please use the V3 CLI: python main.py cleanup-flags", err=True)
    sys.exit(1)
    # Note: Once cleanup_flags.py is migrated to V4, implement here


@cli.command()
@click.option(
    '--account',
    type=str,
    required=True,
    help='Account name to process backfill for (required)'
)
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
@click.pass_context
def backfill(
    ctx: click.Context,
    account: str,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    force_reprocess: bool,
    dry_run: bool,
    max_emails: Optional[int]
):
    """
    Process all historical emails with the classification system.
    
    This command processes all emails in the target mailbox, regardless of their
    current flag status. Useful for backfilling historical emails.
    
    Supports date range filtering, progress tracking, and API throttling.
    
    Examples:
        python main.py backfill --account work
        python main.py backfill --account work --start-date 2024-01-01
        python main.py backfill --account work --start-date 2024-01-01 --end-date 2024-12-31
        python main.py backfill --account work --max-emails 100
        python main.py backfill --account work --dry-run
    """
    # TODO: Migrate backfill module to use V4 AccountProcessor instead of Pipeline
    click.echo("Error: backfill command is not yet fully migrated to V4.", err=True)
    click.echo("This command will be available in a future update.", err=True)
    click.echo("For now, please use the V3 CLI: python main.py backfill", err=True)
    sys.exit(1)
    # Note: Once backfill.py is migrated to V4, implement here using AccountProcessor


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
    
    Examples:
        python main.py show-config --account work
        python main.py show-config --account work --format json
        python main.py show-config --account work --format json --with-sources
    """
    try:
        from src.config_display import AnnotatedConfigMerger, ConfigFormatter
        from src.config_loader import ConfigurationError
        
        # Get config loader from context
        config_loader = _get_config_loader(ctx)
        
        # Load global and account configs separately for annotation
        global_config = config_loader.load_global_config()
        account_config = config_loader.load_account_config(account)
        
        # Create annotated merged config if highlighting is enabled
        if not no_highlight:
            merger = AnnotatedConfigMerger()
            annotated_config = merger.merge_with_annotations(global_config, account_config)
        else:
            # Just use plain merged config
            annotated_config = config_loader.load_merged_config(account)
        
        # Format and display
        formatter = ConfigFormatter()
        if format.lower() == 'json':
            output = formatter.format_json(
                annotated_config,
                show_sources=not no_highlight,
                include_source_fields=with_sources
            )
        else:
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
        click.echo(f"Error displaying configuration: {e}", err=True)
        logger = logging.getLogger('email_agent')
        logger.error(f"show-config failed: {e}", exc_info=True)
        sys.exit(1)
