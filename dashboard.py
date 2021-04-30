import streamlit as st
import requests as req
import sqlite3
from nsepy import *
import db
import talib as tb
import patterns
import pandas as pd
import streamlit.components.v1 as components
import ttm
import plotly.graph_objects as go
import time
import numpy as np
import json
import streamlit.components.v1 as components
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns
from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices
connection = db.getConnectionCursor()
dashboard = st.sidebar.selectbox(
    'Which Dashboard to open?', ('All Stocks','Strategies','Analysis','Portfolio','Pattern'))
cursor = connection.cursor()
if dashboard == 'All Stocks':
    st.title(dashboard)
    

    cursor.execute('''select symbol from stock''')
    stocks_symbols = cursor.fetchall()
    stocks = [item for t in stocks_symbols for item in t]
    symbol_search = st.sidebar.text_input("Stock name ")
    symbol = st.sidebar.selectbox("Select the Stock",stocks) 
    if symbol_search != "":
        symbol = symbol_search
    result = get_quote(symbol)
    #data = json.loads(result['data'][0])
    #df = pd.json_normalize(data['data']) 
    st.dataframe(pd.DataFrame(result['data']))
    
    
elif dashboard == 'Pattern':
    stocks= {}
    st.title(dashboard)
    cursor.execute('''select symbol from stock''')
    stocks_symbols = cursor.fetchall()
    stocks = [item for t in stocks_symbols for item in t]
    symbol = st.sidebar.selectbox("Select the Stock",stocks) 
    df = pd.read_sql("select open,high,low,close,symbol from stock_price where symbol ='"+symbol+"'", connection)
    cursor.execute('''select key,name from patterns''')
    patterns = cursor.fetchall()
    # patterns = [item for t in patterns for item in t]
    for pattern in patterns:
        pattern_function = getattr(tb,pattern[0])
        result = pattern_function(df['Open'],df['High'],df['Low'],df['Close'])
        last = result.tail(1).values[0]
        if last>0:
            st.write("Patter name : "+pattern[1])
            st.write("BULLISH")
        elif last<0:
            st.write("Patter name : "+pattern[1])
            st.write("BEARISH")

elif dashboard == 'Strategies':  
    st.title(dashboard)
    cursor.execute('''select name from strategy''')
    strategies = cursor.fetchall()
    strategies = [item for t in strategies for item in t]
    strategy = st.sidebar.selectbox("Select the Strategy",strategies)
    cursor.execute('''select name from sectors''')
    sectors = cursor.fetchall()
    sectors = [item for t in sectors for item in t]
    sector = st.sidebar.selectbox("Select the Sector",sectors)
    if sector == 'All':
        cursor.execute('''select symbol from stock''')
        stocks = cursor.fetchall()
        stock_in_sector = [item for t in stocks for item in t]       
    else:    
        df = pd.read_csv("nifty Sectors/"+sector+".csv")
        stock_in_sector = pd.Series(df['Symbol'])
        st.header("Strategy selected: "+strategy) 
    if strategy == 'TTM Squeeze':
            if sector != "":
                my_bar = st.progress(0)
                percent_complete = 1 
                i = 1   
                for stock in stock_in_sector:
                    percent_complete =  int( (i/len(stock_in_sector)) * 100)  
                    i=i+1    
                    df = pd.read_sql("select * from stock_price where symbol= '"+stock+"'", connection)
                    if df.empty:
                        continue
                    df['20sma'] = df['Close'].rolling(window=20).mean()
                    df['stddev'] = df['Close'].rolling(window=20).std()
                    df['lower_band'] = df['20sma'] - (2* df['stddev'])
                    df['upper_band'] = df['20sma'] + (2* df['stddev'])
                    df['TR'] = abs(df['High']) - df['Low']
                    df['ATR'] = df['TR'].rolling(window=20).mean()

                    df['lower_keltner'] = df['20sma'] - (df['ATR'] * 1.5)
                    df['upper_keltner'] = df['20sma'] + (df['ATR'] * 1.5)
                    obv = [] 
                    obv.append(0)
                    for index in range(1,len(df.Close)):   
                        if df.Close[index] > df.Close[index-1]:
                            obv.append(obv[-1] + df.Volume[i])
                        elif df.Close[index] < df.Close[index-1]:
                             obv.append(obv[-1] - df.Volume[i]) 
                        else:
                            obv.append(obv[-1])
                    df['OBV'] = obv
                    df['OBV_EMA'] = df['OBV'].ewm(span=20).mean()
     
                    def in_squeeze(df):
                        return df['lower_band'] > df['lower_keltner'] and df['upper_band'] < df['upper_keltner'] 
                    
                    df['squeeze_on'] = df.apply(in_squeeze,axis=1)
                    # st.dataframe(df)
                    #if len(df.squeeze_on.tail()) > 3:
                    if df.iloc[-3]['squeeze_on'] and not df.iloc[-1]['squeeze_on'] and df.iloc[-1]['OBV'] > df.iloc[-1]['OBV_EMA']:
                            mess = "{} is coming out of squeezer".format(stock)
                            st.write(mess)
                            
                            st.dataframe(df.sort_values(by=['Date'], ascending=False))
                            newdf = df
                            candlestick = go.Candlestick(x=newdf['Date'],open=newdf['Open'],high=newdf['High'],low=newdf['Low'],close=newdf['Close'])
                            upper_band = go.Scatter(x=newdf['Date'],y=newdf['upper_band'],name = 'Upper Bollinger Band',line = {'color':'red'})
                            lower_band = go.Scatter(x=newdf['Date'],y=newdf['lower_band'],name = 'Lower Bollinger Band',line = {'color':'red'})
                            upper_keltner = go.Scatter(x=newdf['Date'],y=newdf['upper_keltner'],name = 'Upper Keltner Channel',line = {'color':'blue'})
                            lower_keltner = go.Scatter(x=newdf['Date'],y=newdf['lower_keltner'],name = 'Lower Keltner Channel',line = {'color':'blue'})
                            OBV = go.Scatter(x=newdf['Date'],y=newdf['OBV'],name = 'On Balace Volume',line = {'color':'black'})
                            OBV_EMA = go.Scatter(x=newdf['Date'],y=newdf['OBV_EMA'],name = 'On Balace Volume EMA',line = {'color':'green'})
                            

                            fig = go.Figure(data=[candlestick,upper_band,lower_band,upper_keltner,lower_keltner,OBV,OBV_EMA])
                            fig.layout.xaxis.type = 'category'
                            fig.layout.xaxis.rangeslider.visible = False
                            st.plotly_chart(fig)
                    my_bar.progress(percent_complete)
                    if percent_complete == 100:
                        st.balloons()
    elif  strategy == 'On Balance Volume(OBV)':
            if sector != "":
                my_bar = st.progress(0)
                percent_complete = 1
                i = 1     
                for stock in stock_in_sector:
                    percent_complete =  int( (i/len(stock_in_sector)) * 100)  
                    i=i+1
                    st.subheader(stock)
                    df = pd.read_sql("select * from stock_price where symbol= '"+stock+"'", connection)
                    if df.empty:
                        continue    
                    obv = [] 
                    obv.append(0)
                    for index in range(1,len(df.Close)):   
                        if df.Close[index] > df.Close[index-1]:
                            obv.append(obv[-1] + df.Volume[i])
                        elif df.Close[index] < df.Close[index-1]:
                             obv.append(obv[-1] - df.Volume[i]) 
                        else:
                            obv.append(obv[-1])
                    df['OBV'] = obv
                    df['OBV_EMA'] = df['OBV'].ewm(span=20).mean()
                    newdf = df
                    candlestick = go.Candlestick(x=newdf['Date'],open=newdf['Open'],high=newdf['High'],low=newdf['Low'],close=newdf['Close'])                         
                    OBV = go.Scatter(x=newdf['Date'],y=newdf['OBV'],name = 'Volume',line = {'color':'yellow'})
                    OBV_EMA = go.Scatter(x=newdf['Date'],y=newdf['OBV_EMA'],name = 'Volume EMA',line = {'color':'green'})
                    fig = go.Figure(data=[OBV,OBV_EMA])
                    fig.layout.xaxis.type = 'category'
                    fig.layout.xaxis.rangeslider.visible = False
                    figPrice = go.Figure(data=[candlestick])
                    figPrice.layout.xaxis.type = 'category'
                    figPrice.layout.xaxis.rangeslider.visible = False
                    st.plotly_chart(figPrice)
                    st.plotly_chart(fig)
              

                    my_bar.progress(percent_complete)
                if percent_complete == 100:
                    st.balloons()


