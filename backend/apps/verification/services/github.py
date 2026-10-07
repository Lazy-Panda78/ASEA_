import os
import re
from urllib.parse import urlparse
import requests

class GitHubIngestionError(Exception):
    """Custom exception raised during GitHub PR/Diff ingestion failures."""
    pass


class GitHubIngestionService:
    """
    Service handling parsing of GitHub repository URLs and fetching
    pull request details, changed files, and patch diffs via GitHub REST API.
    """
    GITHUB_API_BASE = "https://api.github.com"

    @staticmethod
    def parse_github_url(repo_url: str) -> tuple[str, str]:
        """
        Parses a GitHub repository URL to extract owner and repository name.
        Example: https://github.com/owner/repository -> ('owner', 'repository')
        """
        if not repo_url:
            raise GitHubIngestionError("Repository URL is required.")
        
        parsed = urlparse(repo_url.strip())
        if parsed.netloc not in ("github.com", "www.github.com"):
            raise GitHubIngestionError("Only GitHub repository URLs (github.com) are supported.")
        
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) < 2:
            raise GitHubIngestionError("Invalid GitHub repository URL format. Expected https://github.com/owner/repository.")
        
        owner = path_parts[0]
        repo = path_parts[1].removesuffix(".git")
        return owner, repo

    @classmethod
    def ingest_pull_request(cls, repo_url: str, pr_number: int) -> dict:
        """
        Fetches PR details and changed files diff from GitHub REST API.
        Returns a normalized dictionary structure of PR and diff metadata.
        """
        owner, repo = cls.parse_github_url(repo_url)
        
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise GitHubIngestionError("prNumber must be a positive integer.")

        token = os.environ.get("GITHUB_TOKEN", "").strip()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ASEA-Verification-Agent"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # 1. Fetch Pull Request details
        pr_endpoint = f"{cls.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            pr_response = requests.get(pr_endpoint, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise GitHubIngestionError(f"Failed to connect to GitHub API: {str(exc)}")

        if pr_response.status_code == 404:
            raise GitHubIngestionError(f"Pull request #{pr_number} or repository '{owner}/{repo}' not found on GitHub.")
        elif pr_response.status_code != 200:
            raise GitHubIngestionError(f"GitHub API error ({pr_response.status_code}): {pr_response.text}")

        pr_data = pr_response.json()

        # 2. Fetch Changed Files & Patch Diffs
        files_endpoint = f"{cls.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        try:
            files_response = requests.get(files_endpoint, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise GitHubIngestionError(f"Failed to fetch changed files from GitHub API: {str(exc)}")

        if files_response.status_code != 200:
            raise GitHubIngestionError(f"GitHub API error fetching files ({files_response.status_code}): {files_response.text}")

        files_data = files_response.json()

        # 3. Normalize files data
        normalized_files = []
        for file_item in files_data:
            normalized_files.append({
                "filename": file_item.get("filename"),
                "status": file_item.get("status"),
                "additions": file_item.get("additions", 0),
                "deletions": file_item.get("deletions", 0),
                "changes": file_item.get("changes", 0),
                "patch": file_item.get("patch", ""),
                "raw_url": file_item.get("raw_url", "")
            })

        # 4. Construct normalized ingestion payload
        normalized_ingestion = {
            "provider": "github",
            "repository": {
                "owner": owner,
                "name": repo,
                "url": repo_url,
            },
            "pr": {
                "number": pr_number,
                "title": pr_data.get("title", ""),
                "description": pr_data.get("body") or "",
                "author": pr_data.get("user", {}).get("login", "") if pr_data.get("user") else "",
                "pr_url": pr_data.get("html_url", ""),
                "state": pr_data.get("state", ""),
                "base_branch": pr_data.get("base", {}).get("ref", "") if pr_data.get("base") else "",
                "head_branch": pr_data.get("head", {}).get("ref", "") if pr_data.get("head") else "",
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files_count": pr_data.get("changed_files", len(normalized_files)),
            },
            "files": normalized_files
        }

        return normalized_ingestion
