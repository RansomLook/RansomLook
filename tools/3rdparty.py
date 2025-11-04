#!/usr/bin/env python3

import requests

from ransomlook.default import get_homedir

plotly_version = "2.30.0"

if __name__ == '__main__':
    dest_dir = get_homedir() / 'website' / 'web' / 'static'

    plotly = requests.get(f'https://cdn.plot.ly/plotly-{plotly_version}.min.js')
    with (dest_dir / 'js'/ 'plotly.min.js').open('wb') as f:
        f.write(plotly.content)
        print(f'Downloaded plotly_js v{plotly_version}.')

    print('All 3rd party modules for the website were downloaded.')
