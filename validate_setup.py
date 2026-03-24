#!/usr/bin/env python3
"""
Validation script to verify email agent setup.
Run this to check if all components are properly configured.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def check_imports():
    """Check if all required packages can be imported."""
    required_packages = [
        ("requests", "requests"),
        ("dotenv", "python-dotenv"),
        ("imapclient", "imapclient"),
        ("pyrogram", "pyrogram"),
        ("pydantic", "pydantic"),
        ("pydantic_settings", "pydantic-settings"),
        ("apscheduler", "APScheduler"),
        ("structlog", "structlog"),
        ("aiosqlite", "aiosqlite"),
        ("filelock", "filelock"),
    ]

    print("Checking package imports...")
    all_ok = True

    for module, package in required_packages:
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError as e:
            print(f"  ✗ {package} (ImportError: {e})")
            all_ok = False

    return all_ok


def check_config():
    """Check if configuration can be loaded."""
    print("\nChecking configuration...")

    try:
        from config.settings import Settings
        settings = Settings()
        print("  ✓ Settings loaded successfully")
        print(f"    - Fetch interval: {settings.FETCH_INTERVAL_MINUTES} minutes")
        print(f"    - Skip promotions: {settings.SKIP_PROMOTIONS}")
        print(f"    - Peek mode: {settings.PEEK_MODE}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to load settings: {e}")
        return False


def check_modules():
    """Check if all modules can be imported."""
    print("\nChecking module imports...")

    modules = [
        "config.settings",
        "core.email_service",
        "core.llm_service",
        "core.telegram_service",
        "core.storage",
        "processors.email_classifier",
        "processors.summarizer",
        "scheduler.job_manager",
        "utils.logging_config",
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError as e:
            print(f"  ✗ {module} ({e})")
            all_ok = False

    return all_ok


def check_directories(settings):
    """Check if required directories exist or can be created."""
    print("\nChecking directories...")

    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Data directory: {settings.DATA_DIR}")

        settings.EMAILS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Emails directory: {settings.EMAILS_DIR}")

        return True
    except Exception as e:
        print(f"  ✗ Directory check failed: {e}")
        return False


def check_env_variables():
    """Check if required environment variables are set."""
    print("\nChecking environment variables...")

    required_vars = [
        "GMAIL_EMAIL",
        "GMAIL_PASSWORD",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]

    all_ok = True
    for var in required_vars:
        import os
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            masked = "*****" + value[-4:] if len(value) > 4 else "*****"
            print(f"  ✓ {var}: {masked}")
        else:
            print(f"  ✗ {var}: NOT SET")
            all_ok = False

    return all_ok


def main():
    """Run all validation checks."""
    print("=" * 50)
    print("Email Agent Setup Validation")
    print("=" * 50)

    checks = [
        ("Package Imports", check_imports),
        ("Environment Variables", check_env_variables),
        ("Modules", check_modules),
        ("Configuration", check_config),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} check failed with exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    all_passed = all(result for _, result in results)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    if all_passed:
        print("\n✓ All checks passed! Setup is ready.")
        print("\nNext steps:")
        print("  1. Run: python main.py")
        print("  2. Send /start to your Telegram bot")
        print("  3. Verify email processing works")
        return 0
    else:
        print("\n✗ Some checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
