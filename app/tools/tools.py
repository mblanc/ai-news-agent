import os

import requests
from google.adk.tools.function_tool import FunctionTool, ToolContext
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from markdownify import markdownify as md

# from google.adk.tools.computer_use.base_computer import BaseComputer
# from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset

playwright_mcp_tool = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=[
                "-y",  # Argument for npx to auto-confirm install
                "@playwright/mcp@latest",
                "--headless",
            ],
        ),
        timeout=60,
    ),
)

reddit_mcp_tool = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uvx",
            args=["mcp-server-reddit"],
            # Optional: Add environment variables if needed by the MCP server,
            # e.g., credentials if mcp-reddit required them.
            # env=os.environ.copy()
        ),
        timeout=60,
    ),
)

# computer_use_toolset = ComputerUseToolset(
#     computer=BaseComputer()
# )

def get_news_from_url(tool_context: ToolContext, url: str, state_key: str):
    try:
        #tool_context.actions.skip_summarization = True
        html = requests.get(url).text

        # Extract main content
        # text_content = trafilatura.extract(html, include_links=True, include_comments=False, include_tables=True)
        markdown = md(html)
        # Convert to Markdown
        # markdown = html2text.html2text(text_content)
        # tool_context.state[state_key] = markdown
        return markdown
    except Exception as e:
        print(f"Error getting news from {url}: {e}")
        return f"Error getting news from {url}: {e}"


get_news_from_url_tool = FunctionTool(get_news_from_url)


def get_community_tweets(tool_context: ToolContext, community_id: str, state_key: str):
    # tool_context.actions.skip_summarization = True
    api_key = os.getenv("TWITTERAPI_API_KEY")  # Replace with your actual API key
    url = f"https://api.twitterapi.io/twitter/community/tweets?community_id={community_id}"

    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
    }
    print("="*42)
    print(f"Getting community tweets for {url}")
    print(f"Headers: {headers}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        community_info = response.json()
        return community_info

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


get_community_tweets_tool = FunctionTool(get_community_tweets)