elif dashboard == 'Portfolio':
    st.title(dashboard)
    cursor.execute('''select name from sectors''')
    sectors = cursor.fetchall()
    sectors = [item for t in sectors for item in t]
    sector = st.sidebar.selectbox("Select the Sector",sectors)
    alldf = pd.read_sql("select * from stock_price", connection)
    if sector == 'All':
        cursor.execute('''select symbol from stock''')
        stocks = cursor.fetchall()
        stock_in_sector = [item for t in stocks for item in t] 
        alldf = alldf.loc[alldf['Symbol'].isin(stock_in_sector)]              
    else:    
        df = pd.read_csv("nifty Sectors/"+sector+".csv")
        stock_in_sector = pd.Series(df['Symbol'])
        alldf = alldf.loc[alldf['Symbol'].isin(df['Symbol'])]        
         
    #alldf = alldf.set_index(pd.DatetimeIndex(df['Date'].values))
    #alldf.drop(columns = ['Date'], axis =1, inplace=True)
    assets = alldf.Symbol.unique()
    alldf = alldf.set_index('Date')
    alldf = alldf.pivot_table(index='Date', columns=['Symbol'], values='Close')
    alldf = alldf.set_index(pd.DatetimeIndex(alldf.index.values))
    alldf = alldf.dropna(axis=1)
    #medals.reindex_axis(['Gold', 'Silver', 'Bronze'], axis=1)
    st.write(alldf)
    mu = expected_returns.mean_historical_return(alldf)
    s = risk_models.sample_cov(alldf)
    ef = EfficientFrontier(mu,s)
    weight = ef.max_sharpe()
    clean_weight = ef.clean_weights()
    expectedreturn, volatility, Sharperatio = ef.portfolio_performance(verbose=True)
    st.subheader("Expected annual return: " +str(round(expectedreturn,2)*100)+'%')
    st.subheader("Annual volatility: "+str(round(volatility,2)*100)+'%')
    st.subheader("Sharpe Ratio: "+str(round(Sharperatio,2)))
    funds = st.slider('PortFolio Value:',min_value=50000,max_value=500000)
    latest_prices = get_latest_prices(alldf)
    weights = clean_weight
    da = DiscreteAllocation(weights,latest_prices,total_portfolio_value=funds)
    allocation,leftover = da.lp_portfolio() 
    st.subheader("Weight")
    st.write(pd.DataFrame(weights, columns=weights.keys(), index=[0]))
    st.subheader("Discreate Allocation")
    st.write(pd.DataFrame(allocation, columns=allocation.keys(), index=[0]))
    st.subheader("Funds Reamaning:"+str(leftover))
    alldf.pct    