#!/usr/bin/env python3
import redis
import os
from ransomlook.default import get_socket_path, get_config
from ransomlook.default.config import get_homedir

import json
import csv
import datetime

import plotly.express as px
import plotly.io as pio
import pandas as pd

from typing import Dict

def run_data_viz(days_filter):
    now = datetime.datetime.now()

    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)

    group_names = []
    timestamps = []
    for key in red.keys():
        posts = json.loads(red.get(key))
        for post in posts:
            postdate = datetime.datetime.fromisoformat(post['discovered'])
            if (now - postdate).days < days_filter:
                group_names.append(key.decode())
                timestamps.append(post['discovered'])
    df = pd.DataFrame({'group_name': group_names, 'timestamp': timestamps})
    # Convert the timestamps into a datetime format
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Group and sort the data by the number of postings in each group
    df_sorted = df.groupby(['group_name', 'timestamp']).size().reset_index(name='count')
    df_sorted = df_sorted.sort_values(by='count', ascending=False)


    # Use Plotly's Scatter plot to create the scatter plot
    fig2 = px.scatter(df_sorted, x='timestamp', y='group_name', color='group_name', title='Posting Frequency by group', color_continuous_scale='Plotly3', width=1050, height=750)
    #fig2 = px.scatter(df_sorted, x='group_name', y='count', title='Posting Frequency by Group', template='plotly_dark')
    filename = os.path.join(get_homedir(),"source/screenshots/stats","scatter_plot_"+ str(days_filter)+".png")
    fig2.write_image(filename)

    # Use Plotly's Bar plot to create the bar chart
    #fig4 = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posting Frequency by Group', template='plotly_dark', color_continuous_scale='Portland')
    #fig4.show()

    # Group and sort the data by the number of postings in each group
    df_sorted = df.groupby('group_name').size().reset_index(name='count').sort_values(by='count', ascending=True)

    # Use Plotly's Pie plot to create the pie chart
    fig3 = px.pie(df_sorted, values='count', names='group_name', title='Posting Frequency by Group', width=1050, height=750)
    filename = os.path.join(get_homedir(),"source/screenshots/stats","pie_chart_"+ str(days_filter)+".png")
    fig3.write_image(filename)

    # Use Plotly's Scatter plot to visualize the data
    fig4 = px.bar(df_sorted, x='group_name', y='count', color='count', title='Posting Frequency by Group', color_continuous_scale='Portland',width=1050, height=750)
    filename = os.path.join(get_homedir(),"source/screenshots/stats","bar_chart_"+ str(days_filter)+".png")
    fig4.write_image(filename)


def main():
    run_data_viz(7)
    run_data_viz(14)
    run_data_viz(30)
    run_data_viz(90)

if __name__ == '__main__':
    main()
