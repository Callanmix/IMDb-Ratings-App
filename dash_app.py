# Dash
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly_express as px
import plotly.graph_objects as go
import statsmodels.api as sm


def dash_app(df, title, server, pathname):
    app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                server=server,
                routes_pathname_prefix='/' + pathname + '/')
    
    app.url_base_pathname = '/' + pathname + '/'
    app.routes_pathname_prefix = app.url_base_pathname
    app.title = title

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
        html.H4(
            children=title,
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
    return app
