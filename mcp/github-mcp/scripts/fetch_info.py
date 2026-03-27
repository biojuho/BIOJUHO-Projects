import requests
import json

import os

import os

# Load .env from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, '.env')

if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                if not os.environ.get(key):  # Don't overwrite existing env vars
                    os.environ[key] = value

# GitHub PAT
token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "YOUR_GITHUB_PAT_HERE")

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

def get_repos():
    try:
        # Get user repos
        response = requests.get("https://api.github.com/user/repos?sort=updated&per_page=5", headers=headers)
        if response.status_code == 200:
            repos = response.json()
            print(f"[FOUND] Found {len(repos)} recent repositories:")
            for repo in repos:
                print(f"- [{repo['name']}]({repo['html_url']})")
                print(f"  - Description: {repo['description']}")
                print(f"  - Stars: {repo['stargazers_count']} | Updated: {repo['updated_at']}")
                print("")
        else:
            print(f"[ERROR] Error fetching repos: {response.status_code}")
            print(response.text)

        # Check specifically for BIOJUHO-Projects
        print("-" * 20)
        print("[CHECK] Checking 'BIOJUHO-Projects'...")
        # Since we don't know the exact owner username (implied owner of token), we search user repos or try specific url if we knew user.
        # But listing above should cover it if it was recently listed.
        
    except Exception as e:
        print(f"[ERROR] Exception: {e}")

if __name__ == "__main__":
    get_repos()
