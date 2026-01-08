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
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

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
    Email-Agent V3: Headless IMAP AI Triage CLI
    
    Process emails using AI classification and generate Obsidian notes.
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
@click.pass_context
def process(ctx: click.Context, uid: Optional[str], force_reprocess: bool, dry_run: bool):
    """
    Main command for bulk or single email processing.
    
    Processes emails using AI classification and generates Obsidian notes.
    By default, processes unprocessed emails according to the configured IMAP query.
    
    Examples:
        python main.py process                    # Process unprocessed emails
        python main.py process --uid 12345       # Process specific email
        python main.py process --force-reprocess # Reprocess all emails
        python main.py process --dry-run         # Test without side effects
    """
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
    
    # TODO: This will be connected to orchestrator in Task 14
    if dry_run:
        click.echo("[DRY RUN MODE] No files will be written or flags set")
    
    click.echo("Process command called with:")
    click.echo(f"  UID: {uid if uid else '(all unprocessed)'}")
    click.echo(f"  Force reprocess: {force_reprocess}")
    click.echo(f"  Dry run: {dry_run}")
    click.echo("\n[INFO] Processing logic will be implemented in Task 14 (orchestrator integration)")
    
    # Return options for programmatic use
    return options


@cli.command()
@click.pass_context
def cleanup_flags(ctx: click.Context):
    """
    Maintenance command to clean up IMAP processed flags.
    
    This command removes the processed_tag from emails in the IMAP server.
    Use this command if you need to reset the processing state.
    
    WARNING: This will mark all emails as unprocessed, which may cause
    them to be reprocessed on the next run.
    
    This command requires explicit confirmation before execution.
    """
    # Initialize config (lazy loading)
    _ensure_config_initialized(ctx)
    
    # Create structured options object
    options = CleanupFlagsOptions(
        config_path=ctx.obj['config_path'],
        env_path=ctx.obj['env_path']
    )
    
    # Store in context for potential use by other functions
    ctx.obj['cleanup_options'] = options
    
    # Display warning message
    click.echo("\n" + "=" * 70, err=True)
    click.echo("WARNING: This command will remove processed flags from ALL emails", err=True)
    click.echo("in your IMAP mailbox. This action cannot be undone.", err=True)
    click.echo("=" * 70 + "\n", err=True)
    
    # Get processed tag name from settings
    try:
        processed_tag = settings.get_imap_processed_tag()
        click.echo(f"This will remove the '{processed_tag}' flag from all emails.")
    except Exception:
        click.echo("This will remove the processed flag from all emails.")
    
    click.echo("\nThis may cause emails to be reprocessed on the next run.")
    
    # Mandatory confirmation prompt (PDD requirement)
    confirmation = click.prompt(
        "\nType 'yes' to confirm and proceed, or anything else to cancel",
        type=str,
        default='no'
    )
    
    if confirmation.lower().strip() != 'yes':
        click.echo("\nOperation cancelled. No flags were modified.", err=True)
        sys.exit(0)
    
    # Confirmation received - proceed with cleanup
    # TODO: This will be connected to IMAP client in Task 3
    click.echo("\n[INFO] Cleanup logic will be implemented in Task 3 (IMAP client)")
    click.echo("Confirmation received. Ready to proceed with flag cleanup.")
    
    # Return options for programmatic use
    return options


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


if __name__ == '__main__':
    cli()
