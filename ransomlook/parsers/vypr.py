import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def build_description(company: dict) -> str:
    parts = []
    website = company.get("website")
    if website:
        parts.append(str(website))
    country = company.get("country")
    if isinstance(country, dict) and country.get("name"):
        parts.append(country["name"])
    category = company.get("category")
    if isinstance(category, dict) and category.get("name"):
        parts.append(category["name"])
    employees = company.get("employees")
    if employees:
        parts.append("Employees: " + str(employees))
    revenue = company.get("revenue")
    if revenue:
        parts.append("Revenue: " + str(revenue))
    return " | ".join(parts)


def main() -> list[dict[str, str]]:
    list_div: list[dict[str, str]] = []
    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")
            # API /api/v1/posts rendered as JSON inside a <pre> tag
            data = json.loads(soup.pre.text)  # type: ignore
            for entry in data["data"]["posts"]:
                if entry.get("status") != "published":
                    continue
                company = entry.get("company", {})
                title = company.get("name", "").strip()
                if not title:
                    continue
                list_div.append(
                    {
                        "title": title,
                        "description": build_description(company),
                        "link": "/blog/posts/" + str(entry["id"]),
                        "slug": filename,
                    }
                )
        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)
    logger.debug(list_div)
    return list_div
