import hashlib
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse

from google.adk.tools.function_tool import ToolContext
from google.cloud import firestore
from google.cloud.firestore import FieldFilter


class NewsItem:
    def __init__(
        self,
        title: str,
        url: str = "",
        date: str | None = None,
        domain: str | None = None,
    ):
        self.title = title.strip()
        self.url = url.strip()
        self.date = date
        self.domain = domain or self._extract_domain(url) if url else None

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return ""

    def get_document_id(self) -> str:
        """Generate a Firestore-safe document ID from the URL."""
        if not self.url:
            # If no URL, use a hash of the title
            return hashlib.sha256(self.title.encode()).hexdigest()[:20]

        # Create a hash of the URL for a safe document ID
        url_hash = hashlib.sha256(self.url.encode()).hexdigest()
        return f"news_{url_hash[:20]}"

    def __eq__(self, other):
        if not isinstance(other, NewsItem):
            return False
        # Compare by URL for uniqueness
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def to_dict(self) -> dict:
        """Convert to dictionary for Firestore storage."""
        return {
            "title": self.title,
            "url": self.url,
            "date": self.date,
            "domain": self.domain,
            "created_at": datetime.utcnow(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        """Create NewsItem from Firestore document."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            date=data.get("date"),
            domain=data.get("domain"),
        )

    def __str__(self):
        if self.url and self.domain:
            return f"* {self.title} - [{self.domain}]({self.url})"
        return f"* {self.title}"


class FirestoreNewsManager:
    def __init__(
        self,
        project_id: str | None = None,
        database_id: str = "(default)",
        collection_name: str = "news",
    ):
        """
        Initialize Firestore client with configurable project and database.

        Args:
            project_id: Google Cloud project ID. If None, uses default from environment.
            database_id: Firestore database ID. Defaults to "(default)".
            collection_name: Name of the collection to store news items.
        """
        # Initialize Firestore client with specified project and database
        if project_id:
            self.db = firestore.Client(project=project_id, database=database_id)
        else:
            self.db = firestore.Client(database=database_id)

        self.collection_name = collection_name
        self.project_id = project_id
        self.database_id = database_id

    def _get_collection(self):
        """Get the news collection reference."""
        return self.db.collection(self.collection_name)

    def add_news_item(self, news_item: NewsItem) -> bool:
        """Add a news item to Firestore. Returns True if added, False if already exists."""
        try:
            # Check if URL already exists
            existing_query = self._get_collection().where(
                filter=FieldFilter("url", "==", news_item.url)
            )
            existing_docs = list(existing_query.stream())

            if existing_docs:
                return False  # Already exists

            # Add new document with safe document ID
            doc_id = news_item.get_document_id()
            doc_ref = self._get_collection().document(doc_id)
            doc_ref.set(news_item.to_dict())
            return True
        except Exception as e:
            print(f"Error adding news item: {e}")
            return False

    def add_news_items_batch(self, news_items: list[NewsItem]) -> tuple[int, int]:
        """
        Add multiple news items to Firestore using batch operations.
        Returns (added_count, skipped_count).
        """
        if not news_items:
            return 0, 0

        try:
            # Get all URLs to check for existing items
            urls = [item.url for item in news_items if item.url]
            if not urls:
                return 0, len(news_items)

            # Check for existing URLs in chunks (Firestore IN operator supports max 30 values)
            existing_urls = set()
            if urls:
                # Process URLs in chunks of 30 to respect Firestore IN operator limit
                chunk_size = 30
                for i in range(0, len(urls), chunk_size):
                    url_chunk = urls[i:i + chunk_size]
                    existing_query = self._get_collection().where(
                        filter=FieldFilter("url", "in", url_chunk)
                    )
                    existing_docs = list(existing_query.stream())
                    existing_urls.update(doc.to_dict().get("url") for doc in existing_docs)

            # Prepare batch write
            batch = self.db.batch()
            added_count = 0
            skipped_count = 0

            for news_item in news_items:
                if news_item.url in existing_urls:
                    skipped_count += 1
                    continue

                # Add to batch
                doc_id = news_item.get_document_id()
                doc_ref = self._get_collection().document(doc_id)
                batch.set(doc_ref, news_item.to_dict())
                added_count += 1

            # Commit batch if there are items to add
            if added_count > 0:
                batch.commit()

            return added_count, skipped_count

        except Exception as e:
            print(f"Error adding news items in batch: {e}")
            return 0, len(news_items)

    def get_all_news(self) -> list[NewsItem]:
        """Get all news items from Firestore."""
        try:
            docs = self._get_collection().stream()
            news_items = []
            for doc in docs:
                data = doc.to_dict()
                news_items.append(NewsItem.from_dict(data))
            return news_items
        except Exception as e:
            print(f"Error getting news items: {e}")
            return []

    def get_recent_news(self, limit: int = 100) -> list[NewsItem]:
        """Get recent news items from Firestore (limited for performance)."""
        try:
            # Order by created_at descending and limit results
            docs = (
                self._get_collection()
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            news_items = []
            for doc in docs:
                data = doc.to_dict()
                news_items.append(NewsItem.from_dict(data))
            return news_items
        except Exception as e:
            print(f"Error getting recent news items: {e}")
            return []

    def get_news_by_date(self, date: str) -> list[NewsItem]:
        """Get news items for a specific date."""
        try:
            query = self._get_collection().where(filter=FieldFilter("date", "==", date))
            docs = query.stream()
            news_items = []
            for doc in docs:
                data = doc.to_dict()
                news_items.append(NewsItem.from_dict(data))
            return news_items
        except Exception as e:
            print(f"Error getting news by date: {e}")
            return []

    def get_news_by_domain(self, domain: str) -> list[NewsItem]:
        """Get news items from a specific domain."""
        try:
            query = self._get_collection().where(
                filter=FieldFilter("domain", "==", domain)
            )
            docs = query.stream()
            news_items = []
            for doc in docs:
                data = doc.to_dict()
                news_items.append(NewsItem.from_dict(data))
            return news_items
        except Exception as e:
            print(f"Error getting news by domain: {e}")
            return []

    def delete_news_item(self, url: str) -> bool:
        """Delete a news item by URL."""
        try:
            # Find the document by URL first
            existing_query = self._get_collection().where(
                filter=FieldFilter("url", "==", url)
            )
            existing_docs = list(existing_query.stream())

            if not existing_docs:
                return False  # Document not found

            # Delete the document
            doc_ref = existing_docs[0].reference
            doc_ref.delete()
            return True
        except Exception as e:
            print(f"Error deleting news item: {e}")
            return False


def parse_markdown_content(content: str) -> dict[str, list[NewsItem]]:
    """Parse markdown content into date sections with news items."""
    sections = {}
    current_section = None

    lines = content.split("\n")
    for line in lines:
        line = line.strip()

        # Check for date headers (## date format)
        if line.startswith("## ") and not line.startswith("### "):
            current_section = line[3:].strip()  # Remove '## '
            sections[current_section] = []

        # Check for news items (starting with *)
        elif line.startswith("* ") and current_section is not None:
            # Extract text and URL from markdown link format
            text = line[2:].strip()  # Remove '* '

            # Try to extract URL from markdown link format: text - [domain](url)
            url_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", text)
            if url_match:
                domain = url_match.group(1)
                url = url_match.group(2)
                title = text.replace(f" - [{domain}]({url})", "")
                news_item = NewsItem(title, url, current_section, domain)
            else:
                news_item = NewsItem(text, date=current_section)

            sections[current_section].append(news_item)

    return sections


def extract_news_items_from_text(text: str, date: str | None = None) -> list[NewsItem]:
    """Extract news items from raw text content."""
    items = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if line.startswith("* "):
            text_content = line[2:].strip()  # Remove '* '

            # Try to extract URL from markdown link format
            url_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", text_content)
            if url_match:
                domain = url_match.group(1)
                url = url_match.group(2)
                title = text_content.replace(f" - [{domain}]({url})", "")
                items.append(NewsItem(title, url, date, domain))
            else:
                items.append(NewsItem(text_content, date=date))

    return items


def find_unseen_news(
    existing_items: set[NewsItem], new_items: list[NewsItem]
) -> list[NewsItem]:
    """Find news items that don't exist in the existing content."""
    return [item for item in new_items if item not in existing_items]


def write_to_firestore_tool(tool_context: ToolContext):
    """Tool to write news content to Firestore database."""
    start_time = time.time()
    timing_info = {}

    content = tool_context.state.get("generated_news")

    if not content:
        return {"status": "error", "message": "No generated news content found"}

    try:
        # Section 1: Initialize Firestore manager
        section_start = time.time()
        firestore_manager = create_firestore_manager()
        timing_info["firestore_init"] = time.time() - section_start

        # Section 2: Parse markdown content
        section_start = time.time()
        sections = parse_markdown_content(content)
        timing_info["markdown_parse"] = time.time() - section_start

        # Section 3: Process and add news items (optimized batch operation)
        section_start = time.time()

        # Collect all news items from all sections
        all_new_items = []
        for news_items in sections.values():
            all_new_items.extend(news_items)

        # Use batch operation for better performance
        added_count, skipped_count = firestore_manager.add_news_items_batch(
            all_new_items
        )
        timing_info["add_news_items"] = time.time() - section_start

        # Calculate total time
        total_time = time.time() - start_time
        timing_info["total"] = total_time

        return {
            "status": "success",
            "message": f"Added {added_count} new news items to Firestore, skipped {skipped_count} duplicates",
            "added": added_count,
            "skipped": skipped_count,
            "timing": timing_info,
        }

    except Exception as e:
        total_time = time.time() - start_time
        return {
            "status": "error",
            "message": f"Error writing to Firestore: {e!s}",
            "timing": {"total": total_time},
        }


def parse_date_for_sorting(section_name):
    """Parse date for sorting purposes."""
    try:
        # Try different date formats including year
        for fmt in [
            "%d %b %Y",
            "%b %d %Y",
            "%d %B %Y",
            "%B %d %Y",
            "%b %d",
            "%d %b",
            "%B %d",
            "%d %B",
        ]:
            try:
                return datetime.strptime(section_name, fmt)
            except ValueError:
                continue
        # If no date format matches, return a far future date to put it at the end
        return datetime(9999, 12, 31)
    except Exception:
        return datetime(9999, 12, 31)


def create_firestore_manager(
    project_id: str | None = None,
    database_id: str | None = None,
    collection_name: str | None = None,
) -> FirestoreNewsManager:
    """
    Create a FirestoreNewsManager with configuration from environment variables or parameters.

    Args:
        project_id: Google Cloud project ID. If None, uses GOOGLE_CLOUD_PROJECT env var.
        database_id: Firestore database ID. If None, uses FIRESTORE_DATABASE_ID env var or "(default)".
        collection_name: Collection name. If None, uses FIRESTORE_COLLECTION_NAME env var or "news".

    Returns:
        Configured FirestoreNewsManager instance.
    """
    # Use parameters or fall back to environment variables
    final_project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    final_database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "(default)")
    final_collection_name = collection_name or os.getenv(
        "FIRESTORE_COLLECTION_NAME", "news"
    )

    return FirestoreNewsManager(
        project_id=final_project_id,
        database_id=final_database_id,
        collection_name=final_collection_name,
    )


def get_news_from_firestore_tool(tool_context: ToolContext):
    """Tool to retrieve news from Firestore database."""
    start_time = time.time()
    timing_info = {}

    try:
        # Section 1: Initialize Firestore manager
        section_start = time.time()
        firestore_manager = create_firestore_manager()
        timing_info["firestore_init"] = time.time() - section_start

        # Section 2: Retrieve all news
        section_start = time.time()
        all_news = firestore_manager.get_all_news()
        timing_info["retrieve_all_news"] = time.time() - section_start

        # Section 3: Group and format news for display
        section_start = time.time()
        news_by_date = {}
        for item in all_news:
            date = item.date or "Misc"
            if date not in news_by_date:
                news_by_date[date] = []
            news_by_date[date].append(item)

        # Create markdown representation
        markdown_content = "# AI news\n\n"

        # Sort dates (most recent first)
        sorted_dates = sorted(
            news_by_date.keys(), key=lambda x: parse_date_for_sorting(x), reverse=True
        )

        for date in sorted_dates:
            if news_by_date[date]:  # Only add non-empty sections
                markdown_content += f"## {date}\n"
                for item in news_by_date[date]:
                    markdown_content += f"{item!s}\n"
                markdown_content += "\n"

        tool_context.state["news"] = markdown_content
        timing_info["format_display"] = time.time() - section_start

        # Calculate total time
        total_time = time.time() - start_time
        timing_info["total"] = total_time

        return {
            "status": "success",
            "message": f"Retrieved {len(all_news)} news items from Firestore",
            "count": len(all_news),
            "timing": timing_info,
        }

    except Exception as e:
        total_time = time.time() - start_time
        return {
            "status": "error",
            "message": f"Error reading from Firestore: {e!s}",
            "timing": {"total": total_time},
        }
