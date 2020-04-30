#!/usr/bin/env python
# coding: utf-8

# In[1]:

from flask import Flask, request, render_template, flash, url_for
from wtforms import Form, validators, TextField
from imdb import IMDb
import pandas as pd
import numpy as np
from plotnine import *
import requests, os, io, random

app = Flask(__name__)

if 'SECRET_KEY' in os.environ: app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
else: app.config['SECRET_KEY'] = os.urandom(24)

global imdb
imdb = IMDb()




@app.route('/output/<ids>/<std>/', methods=['GET', 'POST'])
def display_output(ids, std):
    
    files = [file for file in os.listdir('static') if file.endswith('.png')]
    [os.remove('static/'+ filename) for filename in files]
    
    if request.method == 'POST':
        show = imdb.get_movie(ids)

        try:
            imdb.update(show, info = ['episodes'])
        except:
            print("Error 404- Show Episodes not found")

        show_obj = show_series(show)
        show_obj.create_df()
        show_obj.calc_outliers(sd=std)

        df = show_obj.df
        df['combined_labs'] = df['title'] + "\nS " + df['season'].astype(str) + " | E " + df['episode'].astype(str)
        outlier_index = df[df['outlier']==True].index.tolist()
        
        plot = (ggplot(df, aes(y='rating', x=df.index.tolist()))
            + geom_smooth(color='lightblue', size = 2)
            + geom_point(aes(color = 'factor(season)'), size = 2)
            + geom_label(aes(x = outlier_index,
                            y = df[df['outlier']==True]['rating'].values,
                            label = 'combined_labs'),
                        data = df[df['outlier']==True], size = 6, show_legend = False, alpha = .7, fill = 'gray',
                        adjust_text={'expand_points':(1.5, 1.5), 'expand_text':(2, 2), 'arrowprops': {'arrowstyle': '-'}})
            + labs(x = 'Episode Number', y = 'IMDb Rating', color = "Season")
            + theme_classic())
        filename = 'visual' + str(random.randrange(1,10000)) + '.png'
        plot.save(filename = 'static/' +  filename)
        
        return render_template('output.html', name = str(df['series'].unique()[0]), url = filename)
    return render_template('verify_show.html')


class Show_choices(Form):
    show = TextField('Show:', validators=[validators.DataRequired()])

@app.route('/', methods=['GET', 'POST'])
def index():        
    form = Show_choices(request.form)
    
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


@app.errorhandler(500)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('python_error.html')


class show_series():
    def __init__(self, show):
        self.show = show

    def create_df(self):
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
        self.df = self.get_ratings(df)
        
    def get_ratings(self, df):
        ratings = pd.read_csv('files/title.ratings.csv')
        df['rating'] = df['code'].apply(lambda x: ratings[ratings["tconst"] == x].values)
        df = df[df['rating'].apply(lambda x: len(x)) > 0]
        df['votes'] = df['rating'].apply(lambda x: x[0][2])
        df['rating'] = df['rating'].apply(lambda x: x[0][1])
        return df
    
    def calc_outliers(self, column = 'rating', sd = 2):
        groups = self.df.groupby('season')[column]
        groups_mean = groups.transform('mean')
        groups_std = groups.transform('std')
        self.df['outlier'] = self.df[column].between(groups_mean.sub(groups_std.mul(float(sd))),
                      groups_mean.add(groups_std.mul(float(sd))))
        self.df['outlier'] = [ True if x == False else False for x in self.df['outlier'] ]


        
if __name__ == '__main__':
    app.run(use_reloader=False)


# In[ ]:



