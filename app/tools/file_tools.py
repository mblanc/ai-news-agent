import os
import re
from datetime import datetime

from google.adk.tools.function_tool import ToolContext

AI_NEWS_FILE_PATH = "ai_news.md"

class NewsItem:
    def __init__(self, text: str, url: str = ""):
        self.text = text.strip()
        self.url = url.strip()

    def __eq__(self, other):
        if not isinstance(other, NewsItem):
            return False
        # Compare normalized text (remove extra spaces, case insensitive)
        return self.text.lower().strip() == other.text.lower().strip()

    def __hash__(self):
        return hash(self.text.lower().strip())

    def __str__(self):
        if self.url:
            return f"* {self.text} - [{self.url}]({self.url})"
        return f"* {self.text}"


def parse_markdown_content(content: str) -> dict[str, list[NewsItem]]:
    """Parse markdown content into date sections with news items."""
    sections = {}
    current_section = None

    lines = content.split('\n')
    for line in lines:
        line = line.strip()

        # Check for date headers (## date format)
        if line.startswith('## ') and not line.startswith('### '):
            current_section = line[3:].strip()  # Remove '## '
            sections[current_section] = []

        # Check for news items (starting with *)
        elif line.startswith('* ') and current_section is not None:
            # Extract text and URL from markdown link format
            text = line[2:].strip()  # Remove '* '

            # Try to extract URL from markdown link format: text - [domain](url)
            url_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', text)
            if url_match:
                domain = url_match.group(1)
                url = url_match.group(2)
                news_item = NewsItem(text.replace(f" - [{domain}]({url})", ""), url)
            else:
                news_item = NewsItem(text)

            sections[current_section].append(news_item)

    return sections


def extract_news_items_from_text(text: str) -> list[NewsItem]:
    """Extract news items from raw text content."""
    items = []
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith('* '):
            text_content = line[2:].strip()  # Remove '* '

            # Try to extract URL from markdown link format
            url_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', text_content)
            if url_match:
                domain = url_match.group(1)
                url = url_match.group(2)
                news_text = text_content.replace(f" - [{domain}]({url})", "")
                items.append(NewsItem(news_text, url))
            else:
                items.append(NewsItem(text_content))

    return items


def find_unseen_news(existing_items: set[NewsItem], new_items: list[NewsItem]) -> list[NewsItem]:
    """Find news items that don't exist in the existing content."""
    return [item for item in new_items if item not in existing_items]


def merge_news_content(existing_content: str, new_content: str) -> str:
    """Merge new AI news content with existing content, adding only unseen news."""
    if not existing_content.strip():
        return new_content

    # Parse existing content
    existing_sections = parse_markdown_content(existing_content)

    # Extract all existing news items for comparison
    all_existing_items = set()
    for items in existing_sections.values():
        all_existing_items.update(items)

    # Parse new content
    new_sections = parse_markdown_content(new_content)

    # Find unseen news in each section
    merged_sections = existing_sections.copy()

    for section_name, new_items in new_sections.items():
        if section_name not in merged_sections:
            merged_sections[section_name] = []

        unseen_items = find_unseen_news(all_existing_items, new_items)

        if unseen_items:
            merged_sections[section_name].extend(unseen_items)
            # Update the set of existing items to avoid duplicates in subsequent sections
            all_existing_items.update(unseen_items)

    # Reconstruct the markdown content
    result_lines = []

    # Add title if it exists
    if existing_content.strip().startswith('# '):
        result_lines.append('# AI news')

    # Sort sections by date (most recent first)
    section_order = []
    misc_section = None

    for section_name in merged_sections.keys():
        if section_name.lower() == 'misc' or 'misc' in section_name.lower():
            misc_section = section_name
        else:
            section_order.append(section_name)

    # Sort date sections (assuming format like "Dec 15", "15 Dec", "07 Sep 2025", etc.)
    def parse_date_for_sorting(section_name):
        try:
            # Try different date formats including year
            for fmt in ['%d %b %Y', '%b %d %Y', '%d %B %Y', '%B %d %Y', '%b %d', '%d %b', '%B %d', '%d %B']:
                try:
                    return datetime.strptime(section_name, fmt)
                except ValueError:
                    continue
            # If no date format matches, return a far future date to put it at the end
            return datetime(9999, 12, 31)
        except Exception:
            return datetime(9999, 12, 31)

    section_order.sort(key=parse_date_for_sorting, reverse=True)

    # Add date sections
    for section_name in section_order:
        if merged_sections[section_name]:  # Only add non-empty sections
            result_lines.append(f"## {section_name}")
            for item in merged_sections[section_name]:
                result_lines.append(str(item))
            result_lines.append("")  # Add empty line after section

    # Add misc section at the end if it exists and has content
    if misc_section and merged_sections[misc_section]:
        result_lines.append(f"## {misc_section}")
        for item in merged_sections[misc_section]:
            result_lines.append(str(item))

    return '\n'.join(result_lines)


def write_to_file_tool(tool_context: ToolContext):
    content = tool_context.state.get("generated_news")

    # Check if file exists and read existing content
    existing_content = ""
    if os.path.exists(AI_NEWS_FILE_PATH):
        with open(AI_NEWS_FILE_PATH) as f:
            existing_content = f.read()

    # Merge new content with existing content intelligently
    merged_content = merge_news_content(existing_content, content)

    # Write the merged content to file
    with open(AI_NEWS_FILE_PATH, "w") as f:
        f.write(merged_content)

    return {"status": "success", "message": f"AI news content intelligently merged into {AI_NEWS_FILE_PATH}"}
