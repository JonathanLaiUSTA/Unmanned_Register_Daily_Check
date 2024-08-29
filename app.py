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

st.set_page_config(layout="wide")

st.title("Unmanned Registers Daily Check")
st.write("First, execute the below query to get 4 extracts (1 for each store) from Aramark")
st.code("""
WITH
	-- The below gets invoice-level information, including year, date, time_partition, workstation, elapsed_time, basket size, and basket amount
	-- only includes non-cancelled, regular sales invoices from 2023 and 2024, between 10am to 10pm at Court 11 Store
	invoice_all AS (
		SELECT
			inv.invc_sid,
			inv.created_date,
			TO_CHAR(inv.created_date, 'YYYY') AS created_year,
			CASE
				WHEN TO_CHAR(inv.created_date, 'YYYY') = '2023' THEN (TRUNC(inv.created_date) - TO_DATE('2023-08-28', 'yyyy-mm-dd')) 
				WHEN TO_CHAR(inv.created_date, 'YYYY') = '2024' THEN (TRUNC(inv.created_date) - TO_DATE('2024-08-26', 'yyyy-mm-dd'))
				END AS date_index,
			CASE
				WHEN TO_NUMBER(TO_CHAR(inv.created_date, 'MI')) > 30 
				THEN TO_NUMBER(TO_CHAR(inv.created_date, 'HH24')) + 0.5
				ELSE TO_NUMBER(TO_CHAR(inv.created_date, 'HH24'))
				END AS time_partition,
			inv.workstation,
			LEAST(inv.elapsed_time, 300) AS elapsed_time,																							-- ADJUST ELAPSED_TIME CAP HERE
			SUM(item.qty) AS basket_size,
			SUM((COALESCE(item.price, item.orig_price) + COALESCE(item.tax_amt, item.orig_tax_amt)) * item.qty) AS basket_amt
		FROM cms.invoice_v inv
		LEFT JOIN cms.store_v str 
			ON inv.store_no = str.store_no 
			AND inv.sbs_no = str.sbs_no
		LEFT JOIN cms.invc_item_v item
			ON inv.invc_sid = item.invc_sid
		WHERE 1=1
			AND str.store_name = 'US OPEN Tennis Championships - 11G'                                           -- SWAP HERE -----------------------------------------------------------------------------
--			AND str.store_name = 'US OPEN Tennis Championships - S2'                                            -- SWAP HERE -----------------------------------------------------------------------------
--			AND str.store_name = 'US OPEN Tennis Championships- OCT'                                            -- SWAP HERE -----------------------------------------------------------------------------
--			AND str.store_name = 'US OPEN Tennis Championships - 22B'                                           -- SWAP HERE -----------------------------------------------------------------------------
			AND ((inv.created_date >= TO_DATE('2023-08-21', 'yyyy-mm-dd') AND (inv.created_date <= TO_DATE('2023-09-11', 'yyyy-mm-dd')))			-- days -7 through 14 FOR 2023
				OR (inv.created_date >= TO_DATE('2024-08-18', 'yyyy-mm-dd') AND (inv.created_date <= TO_DATE('2024-09-9', 'yyyy-mm-dd')))			-- days -8 through 14 FOR 2024
                                )
			AND TO_CHAR(inv.created_date, 'HH24:MI') BETWEEN '10:00' AND '22:00'																	-- 10am until 10pm
			AND inv.invc_type = 0																													-- standard sales invoices
			AND inv.status = 0																														-- non-cancelled invoices
		GROUP BY 
			inv.invc_sid,
			inv.created_date,
			TO_CHAR(inv.created_date, 'YYYY'), -- created_year
			inv.workstation,
			elapsed_time
		HAVING SUM(item.qty) > 0																													-- remove strange return/exchange invoices that persist
		ORDER BY inv.created_date
	),
	-- the below contains register volumes by year/date/time/workstation
	-- NOTE: When generalizing this SQL query to include other stores, will  need to revisit some of the logic in creating the baseplate (cross joins)
	register_volumes_ydtw AS (
		SELECT -- 2023 baseplate
			cy.created_year,
			di.date_index,
			tp.time_partition,
			w.workstation,
			COUNT(inv_a.invc_sid) AS invoice_count_ydtw,
			CASE WHEN SUM(inv_a.elapsed_time) IS NOT NULL THEN SUM(inv_a.elapsed_time) ELSE 0 END AS elapsed_time_ydtw,
			CASE WHEN SUM(inv_a.basket_size) IS NOT NULL THEN SUM(inv_a.basket_size) ELSE 0 END AS qty_items_ydtw,
			CASE WHEN SUM(inv_a.basket_amt) IS NOT NULL THEN SUM(inv_a.basket_amt) ELSE 0 END AS sales_ydtw
		FROM (SELECT DISTINCT invoice_all.created_year FROM invoice_all WHERE invoice_all.created_year = '2023') cy
		CROSS JOIN (SELECT DISTINCT invoice_all.date_index FROM invoice_all) di
		CROSS JOIN (SELECT DISTINCT invoice_all.time_partition FROM invoice_all) tp
		CROSS JOIN (SELECT DISTINCT invoice_all.workstation FROM invoice_all WHERE invoice_all.created_year = '2023') w
		LEFT JOIN invoice_all inv_a 
			ON inv_a.created_year = cy.created_year
			AND inv_a.date_index = di.date_index
			AND inv_a.time_partition = tp.time_partition
			AND inv_a.workstation = w.workstation
		GROUP BY
			cy.created_year,
			di.date_index,
			tp.time_partition,
			w.workstation
		UNION -- 2024 prior days baseplate
		SELECT
			cy.created_year,
			di.date_index,
			tp.time_partition,
			w.workstation,
			COUNT(inv_a.invc_sid) AS invoice_count_ydtw,
			CASE WHEN SUM(inv_a.elapsed_time) IS NOT NULL THEN SUM(inv_a.elapsed_time) ELSE 0 END AS elapsed_time_ydtw,
			CASE WHEN SUM(inv_a.basket_size) IS NOT NULL THEN SUM(inv_a.basket_size) ELSE 0 END AS qty_items_ydtw,
			CASE WHEN SUM(inv_a.basket_amt) IS NOT NULL THEN SUM(inv_a.basket_amt) ELSE 0 END AS sales_ydtw
		FROM (SELECT DISTINCT invoice_all.created_year FROM invoice_all WHERE invoice_all.created_year = '2024') cy
		CROSS JOIN (SELECT DISTINCT invoice_all.date_index FROM invoice_all WHERE invoice_all.date_index < (SELECT MAX(invoice_all.date_index) 
																											FROM invoice_all 
																											WHERE invoice_all.created_year = '2024')) di
		CROSS JOIN (SELECT DISTINCT invoice_all.time_partition FROM invoice_all) tp
		CROSS JOIN (SELECT DISTINCT invoice_all.workstation FROM invoice_all WHERE invoice_all.created_year = '2024') w
		LEFT JOIN invoice_all inv_a 
			ON inv_a.created_year = cy.created_year
			AND inv_a.date_index = di.date_index
			AND inv_a.time_partition = tp.time_partition
			AND inv_a.workstation = w.workstation
		GROUP BY
			cy.created_year,
			di.date_index,
			tp.time_partition,
			w.workstation
		UNION -- 2024 current day baseplate (so as to not create blank rows past the current time partition in the current day)
		SELECT
			cy.created_year,
			di.date_index,
			tp.time_partition,
			w.workstation,
			COUNT(inv_a.invc_sid) AS invoice_count_ydtw,
			CASE WHEN SUM(inv_a.elapsed_time) IS NOT NULL THEN SUM(inv_a.elapsed_time) ELSE 0 END AS elapsed_time_ydtw,
			CASE WHEN SUM(inv_a.basket_size) IS NOT NULL THEN SUM(inv_a.basket_size) ELSE 0 END AS qty_items_ydtw,
			CASE WHEN SUM(inv_a.basket_amt) IS NOT NULL THEN SUM(inv_a.basket_amt) ELSE 0 END AS sales_ydtw
		FROM (SELECT DISTINCT invoice_all.created_year FROM invoice_all WHERE invoice_all.created_year = '2024') cy
		CROSS JOIN (SELECT MAX(invoice_all.date_index) AS date_index FROM invoice_all WHERE invoice_all.created_year = '2024') di
		CROSS JOIN (SELECT DISTINCT invoice_all.time_partition FROM invoice_all WHERE invoice_all.date_index = (SELECT MAX(invoice_all.date_index) 
																												FROM invoice_all 
																												WHERE invoice_all.created_year = '2024')
																				AND invoice_all.created_year = '2024') tp
		CROSS JOIN (SELECT DISTINCT invoice_all.workstation FROM invoice_all WHERE invoice_all.created_year = '2024') w
		LEFT JOIN invoice_all inv_a 
			ON inv_a.created_year = cy.created_year
			AND inv_a.date_index = di.date_index
			AND inv_a.time_partition = tp.time_partition
			AND inv_a.workstation = w.workstation
		GROUP BY
			cy.created_year,
			di.date_index,
			tp.time_partition,
			w.workstation
	),
	-- the below contains register volumes by year/date/time
	register_volumes_ydt AS (
		SELECT
			ydtw.created_year,
			ydtw.date_index,
			ydtw.time_partition,
			SUM(ydtw.invoice_count_ydtw) AS invoice_count_ydt,
			SUM(ydtw.elapsed_time_ydtw) AS elapsed_time_ydt,
			SUM(ydtw.qty_items_ydtw) AS qty_items_ydt,
			SUM(ydtw.sales_ydtw) AS sales_ydt
		FROM register_volumes_ydtw ydtw
		GROUP BY 
			ydtw.created_year, 
			ydtw.date_index, 
			ydtw.time_partition
	),
	-- the below contains register volumes by year/date
	register_volumes_yd AS (
		SELECT 
			ydt.created_year,
			ydt.date_index,
			SUM(ydt.invoice_count_ydt) AS invoice_count_yd,
			SUM(ydt.elapsed_time_ydt) AS elapsed_time_yd,
			SUM(ydt.qty_items_ydt) AS qty_items_yd,
			SUM(ydt.sales_ydt) AS sales_yd,
			AVG(ydt.invoice_count_ydt) AS avg_invoice_count_per_time,
			STDDEV(ydt.invoice_count_ydt) AS std_invoice_count_across_times,
			AVG(ydt.invoice_count_ydt) - 0.5*STDDEV(ydt.invoice_count_ydt) AS activity_level_cutoff_low,
			AVG(ydt.invoice_count_ydt) + 0.5*STDDEV(ydt.invoice_count_ydt) AS activity_level_cutoff_high
		FROM register_volumes_ydt ydt
		GROUP BY 
			ydt.created_year, 
			ydt.date_index
	),
	-- the below contains Activity Level classifications by year/date/time
	activity_levels AS (
		SELECT 
			ydt.created_year,
			ydt.date_index,
			ydt.time_partition,
--			ydt.invoice_count_ydt,
--			yd.activity_level_cutoff_low,
--			yd.activity_level_cutoff_high,
			CASE
				WHEN ydt.invoice_count_ydt >= 25 AND ydt.invoice_count_ydt >= yd.activity_level_cutoff_high
					THEN 'High'
				WHEN ydt.invoice_count_ydt < yd.activity_level_cutoff_low
					THEN 'Low'
				ELSE 'Mid'
				END AS activity_level
		FROM register_volumes_ydt ydt
		LEFT JOIN register_volumes_yd yd
			ON ydt.created_year = yd.created_year
			AND ydt.date_index = yd.date_index
	),
	-- the below contains Manned/Unmanned status by year/date/time/workstation
	master AS (
		SELECT 
			ydtw.created_year,
			ydtw.date_index,
			ydtw.time_partition,
			ydtw.workstation,
			CASE
				WHEN ydtw.workstation = 11 AND ydtw.created_year = '2024' 								-- ADJUST FRICTIONLESS REGISTER WORKSTATION ID HERE
					THEN 'Frictionless'
				ELSE 'Standard'
				END AS workstation_type,
			ydtw.invoice_count_ydtw,
			ydtw.elapsed_time_ydtw,
			ydtw.qty_items_ydtw,
			ydtw.sales_ydtw,
			al.activity_level,
			CASE 
				WHEN al.activity_level = 'High' AND ydtw.invoice_count_ydtw = 0 AND (CASE
																						WHEN ydtw.workstation = 11 AND ydtw.created_year = '2024'
																							THEN 'Frictionless'
																						ELSE 'Standard' END) = 'Standard' 
					THEN 'Unmanned'
				ELSE 'Manned' END AS status
		FROM register_volumes_ydtw ydtw
		LEFT JOIN activity_levels al
			ON ydtw.created_year = al.created_year
			AND ydtw.date_index = al.date_index
			AND ydtw.time_partition = al.time_partition
	)
-- invoice_all, register_volumes_ydtw, register_volumes_ydt, register_volumes_yd, activity_levels (ydt), master (ydtw)
SELECT 
	m.created_year,
	m.date_index,
	m.time_partition,
	m.workstation,
	m.workstation_type,
	m.invoice_count_ydtw AS invoice_count,
	m.elapsed_time_ydtw AS transactions_time,
	m.qty_items_ydtw AS qty_items_sold,
	m.sales_ydtw AS total_sales,
	m.activity_level,
	m.status,
	yd.invoice_count_yd AS daily_store_invoice_count
FROM master m
LEFT JOIN register_volumes_yd yd
	ON m.created_year = yd.created_year
	AND m.date_index = yd.date_index
ORDER BY 
	created_year DESC, 
	date_index DESC, 
	time_partition DESC, 
	workstation ASC
""", language='plsql')

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

