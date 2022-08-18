
#!/usr/bin/env python3
from ransomlook import ransomlook

def main():
    print("Starting scraping")
    ransomlook.scraper()
    ransomlook.forumscraper()

if __name__ == '__main__':
    main()

