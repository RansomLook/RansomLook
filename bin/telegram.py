#!/usr/bin/env python3
from ransomlook import telegram

def main():
    print("Starting scraping")
    telegram.scraper()
    telegram.parser()

if __name__ == '__main__':
    main()

