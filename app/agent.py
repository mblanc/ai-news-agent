import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.planners import BuiltInPlanner
from google.genai.types import ThinkingConfig
from pydantic import BaseModel

from .tools.firestore_tools import write_to_firestore_tool
from .tools.tools import (
    get_community_tweets_tool,
    get_news_from_url_tool,
    playwright_mcp_tool,
    reddit_mcp_tool,
)

load_dotenv()


# see https://github.com/google/adk-python/issues/860
# Disable OpenTelemetry to avoid context management issues with incompatible GCP exporter
os.environ["OTEL_SDK_DISABLED"] = "true"

# Suppress OpenTelemetry warnings
logging.getLogger("opentelemetry").setLevel(logging.ERROR)


MODEL = "gemini-2.5-flash"

thinking_config = ThinkingConfig(
    include_thoughts=False,  # Ask the model to include its thoughts in the response
    thinking_budget=0,  # Limit the 'thinking' to 256 tokens (adjust as needed)
)

planner = BuiltInPlanner(thinking_config=thinking_config)


class Site(BaseModel):
    name: str
    url: str
    result_key: str


researcher_agents = []
fetch_sites = [
    Site(
        name="hacker_news",
        url="https://news.ycombinator.com/",
        result_key="hacker_news_result",
    ),
    Site(
        name="tech_crunch",
        url="https://techcrunch.com/category/artificial-intelligence/",
        result_key="tech_crunch_result",
    ),
    Site(
        name="the_verge",
        url="https://www.theverge.com/ai-artificial-intelligence",
        result_key="the_verge_result",
    ),
    Site(
        name="ai_weekly",
        url="https://aiweekly.co/issues.rss",
        result_key="ai_weekly_result",
    ),
    Site(
        name="artificial_intelligence_news",
        url="https://www.artificialintelligence-news.com/",
        result_key="artificial_intelligence_news_result",
    ),
    Site(
        name="venture_beat",
        url="https://venturebeat.com/",
        result_key="venture_beat_result",
    ),
    Site(
        name="technology_review",
        url="https://www.technologyreview.com/topic/artificial-intelligence/",
        result_key="technology_review_result",
    ),
    Site(
        name="sciencedaily",
        url="https://www.sciencedaily.com/news/computers_math/artificial_intelligence/",
        result_key="sciencedaily_result",
    ),
    Site(
        name="wired",
        url="https://www.wired.com/feed/tag/ai/latest/rss",
        result_key="wired_result",
    ),
    Site(
        name="forbes",
        url="https://www.forbes.com/ai/",
        result_key="forbes_result",
    ),
    Site(
        name="google_ai",
        url="https://blog.google/rss/",
        result_key="google_ai_result",
    ),
    Site(
        name="google_cloud_ai",
        url="https://cloud.google.com/blog/products/ai-machine-learning",
        result_key="google_cloud_ai_result",
    ),
    Site(
        name="deepmind",
        url="https://deepmind.google/discover/blog/",
        result_key="deepmind_result",
    ),
    Site(
        name="google_developers_blog",
        url="https://developers.googleblog.com/en/search/?technology_categories=AI",
        result_key="google_developers_blog_result",
    ),
    Site(
        name="anthropic_news",
        url="https://rsshub.app/anthropic/news",
        result_key="anthropic_news_result",
    ),
]
twitter_sites = [
    Site(
        name="twitter_ai_rumors_and_insights",
        url="1762494276565426592",
        result_key="twitter_ai_rumors_and_insights_result",
    ),
]
playwright_sites = [
    # Site(
    #     name="twitter",
    #     url="https://x.com/i/communities/1762494276565426592",
    #     result_key="twitter_result",
    # ),
    # Site(
    #     name="openai",
    #     url="https://openai.com/news/",
    #     result_key="openai_result",
    # ),
    # Site(
    #     name="aibusiness",
    #     url="https://aibusiness.com/ml",
    #     result_key="aibusiness_result",
    # ),
]
reddit_sites = [
    Site(
        name="r_singularity",
        url="singularity",
        result_key="reddit_singularity_result",
    ),
    Site(
        name="r_accelerate",
        url="accelerate",
        result_key="reddit_accelerate_result",
    ),
    Site(
        name="r_technology",
        url="technology",
        result_key="reddit_technology_result",
    ),
]


