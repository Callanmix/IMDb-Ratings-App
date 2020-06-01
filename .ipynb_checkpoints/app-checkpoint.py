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


# Init the flask server
server = Flask(__name__)

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
    app = {}
    if request.method == 'POST':
        filename = 'tmp/'+file+'.csv'
        data = pd.read_csv(filename)
        title = str(data['series'].unique()[0])
        pathname = ''.join(title.split()) + str(time.time())
        
        from dash_app import dash_app
        dash_app(data, title, server, pathname)
        
        return redirect('/' + pathname + '/')
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


        
if __name__ == '__main__':
    server.run(use_reloader = False)