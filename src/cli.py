import argparse
import sys
from src.config import ConfigManager, ConfigError
from src.logger import LoggerFactory
from src.analytics import generate_analytics
import atexit

def main():
    parser = argparse.ArgumentParser(
        description="Email-Agent: Headless IMAP AI Triage CLI"
    )
    parser.add_argument('--config', default='config/config.yaml', help='Path to YAML configuration file')
    parser.add_argument('--env', default='config/.env', help='Path to .env secrets file')
    parser.add_argument('--version', action='version', version='email-agent 0.1.0')
    args = parser.parse_args()

    try:
        config = ConfigManager(args.config, args.env)
        logger = LoggerFactory.create_logger(
            level=config.log_level,
            log_file=config.log_file,
            console=True
        )
        logger.info("Configuration loaded and validated successfully.")

        atexit.register(lambda: generate_analytics(config.log_file, config.analytics_file))
        logger.info("Logging system fully initialized. Ready for further operations.")
        # Main pipeline would continue from here (IMAP, OpenRouter, etc)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
