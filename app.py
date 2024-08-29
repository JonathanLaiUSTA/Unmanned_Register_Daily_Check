import pandas as pd
import numpy as np
import itertools
from collections import defaultdict

import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns

import streamlit as st
import time

st.set_page_config(layout="wide")

st.title("Unmanned Registers Daily Check")

st.divider()

st.header("Upload Files Here")

## NEW DATA READ WITH SQL TRANSFORMATIONS, get latest extract daily from SQL

data_22B = pd.DataFrame({'A' : []})
data_Oct = pd.DataFrame({'A' : []})
data_S2 = pd.DataFrame({'A' : []})
data_11G = pd.DataFrame({'A' : []})

data_22B_upload = st.file_uploader("**22B Volumes**", type="csv", key="Upload_22B")
if data_22B_upload:
    data_22B = pd.read_csv(data_22B_upload)

data_Oct_upload = st.file_uploader("**Oct Volumes**", type="csv", key="Upload_Oct")
if data_Oct_upload:
    data_Oct = pd.read_csv(data_Oct_upload)

data_S2_upload = st.file_uploader("**S2 Volumes**", type="csv", key="Upload_S2")
if data_S2_upload:
    data_S2 = pd.read_csv(data_S2_upload)

data_11G_upload = st.file_uploader("**11G Volumes**", type="csv", key="Upload_11G")
if data_11G_upload:
    data_11G = pd.read_csv(data_11G_upload)

######################################################## NEXT SECTION ########################################################

st.divider()
viz_header = st.header("Visualizations Pending...") 

