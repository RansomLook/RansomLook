#!/usr/bin/env python3

#!/usr/bin/env python3
from ransomlook import twitter

def main():
    print("Starting scraping")
    twitter.scraper()
    twitter.parser()

if __name__ == '__main__':
    main()

