from datetime import datetime

from google import genai
from google.genai.types import GenerateContentConfig, Tool


def main():
    client = genai.Client(vertexai=True, project="my-first-project-199607", location="us-central1")
    model_id = "gemini-2.5-flash"

    tools = [
    {"url_context": {}},
    ]

    url1 = "https://news.ycombinator.com/"

    response = client.models.generate_content(
        model=model_id,
        contents="Research AI news.\n"
            f"Navigate to this website to get the latest news about AI and AI products and models:\n"
            f"url: {url1}\n"
            "Your article should be a markdown list of news items. Try to include dates and links to the news items.\n"
            f"Keep only the news for the latest 3 days. Today is {datetime.now().strftime('%d %b %Y')}",
        config=GenerateContentConfig(
            tools=tools,
        )
    )

    for each in response.candidates[0].content.parts:
        print(each.text)

    # For verification, you can inspect the metadata to see which URLs the model retrieved
    print(response.candidates[0].url_context_metadata)


if __name__ == "__main__":
    main()