## Import all modules
# Flask
from flask import Flask, request, render_template, redirect, url_for
from wtforms import Form, validators, TextField
# General
from imdb import IMDb
import pandas as pd
import numpy as np
import requests, os, random, gzip, urllib.request
# Dash
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly_express as px
import plotly.graph_objects as go
import statsmodels.api as sm


# Init the flask server
server = Flask(__name__)

# Load the up to date rating information
baseURL = "https://datasets.imdbws.com/"
filename = "title.ratings.tsv.gz"
outFilePath = 'files/title.ratings.csv'
response = urllib.request.urlopen(baseURL + filename)
with open(outFilePath, 'wb') as outfile:
    outfile.write(gzip.decompress(response.read()))
# Load the data
ratings = pd.read_csv('files/title.ratings.csv', delimiter='\t')
ratings = ratings.set_index(['tconst'])
# Init Imdb
imdb = IMDb()


# Final output of Dash App
@server.route('/output/', methods=['GET', 'POST'])
def display_output():
   
    if request.method == 'POST':    
        return redirect('/dash')
    return render_template('wait_page.html')

# form for the show entry
class Show_choices(Form):
    show = TextField('Show:', validators=[validators.DataRequired()])

## Choose the right show page
@server.route('/', methods=['GET', 'POST'])
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

## Wait page: This splits the server load time for heroku 
@server.route('/load_data/<ids>/', methods=['GET', 'POST'])
def load_data(ids):
    if request.method == 'POST':
        
        global df
        df = make_data(ids)
        
        return render_template('wait_page.html')
    return render_template('verify_show.html')


@server.errorhandler(500)
def page_not_found(e):
    return render_template('python_error.html')


app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                server=server,
                routes_pathname_prefix='/dash/')
colors = {
    'background': '#111111',
    'text': '#7FDBFF'
}
navbar = dbc.Navbar(
        [
            html.A(
                # Use row and col to control vertical alignment of logo / brand
                dbc.Row(
                    [
                        dbc.Col(dbc.NavbarBrand("Go Home", className="ml-2")),
                    ],
                    align="center",
                    no_gutters=True,
                ),
                href="/",
            )
        ],
        color="dark",
        dark=True,
    )
app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    navbar,
    html.H1(
        children='IMDb TV Series Score',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    
    html.Div(style={'textAlign': 'center','color': colors['text']}, children=[
        dcc.RadioItems(
                id='yaxis',
                options=[{'label': i, 'value': i} for i in ['Rating', 'Votes']],
                value='Rating',
                labelStyle={'display': 'inline-block'}
            )
    ]),
    
    html.Div([
        dcc.Graph(id='indicator-graphic')
    ])
])  
@app.callback(
    Output('indicator-graphic', 'figure'),
    [Input('yaxis', 'value')])
def update_graph(yaxis):
    df["season"] = df["season"].astype(str)
    lowess = sm.nonparametric.lowess
    z = lowess(df[yaxis.lower()], df['EpisodeNum'])
    fig = px.scatter(
        df,
        x = 'EpisodeNum',
        y = yaxis.lower(),
        color="season", 
        hover_name = 'title',
        hover_data = ['episode'],
        opacity=0.7,
    )
    fig.add_trace(
        go.Scatter(
            x=z[:,0],
            y=z[:,1],
            line=dict(color='white', width=8, dash='dash'),
            showlegend=False,
            opacity = .4
            )
    )
    fig.update_traces(marker=dict(size=15,
                                  line=dict(width=2,
                                            color='DarkSlateGrey')),
                      selector=dict(mode='markers'))
    fig.update_layout(
            xaxis={'title':'Episodes Number: ' + str(df['series'].unique()[0])},
            yaxis={'title':'IMDb Rating'},
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            legend={'x': 0, 'y': 1},
            hovermode='closest',
            #plot_bgcolor = colors['background'],
            paper_bgcolor = colors['background'],
            font = {
                'color': colors['text']
            })
    fig.update_layout(legend_orientation="h",
                     legend=dict(x=-.1, y=1.2))
    fig.update_xaxes(showspikes=True)    
    return fig


def make_data(ids):
    global imdb
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
    app.run_server(use_reloader=False)