def get_news_prompt(site: Site, tool_name: str):
    return (
        "Research AI news.\n"
        f"Navigate to this website, using {tool_name}, to get the latest news about AI and AI products and models:\n"
        f"url: {site.url}, state_key: {site.result_key}\n"
        "Your article should be a markdown list of news items. Try to include dates and links to the news items.\n"
        f"Keep only the news for the latest 3 days. Today is {datetime.now().strftime('%d %b %Y')}"
    )


for site in playwright_sites:
    researcher_agent = Agent(
        name=f"{site.name}_researcher",
        model="gemini-2.5-flash",
        planner=planner,
        instruction=get_news_prompt(site, "browser_tab_new"),
        tools=[playwright_mcp_tool],
        output_key=site.result_key,
    )
    researcher_agents.append(researcher_agent)


for site in reddit_sites:
    researcher_agent = Agent(
        name=f"{site.name}_researcher",
        model="gemini-2.5-flash",
        planner=planner,
        instruction=get_news_prompt(
            site, "get_subreddit_top_posts with time='week', limit=50"
        ),
        tools=[reddit_mcp_tool],
        # output_key=site.result_key,
        # after_tool_callback=create_after_tool_callback(site),
    )
    researcher_agents.append(researcher_agent)

for site in fetch_sites:
    researcher_agent = Agent(
        name=f"{site.name}_researcher",
        model="gemini-2.5-flash",
        planner=planner,
        instruction=get_news_prompt(site, "get_news_from_url"),
        tools=[get_news_from_url_tool],
        # output_key=site.result_key,
    )
    researcher_agents.append(researcher_agent)

for site in twitter_sites:
    researcher_agent = Agent(
        name=f"{site.name}_researcher",
        model="gemini-2.5-flash",
        planner=planner,
        instruction=get_news_prompt(site, "get_community_tweets"),
        tools=[get_community_tweets_tool],
        # output_key=site.result_key,
    )
    researcher_agents.append(researcher_agent)

# ParallelAgent executes all researchers concurrently
parallel_research = ParallelAgent(
    name="ParallelToolExecution",
    sub_agents=researcher_agents,
    description="Executes all tool-using agents in parallel",
)

# Optional: Combine with SequentialAgent for post-processing
synthesis_agent = Agent(
    name="SynthesisAgent",
    model="gemini-2.5-flash",
    planner=planner,
    instruction=("""
You are a a specialist in AI and AI products and models.
Your goal is to generate news articles about AI and AI products and models.
Combine results from parallel research:
Then generate a news article about the latest news.
Your article should be a markdown list of news items. Try to include dates and links to the news items. Order by date desc.
Keep only the news for the latest 3 days. Today is {datetime.now().strftime('%d %b %Y')}
Format should be:

# AI news

## date J

    * ai news 1 - [domain_name.extension](article 1 url)
    * ai news 2 - [domain_name.extension](article 2 url)
    * ...

## date J-1

    * ai news 1 - [domain_name.extension](article 1 url)
    * ai news 2 - [domain_name.extension](article 2 url)
    * ...

## date J-2

    * ai news 1 - [domain_name.extension](article 1 url)
    * ai news 2 - [domain_name.extension](article 2 url)
    * ...

## Misc (ai news without date)

    * ai news 1 - [domain_name.extension](article 1 url)
    * ai news 2 - [domain_name.extension](article 2 url)
    * ...
"""

    ),
    description="Synthesizes parallel results",
    output_key="generated_news",
)

writer_to_firestore_agent = Agent(
    name="WriterToFirestoreAgent",
    model="gemini-2.5-flash",
    instruction=(
        "Call the write_to_firestore_tool to store the generated news in Firestore database."
    ),
    tools=[write_to_firestore_tool],
)

# Full pipeline: parallel execution then synthesis
root_agent = SequentialAgent(
    name="ai_news_agent",
    description=(
        "AI news specialist agent that generates news articles about AI and AI products."
    ),
    sub_agents=[parallel_research, synthesis_agent, writer_to_firestore_agent],
)
