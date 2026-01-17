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


# Commands will be added in subsequent subtasks
# This file establishes the core structure
