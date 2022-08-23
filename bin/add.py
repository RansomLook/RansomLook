#!/usr/bin/env python3
from ransomlook import ransomlook
import sys

def main():
    print("Adding location")
    if len(sys.argv) != 3 :
        print('usage : poetry run add [group url]')
        exit(1)
    ransomlook.adder(sys.argv[1].lower(), sys.argv[2])

if __name__ == '__main__':
    main()

