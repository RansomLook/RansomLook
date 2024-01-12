
#!/usr/bin/env python3
from ransomlook import ransomlook

def main() -> None:
    print("Starting scraping")
    ransomlook.scraper(0)
    ransomlook.scraper(3)

if __name__ == '__main__':
    main()

