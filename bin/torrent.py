#!/usr/bin/env python3
from ransomlook import ransomlook

def main():
    print("Starting torrent")
    ransomlook.gettorrentinfo()
    print("Stopping torrent")

if __name__ == '__main__':
    main()

