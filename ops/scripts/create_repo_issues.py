#!/usr/bin/env python3
"""
Helper script to automate creating the 13 audited issues from .github/ISSUE_TEMPLATES
in the live GitHub repository using the GitHub CLI (gh).
"""
import argparse
import os
import re
import subprocess
import sys

# Force UTF-8 terminal encoding on Windows to prevent Unicode/CP949 errors
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def parse_issue_file(filepath):
    """
    Parses a markdown issue file to extract:
    - Title (first H1)
    - Labels (from **Labels**: line)
    - Body (the whole file content)
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return None

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    if not lines:
        return None

    title = ""
    labels = []

    # 1. Parse Title
    title_match = re.match(r'^#\s*(.+)$', lines[0].strip())
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = os.path.basename(filepath).replace('.md', '').replace('-', ' ').title()

    # 2. Parse Labels
    for line in lines:
        match = re.search(r'\*\*Labels\*\*:\s*(.+)', line)
        if match:
            labels_raw = match.group(1)
            # Strip backticks and split by comma
            labels = [l.strip().replace('`', '') for l in labels_raw.split(',')]
            break

    body = content

    return {
        "title": title,
        "labels": labels,
        "body": body,
        "filename": os.path.basename(filepath)
    }

def create_github_issue(issue_data, dry_run=False):
    """
    Creates an issue in the repository using the gh CLI.
    """
    title = issue_data["title"]
    labels = issue_data["labels"]
    body = issue_data["body"]

    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    if labels:
        cmd.extend(["--label", ",".join(labels)])

    print("\n==================================================")
    print(f"Processing: {issue_data['filename']}")
    print(f"Title:      {title}")
    print(f"Labels:     {', '.join(labels)}")
    print("==================================================")

    if dry_run:
        print("[DRY-RUN] Command that would be run:")
        print(" ".join(cmd))
        return True

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        print(f"Successfully created issue: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("Error: The 'gh' CLI was not found. Please install the GitHub CLI and login.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error executing 'gh issue create':\n{e.stderr}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Automates creating audit issues in the GitHub repository.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Process all issue templates")
    group.add_argument("--file", type=str, help="Process a specific markdown file")

    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing them")
    args = parser.parse_args()

    # Determine templates directory path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    templates_dir = os.path.join(workspace_root, ".github", "ISSUE_TEMPLATES")

    if not os.path.exists(templates_dir):
        print(f"Error: Templates directory not found at {templates_dir}", file=sys.stderr)
        sys.exit(1)

    # Gather files
    files_to_process = []
    if args.file:
        filepath = args.file
        if not os.path.isabs(filepath):
            if os.path.exists(os.path.join(templates_dir, filepath)):
                filepath = os.path.join(templates_dir, filepath)
            elif os.path.exists(os.path.join(workspace_root, filepath)):
                filepath = os.path.join(workspace_root, filepath)
        files_to_process.append(filepath)
    elif args.all:
        for filename in sorted(os.listdir(templates_dir)):
            if filename.endswith(".md") and filename != "README.md":
                files_to_process.append(os.path.join(templates_dir, filename))

    if not files_to_process:
        print("No markdown files found to process.", file=sys.stderr)
        sys.exit(0)

    # Check for 'gh' CLI presence if not a dry-run
    if not args.dry_run:
        try:
            subprocess.run(["gh", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("WARNING: GitHub CLI 'gh' is not installed or not in PATH.", file=sys.stderr)
            print("Proceeding with dry-run mode instead...", file=sys.stderr)
            args.dry_run = True

    success_count = 0
    for filepath in files_to_process:
        issue_data = parse_issue_file(filepath)
        if issue_data:
            if create_github_issue(issue_data, dry_run=args.dry_run):
                success_count += 1

    mode_str = "parsed (dry-run)" if args.dry_run else "created"
    print(f"\nDone! Processed {success_count}/{len(files_to_process)} issues successfully ({mode_str}).")

if __name__ == "__main__":
    main()
