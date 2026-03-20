import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                divs_name = soup.find_all(
                    "a",
                    {
                        "class": "flex flex-col justify-between w-full h-56 border-t-4 border-2 border-t-green-500 dark:border-gray-900 dark:border-t-green-500 rounded-[20px] bg-white dark:bg-navy-800"
                    },
                )
                for div in divs_name:
                    section = div.find("span", {"class": "dark:text-gray-600"})
                    title = section.text.strip()
                    description = div.find("span", {"class": "text-sm dark:text-gray-600"}).text.strip()
                    link = div["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                divs_name = soup.find_all(
                    "a",
                    {
                        "class": "flex flex-col justify-between w-full h-56 border-t-4 border-2 border-t-red-500 dark:border-gray-900 dark:border-t-red-500 rounded-[20px] bg-white dark:bg-navy-800"
                    },
                )
                for div in divs_name:
                    section = div.find("span", {"class": "dark:text-gray-600"})
                    title = section.text.strip()
                    description = div.find("span", {"class": "text-sm dark:text-gray-600"}).text.strip()
                    link = div["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                divs_name = soup.find_all("a", {"class": "announcement__container"})
                for div in divs_name:
                    title = div.find("span", {"class": "text-xs text-white"}).text.strip()
                    description = ""
                    link = div["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})

                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
