
#!/usr/bin/env python3
from ransomlook import ransomlook

def main():
    print("Starting scraping")
    ransomlook.scraper("data/groups.json")
    ransomlook.scraper("data/markets.json")

if __name__ == '__main__':
    main()

