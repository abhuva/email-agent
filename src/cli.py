"""
Command-line interface for the email agent.
Provides options for configuration, debug mode, and execution control.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
from src.config import ConfigManager, ConfigError, ConfigFormatError, ConfigPathError
from src.logger import LoggerFactory
from src.analytics import generate_analytics, write_analytics
from src.main_loop import run_email_processing_loop
import atexit


def parse_args(args=None):
    """
    Parse command-line arguments.
    
    Args:
        args: Optional list of arguments (for testing). If None, uses sys.argv.
    
    Returns:
        argparse.Namespace with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Email-Agent: Headless IMAP AI Triage CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Run with default config
  %(prog)s --config custom.yaml               # Use custom config file
  %(prog)s --limit 5                          # Process max 5 emails
  %(prog)s --debug --log-level DEBUG          # Enable debug mode
  %(prog)s --continuous                       # Run continuously (not single batch)
        """
    )
    
    # Config file options
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to YAML configuration file (default: config/config.yaml)'
    )
    parser.add_argument(
        '--env',
        type=str,
        default='.env',
        help='Path to .env secrets file (default: .env)'
    )
    
    # Debug and logging options
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode (equivalent to --log-level DEBUG)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    # Execution control options
    def positive_int(value):
        """Validate that limit is a positive integer"""
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError(f"Limit must be a positive number, got: {ivalue}")
        return ivalue
    
    parser.add_argument(
        '--limit',
        type=positive_int,
        default=None,
        help='Override max_emails_per_run from config (PDD AC 6)'
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuously instead of single batch (default: single batch)'
    )
    
    # Version
    parser.add_argument(
        '--version',
        action='version',
        version='email-agent 0.1.0'
    )
    
    return parser.parse_args(args)


def validate_args(args) -> None:
    """
    Validate parsed arguments.
    
    Args:
        args: Parsed arguments from parse_args()
    
    Raises:
        ValueError: If validation fails
    """
    # Validate config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        raise ValueError(f"Config file not found: {args.config}")
    
    # Validate env file exists (if specified and not default)
    if args.env != '.env':
        env_path = Path(args.env)
        if not env_path.exists():
            raise ValueError(f"Environment file not found: {args.env}")
    
    # Validate limit is positive if provided
    if args.limit is not None and args.limit <= 0:
        raise ValueError(f"Limit must be a positive number, got: {args.limit}")


def main(args=None) -> int:
    """
    Main CLI entry point.
    
    Args:
        args: Optional list of arguments (for testing). If None, uses sys.argv.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        # Parse arguments
        parsed_args = parse_args(args)
        
        # Validate arguments
        try:
            validate_args(parsed_args)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        
        # Determine log level (debug flag overrides log-level)
        log_level = 'DEBUG' if parsed_args.debug else parsed_args.log_level
        
        # Load configuration
        try:
            config = ConfigManager(parsed_args.config, parsed_args.env)
        except ConfigFormatError as e:
            print("Configuration format error:", file=sys.stderr)
            print(str(e), file=sys.stderr)
            print("\nPlease check your config.yaml file and ensure all V2 parameters", file=sys.stderr)
            print("have the correct data types and formats.", file=sys.stderr)
            return 1
        except ConfigPathError as e:
            print("Configuration path error:", file=sys.stderr)
            print(str(e), file=sys.stderr)
            print("\nPlease ensure all required directories and files exist.", file=sys.stderr)
            print("See config/config.yaml.example for the expected configuration structure.", file=sys.stderr)
            return 1
        except ConfigError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            return 1
        
        # Override log level from CLI if specified
        if parsed_args.debug or parsed_args.log_level != 'INFO':
            # Update config with CLI log level
            config.yaml['log_level'] = log_level
        
        # Ensure log directory exists
        log_file_path = Path(config.log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set root logger level so module loggers inherit it
        import logging
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Initialize logger
        logger = LoggerFactory.create_logger(
            level=log_level,
            log_file=config.log_file,
            console=True
        )
        logger.info("Email Agent CLI starting...")
        logger.info(f"Configuration loaded from: {parsed_args.config}")
        
        # Register analytics generation on exit
        atexit.register(
            lambda: generate_analytics(config.log_file, config.analytics_file)
        )
        
        # Determine execution mode
        single_run = not parsed_args.continuous
        max_emails = parsed_args.limit
        
        logger.info(f"Execution mode: {'single batch' if single_run else 'continuous'}")
        if max_emails:
            logger.info(f"Email limit override: {max_emails} (config default: {config.max_emails_per_run})")
        
        # Run main processing loop
        try:
            analytics = run_email_processing_loop(
                config=config,
                single_run=single_run,
                max_emails=max_emails
            )
            
            # Log summary
            summary = analytics.get('summary', {})
            logger.info("=" * 60)
            logger.info("Processing Summary:")
            logger.info(f"  Total processed: {summary.get('total', 0)}")
            logger.info(f"  Successfully processed: {summary.get('successfully_processed', 0)}")
            logger.info(f"  Failed: {summary.get('failed', 0)}")
            logger.info(f"  Success rate: {summary.get('success_rate', 0)}%")
            
            # V2: Display new metrics (Task 11)
            if analytics.get('notes_created', 0) > 0 or analytics.get('summaries_generated', 0) > 0 or analytics.get('note_creation_failures', 0) > 0:
                logger.info("  V2 Metrics:")
                logger.info(f"    Notes created: {analytics.get('notes_created', 0)}")
                logger.info(f"    Summaries generated: {analytics.get('summaries_generated', 0)}")
                logger.info(f"    Note creation failures: {analytics.get('note_creation_failures', 0)}")
            
            if summary.get('remaining_unprocessed', 0) > 0:
                logger.info(f"  Remaining unprocessed: {summary.get('remaining_unprocessed', 0)}")
            
            if summary.get('tags'):
                logger.info("  Tags applied:")
                for tag, count in summary['tags'].items():
                    logger.info(f"    {tag}: {count}")
            
            logger.info("=" * 60)
            
            # V2: Write analytics to file with new schema (Task 11)
            try:
                write_success = write_analytics(
                    analytics_file=config.analytics_file,
                    analytics_data=analytics,
                    include_v1_fields=True  # Include V1 fields for backward compatibility
                )
                if write_success:
                    logger.debug(f"Analytics written to {config.analytics_file}")
                else:
                    logger.warning(f"Failed to write analytics to {config.analytics_file}")
            except Exception as e:
                logger.error(f"Error writing analytics: {e}", exc_info=True)
                # Don't fail the entire run if analytics writing fails
            
            # Return success
            return 0
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user (Ctrl+C)")
            return 130  # Standard exit code for SIGINT
        except Exception as e:
            logger.error(f"Unexpected error during processing: {e}", exc_info=True)
            return 1
            
    except SystemExit:
        # Re-raise SystemExit (from --help, --version, etc.)
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
