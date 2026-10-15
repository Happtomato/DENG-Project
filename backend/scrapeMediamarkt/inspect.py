import json
from pathlib import Path
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]

HTML_FILE = (
    PROJECT_ROOT
    / "data"
    / "debug"
    / "mediamarkt_product.html"
)


def inspect_html():
    html = HTML_FILE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== JSON-LD BLOCKS ==========")

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for index, script in enumerate(scripts):
        print(f"\n--- JSON-LD BLOCK {index} ---")

        try:
            data = json.loads(
                script.string or script.get_text()
            )

            print(json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            )[:5000])

        except json.JSONDecodeError as error:
            print("Invalid JSON:", error)

    print("\n========== PRICE KEYWORDS ==========")

    keywords = [
        "price",
        "sellingPrice",
        "salesPrice",
        "currentPrice",
        "productPrice",
        "availability",
        "ean",
        "manufacturer"
    ]

    for keyword in keywords:
        print(f"\n--- {keyword} ---")

        position = html.lower().find(keyword.lower())

        if position == -1:
            print("Not found")
            continue

        start = max(0, position - 150)
        end = min(len(html), position + 350)

        print(html[start:end])


if __name__ == "__main__":
    inspect_html()