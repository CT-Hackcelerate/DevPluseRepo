"""Connectors for JIRA and DevOps tools. Each returns plain dict payloads
ready to feed into the optimization pipeline."""

from .base import Connector
from .jira import JiraConnector
from .github import GitHubConnector
from .azure_devops import AzureDevOpsConnector
from .gitlab import GitLabConnector
from .jenkins import JenkinsConnector

__all__ = [
    "Connector",
    "JiraConnector",
    "GitHubConnector",
    "AzureDevOpsConnector",
    "GitLabConnector",
    "JenkinsConnector",
]
