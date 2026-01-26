"""
V4 Command-line interface for the email agent.

This module implements the V4 CLI using Click.
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
import os
from typing import Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

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
    '--env-file',
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default='.env',
    help='Path to .env file containing secrets (default: .env)'
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    default='INFO',
    help='Set logging level (default: INFO)'
)
@click.pass_context
def cli(ctx: click.Context, config_dir: Path, env_file: Path, log_level: str):
    """
    Email-Agent V4: Multi-account email processing CLI
    
    Process emails using AI classification and generate Obsidian notes.
    Supports multi-account processing with account-specific configuration.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Load environment variables from .env file (if it exists)
    # This must happen before any components try to access os.environ
    env_path = env_file.resolve() if env_file.exists() else Path('.env')
    if env_path.exists():
        load_dotenv(env_path, override=False)  # Don't override existing env vars
    # Note: .env file is optional - if it doesn't exist, use system environment variables
    
    # Store config directory in context
    ctx.obj['config_dir'] = str(config_dir.resolve())
    ctx.obj['log_level'] = log_level.upper()
    ctx.obj['config_loader'] = None  # Lazy initialization
    
    # Initialize logging early
    try:
        log_overrides = {'level': log_level.upper()}
        init_logging(overrides=log_overrides)
        # Log that .env was loaded (after logging is initialized)
        logger = logging.getLogger('email_agent')
        if env_path.exists():
            logger.debug(f"Loaded environment variables from: {env_path}")
        else:
            logger.debug(f"Environment file not found: {env_path} (using system environment variables)")
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
@click.option(
    '--debug-prompt',
    is_flag=True,
    default=False,
    help='Write the formatted classification prompt to a debug file in logs/ directory. Useful for debugging prompt construction.'
)
@click.option(
    '--after',
    type=str,
    help='Only process emails sent/received after this date. Supports formats: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY, or natural language (e.g., "2 Feb 2022")'
)
@click.option(
    '--before',
    type=str,
    help='Only process emails sent/received before this date. Supports formats: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY, or natural language (e.g., "2 Feb 2022")'
)
@click.pass_context
def process(
    ctx: click.Context,
    account: Optional[str],
    all_accounts: bool,
    dry_run: bool,
    uid: Optional[str],
    force_reprocess: bool,
    max_emails: Optional[int],
    debug_prompt: bool,
    after: Optional[str],
    before: Optional[str]
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
        python main.py process --account work --after 02.02.2022  # Process emails after date
        python main.py process --account work --before 2022-12-31  # Process emails before date
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
    
    # Add processing options to argv for MasterOrchestrator
    if uid:
        argv.extend(['--uid', uid])
    if force_reprocess:
        argv.append('--force-reprocess')
    if max_emails:
        argv.extend(['--max-emails', str(max_emails)])
    if debug_prompt:
        argv.append('--debug-prompt')
    if after:
        argv.extend(['--after', after])
    if before:
        argv.extend(['--before', before])
    
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
    required=True,
    help='Account name for cleanup operation (required).'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Preview which flags would be removed without actually removing them.'
)
@click.pass_context
def cleanup_flags(ctx: click.Context, account: str, dry_run: bool):
    """
    Maintenance command to clean up application-specific IMAP flags.
    
    This command removes only application-specific flags (as defined in configuration)
    from emails in the IMAP server. Use this command if you need to reset the
    processing state or clean up flags.
    
    WARNING: This will remove application-specific flags from emails, which may
    cause them to be reprocessed on the next run. This action cannot be undone.
    
    This command requires explicit confirmation before execution (security requirement).
    
    Examples:
        python main.py cleanup-flags --account work
        python main.py cleanup-flags --account work --dry-run
    """
    try:
        from src.cleanup_flags import CleanupFlags, CleanupFlagsError
        from src.account_processor import create_imap_client_from_config
        from src.config_loader import ConfigurationError
        
        # Get config loader from context
        config_loader = _get_config_loader(ctx)
        
        # Load account configuration
        try:
            account_config = config_loader.load_merged_config(account)
        except (FileNotFoundError, ConfigurationError) as e:
            click.echo(f"Error: Failed to load configuration for account '{account}': {e}", err=True)
            sys.exit(1)
        
        # Get application flags from config
        imap_config = account_config.get('imap', {})
        application_flags = imap_config.get('application_flags', [])
        
        if not application_flags:
            click.echo("Warning: No application-specific flags configured for this account.", err=True)
            click.echo("Using default flags: AIProcessed, ObsidianNoteCreated, NoteCreationFailed", err=True)
            application_flags = ["AIProcessed", "ObsidianNoteCreated", "NoteCreationFailed"]
        
        flags_list = ', '.join(application_flags)
        
        # Display warning message
        click.echo("\n" + "=" * 70, err=True)
        click.echo("WARNING: This command will remove application-specific flags from emails", err=True)
        click.echo("in your IMAP mailbox. This action cannot be undone.", err=True)
        click.echo("=" * 70 + "\n", err=True)
        
        click.echo(f"Account: {account}")
        click.echo(f"Application-specific flags to remove: {flags_list}")
        click.echo("\nThis may cause emails to be reprocessed on the next run.")
        
        if dry_run:
            click.echo("\n[DRY RUN MODE] No flags will actually be removed.")
        
        # Mandatory confirmation prompt (security requirement)
        if not dry_run:
            confirmation = click.prompt(
                "\nType 'yes' to confirm and proceed, or anything else to cancel",
                type=str,
                default='no'
            )
            
            if confirmation.lower().strip() != 'yes':
                click.echo("\nOperation cancelled. No flags were modified.", err=True)
                sys.exit(0)
        
        # Create IMAP client from config
        imap_client = create_imap_client_from_config(account_config)
        
        # Create cleanup manager with V4 config
        cleanup = CleanupFlags(config=account_config, imap_client=imap_client)
        cleanup.connect()
        
        try:
            # Scan for flags
            click.echo("\nScanning emails for application-specific flags...")
            scan_results = cleanup.scan_flags(dry_run=dry_run)
            
            if not scan_results:
                click.echo("\nNo emails with application-specific flags found.")
                cleanup.disconnect()
                return
            
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
        
    except CleanupFlagsError as e:
        click.echo(f"\nError during cleanup operation: {e}", err=True)
        logger = logging.getLogger('email_agent')
        logger.error(f"Cleanup flags command failed: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nUnexpected error during cleanup operation: {e}", err=True)
        logger = logging.getLogger('email_agent')
        logger.error(f"Cleanup flags command failed: {e}", exc_info=True)
        sys.exit(1)


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
    # TODO: Migrate backfill module to use V4 AccountProcessor
    click.echo("Error: backfill command is not yet fully migrated to V4.", err=True)
    click.echo("This command will be available in a future update.", err=True)
    sys.exit(1)
    # Note: Once backfill.py is migrated to V4, implement here using AccountProcessor


