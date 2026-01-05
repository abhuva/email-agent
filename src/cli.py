import argparse
import sys
from src.config import ConfigManager, ConfigError

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
        print("Configuration loaded and validated successfully.")
        # Placeholder for further CLI logic
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