if all([len(data_22B)!=0, len(data_Oct)!=0, len(data_S2)!=0, len(data_11G)!=0]):

    viz_header.header("Store Activity")

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        year_selected = st.selectbox("**Year:**", [2023, 2024], index=1)
    with col2:
        day_selected = st.selectbox("**Date Index:**", range(0,13), index=0) # day 0 is the start of the main draw
    with col3:
        store_selected = st.selectbox("**Store:**", ['22B', 'Oct', 'S2', '11G'], index=3)

    dfs = [data_22B, data_Oct, data_S2, data_11G]

    all_unique = True
    for i in range(len(dfs)):
        for j in range(i + 1, len(dfs)):
            if dfs[i].equals(dfs[j]):
                all_unique = False
                print("At least two dataframes are not unique.")
    if all_unique:
        print("All dataframes are unique.")

    data_22B['STORE_NAME'] = '22B'
    data_Oct['STORE_NAME'] = 'Oct'
    data_S2['STORE_NAME'] = 'S2'
    data_11G['STORE_NAME'] = '11G'

    for df in dfs:
        df['Unmanned_High'] = df.apply(lambda x: x['ACTIVITY_LEVEL'] == 'High' and x['STATUS'] == 'Unmanned', axis=1)

    data_all = pd.concat([data_22B, data_Oct, data_S2, data_11G])

    # Change parameters here at the top

    store_name = store_selected
    date_index = day_selected
    year = year_selected

    try:
    ######################################################## TEMP DATASET CREATION FOR FIG ########################################################

        temp = data_all[ (data_all['STORE_NAME']==store_name) & (data_all['DATE_INDEX']==date_index) & (data_all['CREATED_YEAR']==year)].copy()
        temp.sort_values(['DATE_INDEX', 'WORKSTATION'], inplace=True)

        ######################################################## FIG 1 - STORE OVERALL ACTIVITY ########################################################

        mean = temp.groupby(['TIME_PARTITION'])['INVOICE_COUNT'].sum().mean()
        std = temp.groupby(['TIME_PARTITION'])['INVOICE_COUNT'].sum().std()
        low_cutoff = mean - 0.5*std
        high_cutoff = mean + 0.5*std 

        # Define color mapping function
        def activity_level_mapper(value):
            if value < low_cutoff:
                return 'low'
            elif (value > high_cutoff) and (value > 25):
                return 'high'
            else:
                return 'mid'

        actvity_levels = np.vectorize(activity_level_mapper)(temp.groupby(['TIME_PARTITION'])['INVOICE_COUNT'].sum().to_numpy())
            
        fig1 = px.histogram(temp.groupby(['TIME_PARTITION'])['INVOICE_COUNT'].sum().reset_index(), 
                            x='TIME_PARTITION', y='INVOICE_COUNT',
                            title=f"<b>Store Activity</b><br>{year} | Day {date_index} | {store_name} | {temp.WORKSTATION.unique().size} registers",
                            height=400, color=actvity_levels, barmode='relative', opacity=0.75, 
                            nbins=28, range_x=[9, 23], color_discrete_map={"Low": "lightgrey",
                                                                                "High": "gold",
                                                                                "Mid": "darkgrey"}).add_hline(
                            mean, opacity=0.25, line_dash="dot").add_hline(
                            low_cutoff, line_color='red').add_hline(
                            high_cutoff, line_color='red')

        # fig1.add_annotation(
        #     x=43,  
        #     y=temp.groupby(['CREATED_TIME_PARTITION'])['Register_Volume'].sum().max(),  
        #     text=f"Unmanned Register-Periods: {temp['Unmanned'].sum()}",  
        #     showarrow=False,
        #     font=dict(size=14),
        #     xanchor='right',
        #     yanchor='top'
        # )

        fig1.add_annotation(
            x=20,  
            y=temp.groupby(['TIME_PARTITION'])['INVOICE_COUNT'].sum().max(),  
            text=f"Total Transactions: {temp.DAILY_STORE_INVOICE_COUNT.unique()[0]}",  
            showarrow=False,
            font=dict(size=14),
            xanchor='left',
            yanchor='top'
        )

        st.plotly_chart(fig1)

        print('SUMMARY - Store')
        print("*"*30)
        print('Total # of Transactions:', temp.DAILY_STORE_INVOICE_COUNT.unique()[0])
        print("")
        print('Avg. # of Transactions per Time Period:', mean)
        print('Std. of # of Transactions per Time Period:', std)
        print('High-activity cutoff:', high_cutoff)
        print('Low-activity cutoff:', low_cutoff)
        print("*"*30)

        ######################################################## FIG 2 - ACTIVITY BY REGISTER ########################################################

        # Define color mapping function
        def activity_level_mapper_colors(value):
            if value=='Low':
                return 'lightgrey'
            elif value=='High':
                return 'gold'
            else:
                return 'darkgrey'

        fig2 = make_subplots(rows=len(temp.WORKSTATION.unique()), cols=1, shared_xaxes=True,
                            subplot_titles=temp.WORKSTATION.unique().tolist())
        i=1
        for register in temp.WORKSTATION.unique():
            subplot_data = temp[temp['WORKSTATION']==register]

            fig2.add_trace(
                go.Bar(
                    x=subplot_data.TIME_PARTITION,
                    y=subplot_data.INVOICE_COUNT,
                    name= f"Register {str(register)}",
                    marker_color=subplot_data.ACTIVITY_LEVEL.apply(activity_level_mapper_colors),
                    text=["X" if x==True else "" for x in subplot_data.Unmanned_High],
                    textposition="outside",
                ),
                row=i, col=1
            )

            fig2.add_annotation(
                x=22,  
                y=40,  
                text=f"Periods Unmanned_High: {subplot_data['Unmanned_High'].sum()}",  
                showarrow=False,
                font=dict(size=14),
                xanchor='right',
                yanchor='top',
                row=i, col=1
            )

            fig2.add_annotation(
                x=10,  
                y=40,  
                text=f"Transactions: {int(subplot_data.DAILY_STORE_INVOICE_COUNT.unique()[0])}",  
                showarrow=False,
                font=dict(size=14),
                xanchor='left',
                yanchor='top',
                row=i, col=1
            )
            
            i+=1

        fig2.update_layout(height=950//5*temp.WORKSTATION.unique().size, width=1075, showlegend=False, 
                        title_text=f"<b>Register Activity</b><br>{year} | Day {date_index} | {store_name} | {temp.WORKSTATION.unique().size} registers",)
        st.plotly_chart(fig2)

        ##########################################################################################################################

        unmanned_counts = temp.groupby('WORKSTATION')['Unmanned_High'].sum()
        unmanned_counts_by_time = temp.groupby('TIME_PARTITION')['Unmanned_High'].sum()

        print('SUMMARY - Registers')
        print("*"*30)
        print('# of Registers:', temp.WORKSTATION.unique().size)
        print('Avg. # of Transactions in Day for a Register:', temp.groupby("WORKSTATION")['INVOICE_COUNT'].sum().mean())
        print('Avg. # of Transactions per Period for a Register:', 
            (temp.groupby("WORKSTATION")['INVOICE_COUNT'].sum() / 24).mean())
        print('Avg. # of Transactions per MANNED Period for a Register:',
            (temp[temp['Unmanned_High']==False].groupby("WORKSTATION")['INVOICE_COUNT'].sum() / (24 - unmanned_counts)).mean())
        print('Avg. # of Transactions per Period per Register during high-activity periods:', 
            ((temp[temp['ACTIVITY_LEVEL']=='high'].groupby("TIME_PARTITION")['INVOICE_COUNT'].sum()) / (temp.WORKSTATION.unique().size)).mean())
        print('Avg. # of Transactions per Period per MANNED Register during high-activity periods:',
            ((temp[(temp['Unmanned_High']==False) & (temp['ACTIVITY_LEVEL']=='high')].groupby("TIME_PARTITION")['INVOICE_COUNT'].sum()) / (temp.WORKSTATION.unique().size - unmanned_counts_by_time)).mean())
        print('')
        print('Total # of Unmanned Periods:', unmanned_counts.sum())
        print('Avg. # of Unmanned Periods for a Register:', unmanned_counts.mean())
        print('Avg. %age of periods Unmanned for a Register:', (unmanned_counts/24*100).mean())
        print('Std. of # of Unmanned Periods across Registers:', unmanned_counts.std())
        print("*"*30)

        print("")
        print("**Transactions Per Period**")
        print(temp.groupby("WORKSTATION")['INVOICE_COUNT'].sum() / 24)
        print("")
        print("**Transactions Per MANNED Period**")
        print(temp[temp['Unmanned_High']==False].groupby("WORKSTATION")['INVOICE_COUNT'].sum() / (24 - unmanned_counts))

        ######################################################## NEXT SECTION ########################################################

        st.divider()
        viz_header = st.header("Unmanned Register Presence") 

        col4, col5 = st.columns([1,1])
        with col4:
            years_selected = st.multiselect("**Year:**", [2024, 2025], default=2024)
        with col5:
            days_selected = st.multiselect("**Date Index:**", range(0,13), default=range(0,13)) # day 0 is the start of the main draw
        
        stores = ['22B', 'Oct', 'S2', '11G']

        ######################################################## TEMP DATASET CREATION FOR FIG ########################################################

        for store_name in stores:

            print(f"Store: {store_name}")
            
            temp = data_all[ (data_all['STORE_NAME']==store_name) & (data_all['DATE_INDEX'].isin(days_selected)) & (data_all['CREATED_YEAR'].isin(years_selected))].copy()
            temp.sort_values(['DATE_INDEX', 'WORKSTATION'], inplace=True)
            temp['Activity_Level_High'] = temp['ACTIVITY_LEVEL'] == 'High'
            temp['Unmanned_High'] = temp['STATUS'] == 'Unmanned'
            unmanned_presence = temp.groupby(['STORE_NAME', 'DATE_INDEX', 'CREATED_YEAR', 'TIME_PARTITION'])[['Unmanned_High', 'Activity_Level_High']].max().reset_index()
            unmanned_counts = unmanned_presence.groupby(['STORE_NAME', 'DATE_INDEX', 'TIME_PARTITION'])[['Unmanned_High', 'Activity_Level_High']].sum().reset_index()
            unmanned_counts['Unmanned_High_Ratio'] = unmanned_counts['Unmanned_High'].astype(str) + ' / ' + unmanned_counts['Activity_Level_High'].astype(str)
            unmanned_counts['Unmanned_High_Ratio'] = unmanned_counts['Unmanned_High_Ratio'] + unmanned_counts['Unmanned_High_Ratio'].str[-1].eq('0').map({True: ' ✖️', False: ''})
            unmanned_counts['Unmanned_High_Ratio_Mask'] = unmanned_counts['Unmanned_High_Ratio'].eq('0 / 0 ✖️')
            
            # ------
            
            heat_df = pd.pivot_table(unmanned_counts, values='Unmanned_High', index='TIME_PARTITION', columns='DATE_INDEX')
            label_df = pd.pivot_table(unmanned_counts, values='Unmanned_High_Ratio', index='TIME_PARTITION', columns='DATE_INDEX', 
                                    aggfunc=lambda x: ' '.join(x))
            mask_df = pd.pivot_table(unmanned_counts, values='Unmanned_High_Ratio_Mask', index='TIME_PARTITION', columns='DATE_INDEX',
                                    aggfunc='any')

            # ------
            
            # Create the heatmap
            plt.figure(figsize=(12, 6))  # Adjust the figure size as needed
            sns.heatmap(heat_df, cmap='plasma', annot=label_df.values, cbar=False, vmin=0, vmax=4, fmt = '', mask=mask_df)
            
            # Label the axis
            plt.xlabel('DATE INDEX')
            plt.ylabel('CREATED_TIME_PARTITION')
            plt.title(f'Total # of Years w/ Unmanned Register for {store_name}')
            
            # Show the plot
            st.pyplot(plt,use_container_width=False)

            print("----------------------------------------------------")
            print("----------------------------------------------------")
            print("----------------------------------------------------")
            print("")
    except:
        st.error("There is no data on the filters selected")
        
        #Each cell is total number of years which had an u
        # manned register during that day/time combination across 2019, 2021, 2022, 2023. Each year can
        #contribute a maximum of 1 to this count (1 if it had any # of unmanned registers, 0 if it did not. A cell count of 4 means all 4 years had an unmanned
        #register during that day/time combination)

