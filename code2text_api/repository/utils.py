"""
Utility functions for repository analysis and GitHub API interaction.
"""

import os
import requests
import logging
import git
from django.conf import settings
from collections import Counter

logger = logging.getLogger(__name__)

def analyze_repository(repo_dir):
    """
    Analyze a repository directory and return its statistics.
    
    Args:
        repo_dir: Path to the repository directory.
    
    Returns:
        dict: Repository statistics including languages, file count, and size.
    """
    result = {
        'languages': [],
        'file_count': 0,
        'size': 0,
    }
    
    try:
        # Get languages
        result['languages'] = detect_languages(repo_dir)
        
        # Count files and total size
        file_count = 0
        total_size = 0
        
        for root, _, files in os.walk(repo_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path) and not is_git_file(file_path):
                    file_count += 1
                    total_size += os.path.getsize(file_path)
        
        result['file_count'] = file_count
        result['size'] = total_size
        
        return result
    
    except Exception as e:
        logger.error(f"Error analyzing repository: {str(e)}")
        raise


def detect_languages(repo_dir):
    """
    Detect programming languages used in a repository.
    
    Args:
        repo_dir: Path to the repository directory.
    
    Returns:
        list: List of programming languages used in the repository.
    """
    extension_to_language = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript (React)',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript (React)',
        '.html': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.sass': 'Sass',
        '.java': 'Java',
        '.kt': 'Kotlin',
        '.c': 'C',
        '.cpp': 'C++',
        '.cs': 'C#',
        '.php': 'PHP',
        '.rb': 'Ruby',
        '.go': 'Go',
        '.rs': 'Rust',
        '.swift': 'Swift',
        '.m': 'Objective-C',
        '.h': 'C/C++ Header',
        '.sh': 'Shell',
        '.json': 'JSON',
        '.xml': 'XML',
        '.yml': 'YAML',
        '.yaml': 'YAML',
        '.md': 'Markdown',
    }
    
    extensions = []
    
    for root, _, files in os.walk(repo_dir):
        if '.git' in root:
            continue
            
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in extension_to_language:
                extensions.append(ext)
    
    # Count extensions
    extension_counts = Counter(extensions)
    
    # Convert to languages
    languages = []
    for ext, count in extension_counts.most_common(10):
        if ext in extension_to_language:
            languages.append({
                'name': extension_to_language[ext],
                'count': count
            })
    
    return languages


def is_git_file(file_path):
    """
    Check if a file is a Git file.
    
    Args:
        file_path: Path to the file.
    
    Returns:
        bool: True if the file is a Git file, False otherwise.
    """
    return '.git' in file_path


def get_commit_hash(repo_dir):
    """
    Get the latest commit hash of a Git repository.
    
    Args:
        repo_dir: Path to the repository directory.
    
    Returns:
        str: Latest commit hash.
    """
    try:
        repo = git.Repo(repo_dir)
        return str(repo.head.commit)
    except Exception as e:
        logger.error(f"Error getting commit hash: {str(e)}")
        return None


def get_github_issues(github_url):
    """
    Get GitHub issues for a repository.
    
    Args:
        github_url: GitHub repository URL.
    
    Returns:
        list: List of GitHub issues.
    """
    # Extract owner and repo from GitHub URL
    parts = github_url.strip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL")
    
    owner = parts[-2]
    repo = parts[-1]
    if repo.endswith('.git'):
        repo = repo[:-4]
    
    # GitHub API URL
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    
    # Set headers with token if available
    headers = {}
    if settings.GITHUB_API_TOKEN:
        headers['Authorization'] = f"token {settings.GITHUB_API_TOKEN}"
    
    # Make API request
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"GitHub API error: {response.status_code} - {response.text}")
        raise Exception(f"GitHub API error: {response.status_code}")
    
    # Parse response
    issues = response.json()
    
    # Filter and transform issues
    result = []
    for issue in issues:
        # Skip pull requests
        if 'pull_request' in issue:
            continue
        
        result.append({
            'id': issue['id'],
            'number': issue['number'],
            'title': issue['title'],
            'state': issue['state'],
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'html_url': issue['html_url'],
            'user': {
                'login': issue['user']['login'],
                'avatar_url': issue['user']['avatar_url'],
                'html_url': issue['user']['html_url'],
            },
            'labels': [label['name'] for label in issue.get('labels', [])],
            'comments': issue.get('comments', 0),
        })
    
    return result


def get_github_commits(github_url):
    """
    Get GitHub commits for a repository.
    
    Args:
        github_url: GitHub repository URL.
    
    Returns:
        list: List of GitHub commits.
    """
    # Extract owner and repo from GitHub URL
    parts = github_url.strip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL")
    
    owner = parts[-2]
    repo = parts[-1]
    if repo.endswith('.git'):
        repo = repo[:-4]
    
    # GitHub API URL
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    # Set headers with token if available
    headers = {}
    if settings.GITHUB_API_TOKEN:
        headers['Authorization'] = f"token {settings.GITHUB_API_TOKEN}"
    
    # Make API request
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"GitHub API error: {response.status_code} - {response.text}")
        raise Exception(f"GitHub API error: {response.status_code}")
    
    # Parse response
    commits = response.json()
    
    # Transform commits
    result = []
    for commit in commits:
        result.append({
            'sha': commit['sha'],
            'html_url': commit['html_url'],
            'commit': {
                'message': commit['commit']['message'],
                'author': {
                    'name': commit['commit']['author']['name'],
                    'email': commit['commit']['author']['email'],
                    'date': commit['commit']['author']['date'],
                },
            },
            'author': {
                'login': commit['author']['login'] if commit.get('author') else None,
                'avatar_url': commit['author']['avatar_url'] if commit.get('author') else None,
            } if commit.get('author') else None,
        })
    
    return result 