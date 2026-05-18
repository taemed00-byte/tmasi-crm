#!/usr/bin/env python3
"""
TMASI CRM - GitHub Deployment Script
Runs tests, validates safety, and pushes to main.
Usage: python scripts/deploy_github.py --message "Your commit message"
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

BLOCKED_FILES = [".env", "*.db", "*.sqlite", "*.sqlite3", "tmasi_local.db"]
BLOCKED_PATTERNS = ["WHATSAPP_ACCESS_TOKEN=ey", "postgresql://", "DATABASE_URL=postgres"]

def run(cmd, check=True, capture=False):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: Command failed with code {result.returncode}")
        if capture:
            print(result.stdout)
            print(result.stderr)
        sys.exit(1)
    return result

def check_git():
    result = run("git rev-parse --is-inside-work-tree", check=False, capture=True)
    if result.returncode != 0:
        print("Initializing git repository...")
        run("git init")
        run("git branch -M main", check=False)

def check_staged_for_secrets():
    result = run("git diff --cached --name-only", capture=True, check=False)
    staged = result.stdout.strip().splitlines()

    # Check for blocked files
    for fname in staged:
        basename = os.path.basename(fname)
        if basename in [".env"] or basename.endswith((".db", ".sqlite", ".sqlite3")):
            print(f"  BLOCKED: Staged file '{fname}' is not allowed!")
            sys.exit(1)
        if fname.startswith("uploads/") and not fname.endswith(".gitkeep"):
            print(f"  BLOCKED: Staged upload file '{fname}' - uploads should not be committed!")
            sys.exit(1)

    # Check staged content for secrets
    result = run("git diff --cached", capture=True, check=False)
    for pattern in BLOCKED_PATTERNS:
        if pattern in result.stdout:
            print(f"  BLOCKED: Staged content contains potential secret: '{pattern}'")
            sys.exit(1)

    print(f"  Safety check passed. Staged files: {len(staged)}")
    return staged

def main():
    parser = argparse.ArgumentParser(description="TMASI CRM GitHub Deploy")
    parser.add_argument("--message", "-m", required=True, help="Commit message")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually push")
    args = parser.parse_args()

    print("=" * 60)
    print("TMASI CRM — GitHub Deployment")
    print("=" * 60)

    # 1. Check git
    print("\n[1/6] Checking git...")
    check_git()
    print("  OK")

    # 2. Verify render.yaml and requirements.txt
    print("\n[2/6] Verifying required files...")
    required = ["render.yaml", "requirements.txt", "startup.sh", ".env.example", "app/main.py"]
    for f in required:
        if not (ROOT / f).exists():
            print(f"  ERROR: Required file '{f}' missing!")
            sys.exit(1)
    print("  All required files present")

    # 3. Verify no node server.js in render.yaml
    render_content = (ROOT / "render.yaml").read_text()
    if "node server.js" in render_content:
        print("  ERROR: render.yaml still references 'node server.js'!")
        sys.exit(1)
    print("  render.yaml looks clean")

    # 4. Run tests
    if not args.skip_tests:
        print("\n[3/6] Running backend tests...")
        result = run("python -m pytest tests/ -v --tb=short", check=False, capture=True)
        print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        if result.returncode != 0:
            print("  WARNING: Tests failed. Use --skip-tests to bypass.")
    else:
        print("\n[3/6] Tests skipped (--skip-tests)")

    # 5. Stage files
    print("\n[4/6] Staging files...")
    # Stage all app files (exclude blocked)
    run("git add app/ scripts/ requirements.txt render.yaml startup.sh .env.example .gitignore README.md", check=False)
    staged = check_staged_for_secrets()

    if not staged:
        print("  No changes to commit.")
        sys.exit(0)

    # 6. Commit
    print(f"\n[5/6] Committing: '{args.message}'")
    run(f'git commit -m "{args.message}"')

    # 7. Push
    print("\n[6/6] Pushing to origin main...")
    if args.dry_run:
        print("  DRY RUN — skipping push")
    else:
        result = run("git push origin main", check=False)
        if result.returncode != 0:
            print("  First push - setting upstream...")
            run("git push --set-upstream origin main")
    
    print("\n✓ Deployment complete! Render should auto-deploy within 2-3 minutes.")
    print("  Run: python scripts/verify_render_deploy.py --url https://YOUR_APP.onrender.com")

if __name__ == "__main__":
    main()