@cli.command()
@click.option(
    '--account',
    type=str,
    required=True,
    help='Account name to scan UIDs for (required)'
)
@click.option(
    '--format',
    type=click.Choice(['simple', 'detailed'], case_sensitive=False),
    default='simple',
    help='Output format: simple (just max UID) or detailed (full statistics)'
)
@click.pass_context
def scan_uids(
    ctx: click.Context,
    account: str,
    format: str
):
    """
    Scan Obsidian vault for the highest UID in markdown frontmatter.
    
    This command scans all markdown files in the account-specific vault directory
    and finds the highest UID value stored in YAML frontmatter. This is useful
    for incremental processing - you can use the max UID to only process emails
    with higher UIDs.
    
    The account-specific vault directory is determined by converting the account_id
    to a subdirectory name (e.g., 'info.nica' -> 'info-nica').
    
    Examples:
        python main.py scan-uids --account work
        python main.py scan-uids --account work --format detailed
    """
    try:
        from src.vault_utils import get_max_uid_from_vault, scan_vault_stats
        from src.config_loader import ConfigurationError
        
        # Get config loader from context
        config_loader = _get_config_loader(ctx)
        
        # Load account configuration to get vault path
        try:
            account_config = config_loader.load_merged_config(account)
        except (FileNotFoundError, ConfigurationError) as e:
            click.echo(f"Error: Failed to load configuration for account '{account}': {e}", err=True)
            sys.exit(1)
        
        # Get vault path from config
        vault_path = account_config.get('paths', {}).get('obsidian_vault')
        if not vault_path:
            click.echo(f"Error: obsidian_vault not configured for account '{account}'", err=True)
            click.echo("Please configure paths.obsidian_vault in your account or global config.", err=True)
            sys.exit(1)
        
        # Scan vault
        if format.lower() == 'detailed':
            stats = scan_vault_stats(account, vault_path)
            click.echo(f"\nUID Statistics for account: {account}")
            click.echo("=" * 70)
            click.echo(f"Vault directory: {stats['account_subdir']}")
            click.echo(f"Total markdown files: {stats['total_files']}")
            click.echo(f"Files with UID: {stats['files_with_uid']}")
            if stats['max_uid'] is not None:
                click.echo(f"Maximum UID: {stats['max_uid']}")
                click.echo(f"Minimum UID: {stats['min_uid']}")
            else:
                click.echo("No UIDs found in vault")
            click.echo("=" * 70)
        else:
            # Simple format - just show max UID
            max_uid = get_max_uid_from_vault(account, vault_path)
            if max_uid is not None:
                click.echo(f"{max_uid}")
            else:
                click.echo("No UIDs found", err=True)
                sys.exit(1)
        
    except FileNotFoundError as e:
        click.echo(f"Error: Configuration file not found: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ConfigurationError as e:
        click.echo(f"Error: Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error scanning vault: {e}", err=True)
        logger = logging.getLogger('email_agent')
        logger.error(f"scan-uids failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--account',
    type=str,
    required=True,
    help='Account name to initiate OAuth authentication for (required)'
)
@click.pass_context
def auth(ctx: click.Context, account: str):
    """
    Initiate OAuth 2.0 authentication flow for specified account.
    
    This command starts an interactive OAuth 2.0 authentication flow for the
    specified account. It will:
    1. Load the account configuration
    2. Determine the OAuth provider (Google or Microsoft)
    3. Open your browser to authorize the application
    4. Exchange the authorization code for tokens
    5. Save tokens securely for future use
    
    The account must be configured with auth.method='oauth' and auth.provider
    set to either 'google' or 'microsoft' in the account configuration file.
    
    Required environment variables:
        - GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (for Google accounts)
        - MS_CLIENT_ID, MS_CLIENT_SECRET (for Microsoft accounts)
    
    Examples:
        python main.py auth --account work
        python main.py auth --account personal
    """
    try:
        from src.auth.oauth_flow import (
            OAuthFlow,
            OAuthError,
            OAuthPortError,
            OAuthTimeoutError,
        )
        from src.auth.providers import GoogleOAuthProvider, MicrosoftOAuthProvider
        from src.auth.providers.google import GoogleOAuthError
        from src.auth.providers.microsoft import MicrosoftOAuthError
        from src.auth.token_manager import TokenManager
        from src.config_loader import ConfigurationError
        
        # Get config loader from context
        config_loader = _get_config_loader(ctx)
        
        # Load account configuration
        try:
            account_config = config_loader.load_merged_config(account)
        except (FileNotFoundError, ConfigurationError) as e:
            click.echo(f"[ERROR] Failed to load configuration for account '{account}': {e}", err=True)
            click.echo(f"   Make sure the account configuration file exists: config/accounts/{account}.yaml", err=True)
            sys.exit(1)
        
        # Validate account name
        try:
            ConfigLoader._validate_account_name(account)
        except ValueError as e:
            click.echo(f"[ERROR] Invalid account name: {e}", err=True)
            sys.exit(1)
        
        # Check if auth method is OAuth
        auth_config = account_config.get('auth', {})
        auth_method = auth_config.get('method', 'password')
        
        if auth_method != 'oauth':
            click.echo(f"[ERROR] Account '{account}' is not configured for OAuth authentication.", err=True)
            click.echo(f"   Current auth method: '{auth_method}'", err=True)
            click.echo(f"   To use OAuth, set auth.method='oauth' in config/accounts/{account}.yaml", err=True)
            sys.exit(1)
        
        # Get provider from config
        provider_name = auth_config.get('provider')
        if not provider_name:
            click.echo(f"[ERROR] OAuth provider not specified for account '{account}'.", err=True)
            click.echo(f"   Set auth.provider='google' or auth.provider='microsoft' in config/accounts/{account}.yaml", err=True)
            sys.exit(1)
        
        provider_name = provider_name.lower().strip()
        if provider_name not in ('google', 'microsoft'):
            click.echo(f"[ERROR] Invalid OAuth provider '{provider_name}' for account '{account}'.", err=True)
            click.echo(f"   Supported providers: 'google', 'microsoft'", err=True)
            sys.exit(1)
        
        logger = logging.getLogger('email_agent')
        logger.info(f"Starting OAuth flow for account '{account}' with provider '{provider_name}'")
        
        # Check if tokens already exist
        token_manager = TokenManager()
        credentials_path = token_manager._get_token_path(account)
        if credentials_path.exists():
            click.echo(f"\n[WARNING] Tokens already exist for account '{account}'")
            click.echo(f"   Location: {credentials_path}")
            overwrite = click.prompt(
                "   Do you want to overwrite existing tokens? (yes/no)",
                type=str,
                default='no'
            )
            if overwrite.lower().strip() != 'yes':
                click.echo("   Operation cancelled. Existing tokens will be used.")
                sys.exit(0)
        
        # Initialize OAuth provider
        try:
            if provider_name == 'google':
                provider = GoogleOAuthProvider()
            else:  # microsoft
                provider = MicrosoftOAuthProvider()
        except (GoogleOAuthError, MicrosoftOAuthError) as e:
            click.echo(f"[ERROR] Failed to initialize {provider_name} OAuth provider: {e}", err=True)
            if provider_name == 'google':
                click.echo("   Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set in .env", err=True)
            else:
                click.echo("   Make sure MS_CLIENT_ID and MS_CLIENT_SECRET are set in .env", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"[ERROR] Unexpected error initializing OAuth provider: {e}", err=True)
            logger.error(f"OAuth provider initialization failed: {e}", exc_info=True)
            sys.exit(1)
        
        # Get email from config for login_hint (helps with account selection)
        imap_config = account_config.get('imap', {})
        email = imap_config.get('username', '')
        
        # Create OAuth flow
        try:
            flow = OAuthFlow(
                provider=provider,
                token_manager=token_manager,
                account_name=account,
                callback_port=8080,  # Default port, will auto-detect if unavailable
                login_hint=email if email and provider_name == 'microsoft' else None  # Microsoft supports login_hint
            )
        except Exception as e:
            click.echo(f"[ERROR] Failed to create OAuth flow: {e}", err=True)
            logger.error(f"OAuth flow creation failed: {e}", exc_info=True)
            sys.exit(1)
        
        # Show helpful message about which account to authenticate with
        # (email was already retrieved above for login_hint)
        click.echo(f"\n[AUTH] Starting OAuth authentication for account '{account}' ({provider_name})...")
        if email:
            click.echo(f"\n[IMPORTANT] When the browser opens, please sign in with:")
            click.echo(f"   Email: {email}")
            click.echo(f"   This is the account you want to access emails from.")
            click.echo(f"   Do NOT sign in with a different account, as the token will be tied to that account.\n")
        
        # Run OAuth flow
        try:
            token_info = flow.run(timeout=120)
            
            # Success message
            click.echo(f"\n[SUCCESS] Authentication successful for account '{account}'!")
            click.echo(f"   Tokens saved to: {credentials_path}")
            click.echo(f"   Provider: {provider_name}")
            logger.info(f"OAuth authentication completed successfully for account '{account}'")
            
        except OAuthPortError as e:
            click.echo(f"\n[ERROR] {e}", err=True)
            click.echo("   Please free a port (8080-8099) or close other applications using these ports.", err=True)
            flow.stop_local_server()  # Cleanup server if it was started
            sys.exit(1)
        except OAuthTimeoutError as e:
            click.echo(f"\n[ERROR] Authentication timed out: {e}", err=True)
            click.echo("   Please try again and complete the authorization in your browser.", err=True)
            flow.stop_local_server()  # Cleanup server if it was started
            sys.exit(1)
        except OAuthError as e:
            click.echo(f"\n[ERROR] Authentication failed: {e}", err=True)
            logger.error(f"OAuth flow failed for account '{account}': {e}", exc_info=True)
            flow.stop_local_server()  # Cleanup server if it was started
            sys.exit(1)
        except KeyboardInterrupt:
            click.echo("\n\n[WARNING] Authentication cancelled by user.", err=True)
            flow.stop_local_server()
            sys.exit(130)  # Standard exit code for Ctrl+C
        except Exception as e:
            click.echo(f"\n[ERROR] Unexpected error during authentication: {e}", err=True)
            logger.error(f"Unexpected error during OAuth flow: {e}", exc_info=True)
            flow.stop_local_server()  # Cleanup server if it was started
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"\n[ERROR] Unexpected error: {e}", err=True)
        logger = logging.getLogger('email_agent')
        logger.error(f"Auth command failed: {e}", exc_info=True)
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
