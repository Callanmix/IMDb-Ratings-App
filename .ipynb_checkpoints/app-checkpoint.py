## Import all modules

# Flask
from flask import Flask, request, render_template, redirect, url_for
from wtforms import Form, validators, TextField

# General
from imdb import IMDb
import pandas as pd
import numpy as np
import time
import requests, os, random, gzip, urllib.request

import plotly_express as px
import plotly.graph_objects as go
import statsmodels.api as sm


dir_name = "static/"
for item in os.listdir(dir_name):
    if item.endswith(".html"):
        os.remove(os.path.join(dir_name, item))
        
dir_name = "tmp/"
for item in os.listdir(dir_name):
    if item.endswith(".csv"):
        os.remove(os.path.join(dir_name, item))

# Init the flask server
server = Flask(__name__,
               instance_relative_config=False,
               template_folder="templates",
               static_folder="static")

# Load the up to date rating information
baseURL = "https://datasets.imdbws.com/"
filename = "title.ratings.tsv.gz"
outFilePath = 'static/title.ratings.csv'
response = urllib.request.urlopen(baseURL + filename)

with open(outFilePath, 'wb') as outfile:
    outfile.write(gzip.decompress(response.read()))
    
# Load the data
ratings = pd.read_csv('static/title.ratings.csv', delimiter='\t')
ratings = ratings.set_index(['tconst'])


# Final output of Dash App
@server.route('/output/<file>/', methods=['GET', 'POST'])
def display_output(file):
    if request.method == 'POST':
        filename = 'tmp/'+file+'.csv'
        data = pd.read_csv(filename)
        
        filename = update_graph(data)

        return render_template('output.html', file = '/static/' + filename + '.html')
    return render_template('wait_page.html')

# form for the show entry
class Show_choices(Form):
    show = TextField('Show:', validators=[validators.DataRequired()])

## Choose the right show page
@server.route('/', methods=['GET', 'POST'])
def index():        
    form = Show_choices(request.form)
    imdb = IMDb()
    if request.method == 'POST':
        choice = request.form['show']
        results = imdb.search_movie(choice)
        names = [show['title'] for show in results if show['kind'] == 'tv series']
        year = [show['year'] for show in results if show['kind'] == 'tv series']
        urls = [show['full-size cover url'] for show in results if show['kind'] == 'tv series']
        ids = [imdb.get_imdbID(show) for show in results if show['kind'] == 'tv series']
        
        return render_template('verify_show.html', choice = choice, urls = urls,
                               year = year, names = names, length = len(names), ids = ids)
    return render_template('index.html')

## Wait page: This splits the server load time for heroku 
@server.route('/load_data/<ids>/', methods=['GET', 'POST'])
def load_data(ids):
    if request.method == 'POST':
        
        df = make_data(ids)
        pathname = str(df['series'].unique()[0])
        pathname = ''.join(pathname.split())
        df.to_csv('tmp/' + pathname + '.csv',index = False)
        
        return render_template('wait_page.html', pathname = pathname)
    return render_template('verify_show.html')


@server.errorhandler(500)
def page_not_found(e):
    return render_template('python_error.html')


def make_data(ids):
    # Init Imdb
    imdb = IMDb()
    show = imdb.get_movie(ids)
    imdb.update(show, info = ['episodes'])

    show_obj = show_series(show)
    show_obj.create_df()

    df = show_obj.df
    return df


class show_series():
    def __init__(self, show):
        self.show = show

    def create_df(self):
        imdb = IMDb()
        season, episode, title, year, series, code = [], [], [], [], [], []
        for x in self.show['episodes'].keys():
            for y in self.show['episodes'][x].keys():
                thing = self.show['episodes'][x][y]
                try:
                    year.append(thing['year'])
                    title.append(thing['title'])
                    series.append(self.show['title'])
                    code.append("tt" + imdb.get_imdbID(thing))
                    season.append(x)
                    episode.append(y)
                except:
                    pass
        df_dict = {'season':season, 'episode':episode, 'title':title, 'year':year, 'series':series, 'code':code}
        df = pd.DataFrame(df_dict).sort_values(by=['season', 'episode']).reset_index(drop=True)
        df.index += 1
        df['EpisodeNum'] = df.index
        self.df = self.get_ratings(df)
    
    def try_catch_rating(self, x):
        global ratings
        try:
            return ratings.loc[x, :].values
        except:
            return np.nan
        
    def get_ratings(self, df):
        df['rating'] = df['code'].apply(lambda x: self.try_catch_rating(x))
        df.dropna(inplace = True)
        df = df[df['rating'].apply(lambda x: len(x)) > 0]
        df['votes'] = df['rating'].apply(lambda x: x[1])
        df['rating'] = df['rating'].apply(lambda x: x[0])
        return df
    
    
def update_graph(df):
    df["season"] = df["season"].astype(str)
    lowess = sm.nonparametric.lowess
    z = lowess(df['rating'], df['EpisodeNum'])
    fig = px.scatter(
        df,
        x = 'EpisodeNum',
        y = 'rating',
        color="season", 
        hover_name = 'title',
        hover_data = ['episode'],
        opacity=0.7,
    )
    fig.add_trace(
        go.Scatter(
            x=z[:,0],
            y=z[:,1],
            line=dict(color='black', width=8, dash='dash'),
            showlegend=False,
            opacity = .4
            )
    )
    fig.update_traces(marker=dict(size=15,
                                  line=dict(width=2,
                                            color='DarkSlateGrey')),
                      selector=dict(mode='markers'))
    fig.update_layout(
            xaxis={'title':str(df['series'].unique()[0])},
            yaxis={'title':'IMDb Rating'},
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            legend={'x': 0, 'y': 1},
            hovermode='closest')
    fig.update_layout(legend_orientation="h",
                     legend=dict(x=-.1, y=1.2))
    fig.update_xaxes(showspikes=True)   
    filename = '_'.join(str(df['series'].unique()[0]).split())
    fig.write_html("static/"+ filename +".html")
    return filename

        
if __name__ == '__main__':
    server.run(use_reloader = False)