# -*- coding: utf-8 -*-
"""
Created on Thu Mar 11 03:36:35 2021

@author: Johannes
"""

import os,sys
import pandas as pd
import scipy.stats
import geopandas as gp
from osgeo import gdal
import subprocess
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import matplotlib
matplotlib.rcParams['font.sans-serif'] = "Arial"
matplotlib.rcParams['font.family'] = "sans-serif"

#####################################    
infolder=r'F:\ZTRAX_2021\ZTRAX_CSV_COUNTY_RELEVANT_ATTRIBUTES_RL2_adj_indoor_area'    
outfolder=r'F:\ZTRAX_2021\ZTRAX_CSV_COUNTY_RELEVANT_ATTRIBUTES_RL3_imp_indoor_area'  
plotdir=r'H:\ZTRAX_surfaces_2022\plots'   

lus=['AG','CM','CO','CR','EI','GV','HI','IH','IN','MS','PP','RC','RI','RR','TR','VL']

county_level_miss_stats=False
county_level_miss_maps=False
get_mean_medians=False
impute_areas=True # impute just conus means. works better.
impute_areas_support_adaptive=False ### starting from county to state to conus, but not always working.

if county_level_miss_stats:
    import os,sys
    import pandas as pd
    import scipy.stats
    import geopandas as gp
    from osgeo import gdal
    import subprocess
    import time
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    #####################################    
    xcoo_col = 'PropertyAddressLongitude'
    ycoo_col = 'PropertyAddressLatitude' 
    counter=0
    compl_stats=[]
    for csv in os.listdir(infolder):

        counter+=1
        
        #if counter<=1493:
        #    continue
        if 'zip' in csv:
            continue
        county=csv.split('_')[-4]
        indf_all = pd.read_csv(infolder+os.sep+csv)
        total=len(indf_all)  
        byvalids=indf_all[indf_all['YearBuilt']>0]
        bymiss=total-len(byvalids)
        geovalids=indf_all[np.logical_and(indf_all[xcoo_col]<0,indf_all[ycoo_col]>0)]
        geomiss=total-len(geovalids)
        if not 'PropertyLandUseStndCode' in  indf_all.columns:
            lumiss=total
        else:
            indf_all.PropertyLandUseStndCode = indf_all.PropertyLandUseStndCode.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
            geovalids.PropertyLandUseStndCode = geovalids.PropertyLandUseStndCode.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)            
            lumiss=len(indf_all[indf_all.PropertyLandUseStndCode.isnull()])
            lumiss_geovalid_only=len(geovalids[geovalids.PropertyLandUseStndCode.isnull()])
        if not 'BuildingAreaSqFt' in  indf_all.columns:
            areamiss=total
        else:
            indf_all.BuildingAreaSqFt = indf_all.BuildingAreaSqFt.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
            geovalids.BuildingAreaSqFt = geovalids.BuildingAreaSqFt.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)            
            areamiss=len(indf_all[indf_all.BuildingAreaSqFt.isnull()])
            areamiss_geovalid_only=len(geovalids[geovalids.BuildingAreaSqFt.isnull()])
            
        print(counter,county,total,bymiss,geomiss,areamiss,lumiss,areamiss_geovalid_only,lumiss_geovalid_only)  
        compl_stats.append([county,total,bymiss,geomiss,areamiss,lumiss,areamiss_geovalid_only,lumiss_geovalid_only])
    compl_statsdf=pd.DataFrame(compl_stats)
    compl_statsdf.columns=['county','total','bymiss','geomiss','areamiss','lumiss','areamiss_geovalid_only','lumiss_geovalid_only']
    compl_statsdf.to_csv('ztrax_county_completeness2022.csv',index=False)
    
if county_level_miss_maps:
    import geopandas as gpd
    import matplotlib.pyplot as plt
    
    county_shp=r'F:\TINY_TOWNS_2019\counties_2015\us_county_2015_5m_lower48.shp'
    states_shp=r'F:\TINY_TOWNS_2019\states\cb_2014_us_state_500k_albers_lower48.shp'
    county_gdf = gpd.read_file(county_shp)
    state_gdf = gpd.read_file(states_shp)
    missdf=pd.read_csv('ztrax_county_completeness2022.csv')
    missdf.county=missdf.county.map(str).str.zfill(5)
    missdf['geovalid_only']=missdf.total.values-missdf.geomiss.values
    missdf['geo_compl_perc']=100*(np.divide(missdf.total.values-missdf.geomiss.values,missdf.total.values.astype(np.float)))
    missdf['by_compl_perc']=100*(np.divide(missdf.total.values-missdf.bymiss.values,missdf.total.values.astype(np.float)))
    missdf['area_compl_perc']=100*(np.divide(missdf.total.values-missdf.areamiss.values,missdf.total.values.astype(np.float)))
    missdf['lu_compl_perc']=100*(np.divide(missdf.total.values-missdf.lumiss.values,missdf.total.values.astype(np.float)))
    missdf['area_compl_perc_geovalid_only']=100*(np.divide(missdf.geovalid_only.values-missdf.areamiss_geovalid_only.values,missdf.geovalid_only.values.astype(np.float)))
    missdf['lu_compl_perc_geovalid_only']=100*(np.divide(missdf.geovalid_only.values-missdf.lumiss_geovalid_only.values,missdf.geovalid_only.values.astype(np.float)))
    missdf['total_count']=missdf.total
    
    county_gdf=county_gdf.merge(missdf,left_on='GEOID',right_on='county',how='left')
    plotcols=['total_count','by_compl_perc','geo_compl_perc','area_compl_perc','lu_compl_perc']#,'area_compl_perc_geovalid_only','lu_compl_perc_geovalid_only']
    figsize = (16, 10)
    colors = 10
    cmap='Greens'    
                
    for plotcol in plotcols: 
        #county_gdf=county_gdf[county_gdf[plotcol]>0]
        county_gdf[plotcol]=county_gdf[plotcol].replace(np.inf,np.nan).fillna(0)
        
        county_gdf['%s_cl' %plotcol]=pd.cut(county_gdf[plotcol],10,labels=False)
        county_gdf['%s_cl' %plotcol]=10*(1+county_gdf['%s_cl' %plotcol])
        print(plotcol)        
        fig,ax=plt.subplots()
        ax = state_gdf.plot(facecolor="black", edgecolor="black",figsize=figsize)            
        cbarticks=[0,100]
        if not plotcol=='total_count':
            plotdf=county_gdf[county_gdf['total_count']>0]
            plotdf.plot(column='%s_cl' %plotcol, categorical=True, cmap=cmap, legend=True,ax=ax,legend_kwds={'loc': "lower left",'fontsize': "large"})# , 'shrink':0.4, "pad":0.02, "ticks":cbarticks})# legend_kwds={'labels':}            
            #ax.set_title('ZTRAX completeness [%%], %s' %plotcol, fontdict={'fontsize': 20}, loc='center')
        else:
            continue
            bins=pd.qcut(county_gdf[plotcol],100,retbins=True)
            bindf=pd.DataFrame(bins[1])
            bindf.columns=['binlabel']
            bindf['idx']=bindf.index
            county_gdf['%s_cl' %plotcol]=pd.qcut(county_gdf[plotcol],100,labels=False)
            county_gdf=county_gdf.merge(bindf,left_on='%s_cl' %plotcol,right_on='idx',how='left')
            county_gdf.plot(column=plotcol, scheme='Quantiles',k=10,categorical=False, cmap='viridis', legend=True,ax=ax,legend_kwds={'loc': "lower left",'fontsize': "large"})#legend_kwds={'loc': "lower left",'fontsize': "large"})# , 'shrink':0.4, "pad":0.02, "ticks":cbarticks})# legend_kwds={'labels':}            
            #ax.set_title('ZTRAX records per county', fontdict={'fontsize': 20}, loc='center')
        state_gdf.plot(facecolor='none', edgecolor="white",ax=ax)            
        
        ax.set_axis_off()            
        ax.set_xlim([-2356398, 2258351])
        ax.set_ylim([269249, 3172999])            
        #plt.legend()
        #ax.get_legend().set_bbox_to_anchor((.12, .4))
        fig = ax.get_figure()             
        plt.tight_layout(pad=0.2)
        fig.savefig(plotdir+os.sep+'countymap_%s.png' %(plotcol),dpi=150)
        plt.clf()
        plt.show()
        
    
if get_mean_medians:    
    counter=0
    outstats=[]
    not_imputable_counties=[]
    for csv in os.listdir(infolder):
        counter+=1        
        if 'zip' in csv:
            continue
        county=csv.split('_')[-4]
        indf_all = pd.read_csv(infolder+os.sep+csv)
        if not 'PropertyLandUseStndCode' in  indf_all.columns:
            not_imputable_counties.append(county)
            continue
        if not 'BuildingAreaSqFt' in  indf_all.columns:
            not_imputable_counties.append(county)
            continue 
        indf_all=indf_all.dropna(subset=['PropertyLandUseStndCode'])
        if len(indf_all)==0:
            not_imputable_counties.append(county)
            continue         
        indf_all['lu_superclass']=indf_all.PropertyLandUseStndCode.str.slice(0,2)
        indf_all.BuildingAreaSqFt = indf_all.BuildingAreaSqFt.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
        indf_all=indf_all.dropna(subset=['BuildingAreaSqFt'])
        curr_mean_areas=[]
        curr_median_areas=[]
        curr_support=[]
        for lu in lus:
            ludf=indf_all[indf_all.lu_superclass==lu]
            curr_support.append(len(ludf))
            curr_mean_areas.append(np.nanmean(ludf.BuildingAreaSqFt.values))
            curr_median_areas.append(np.nanmedian(ludf.BuildingAreaSqFt.values))        
        outstats.append([county]+curr_support+curr_mean_areas+curr_median_areas)                  
        print(counter,county,[county]+curr_support+curr_mean_areas+curr_median_areas)  
    outstatsdf=pd.DataFrame(outstats)
    cols=['county']+['support_%s' %x for x in lus]+['areamean_%s' %x for x in lus]+['areamedian_%s' %x for x in lus]
    outstatsdf.columns=cols
    outstatsdf.to_csv('area_imputation_data.csv',index=False)
    not_imputable_countiesdf=pd.DataFrame()
    not_imputable_countiesdf['not_imputable_counties']=not_imputable_counties
    not_imputable_countiesdf.to_csv('not_imputable_counties.csv',index=False)

if impute_areas:
    area_imputation_county_df=pd.read_csv('area_imputation_data.csv')
    not_imputable_countiesdf=pd.read_csv('not_imputable_counties.csv')
    
    area_imputation_county_df['state']=area_imputation_county_df.county.map(str).str.zfill(5).str.slice(0,2)
    
    sum_columns=[x for x in area_imputation_county_df.columns if 'support' in x]
    mean_columns=[x for x in area_imputation_county_df.columns if 'mean' in x]
    median_columns=[x for x in area_imputation_county_df.columns if 'median' in x]
    
    state_supportdf = area_imputation_county_df.groupby('state')[sum_columns].sum().reset_index()
    state_meandf = area_imputation_county_df.groupby('state')[mean_columns].mean().reset_index()
    state_mediandf = area_imputation_county_df.groupby('state')[median_columns].median().reset_index()
    
    us_supportdf = area_imputation_county_df[sum_columns].sum().reset_index()
    us_meandf = area_imputation_county_df[mean_columns].mean().reset_index()
    us_mediandf = area_imputation_county_df[median_columns].median().reset_index()
    us_supportdf.columns=['stat_lu','value']
    us_meandf.columns=['stat_lu','value']
    us_mediandf.columns=['stat_lu','value']
    
    not_imputable_counties=not_imputable_countiesdf.not_imputable_counties.values
    
    counter=0
    for csv in os.listdir(infolder):
        counter+=1        
        if 'zip' in csv:
            continue
        county=csv.split('_')[-4]
        state=county[:2]
        
        #if int(county) in not_imputable_counties:
        #    pass
        #else:
        #if counter<277:
        #    continue
        #if county!='47011':
        #    continue
        #sys.exit(0)
        ###########################
        #if not int(county) in [22017,39127,47011,48471,31021,42133]:
        #    continue
        ###########################        
            
        indf_all = pd.read_csv(infolder+os.sep+csv)
        
        if not 'PropertyLandUseStndCode' in indf_all.columns:
            indf_all['PropertyLandUseStndCode']=='RR101'
        #if indf_all.PropertyLandUseStndCode.unique().shape[0]==1:# and np.isnan(indf_all.PropertyLandUseStndCode.unique()[0]):
        indf_all.PropertyLandUseStndCode = indf_all.PropertyLandUseStndCode.fillna('RR101')    
        
        indf_all['lu_superclass']=indf_all.PropertyLandUseStndCode.map(str).str.slice(0,2)

        try:
            indf_all.BuildingAreaSqFt = indf_all.BuildingAreaSqFt.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
        except:
            indf_all['BuildingAreaSqFt']=np.nan
        
        indf_all['BuildingAreaSqFt_imp_lu_mean']=0
        indf_all['BuildingAreaSqFt_imp_lu_median']=0
        indf_all['BuildingAreaSqFt_imp_lu_support']=0
        indf_all['BuildingAreaSqFt_imp_lu_sourcelevel']=0
        for lu in lus:
            curr_support=us_supportdf[us_supportdf.stat_lu=='support_%s' %lu].value.values[0]
            curr_mean=us_meandf[us_meandf.stat_lu=='areamean_%s' %lu].value.values[0]
            curr_median=us_mediandf[us_mediandf.stat_lu=='areamedian_%s' %lu].value.values[0]
            indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_mean']=curr_mean
            indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_median']=curr_median
            indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_support']=curr_support
            indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_sourcelevel']='country'                         
    #sys.exit(0)
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_mean']=indf_all.loc[indf_all.BuildingAreaSqFt!=np.nan]['BuildingAreaSqFt']
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_median']=indf_all.loc[indf_all.BuildingAreaSqFt!=np.nan]['BuildingAreaSqFt']
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_support']=0
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_sourcelevel']='not_imputed'                         
                     
        outfile=outfolder+os.sep+csv.replace('.csv','_imputed_bldgarea.csv')
        indf_all.to_csv(outfile,index=False)
        print(counter,csv)
        #sys.exit(0)  
        
if impute_areas_support_adaptive:
    area_imputation_county_df=pd.read_csv('area_imputation_data.csv')
    not_imputable_countiesdf=pd.read_csv('not_imputable_counties.csv')
    
    area_imputation_county_df['state']=area_imputation_county_df.county.map(str).str.zfill(5).str.slice(0,2)
    
    sum_columns=[x for x in area_imputation_county_df.columns if 'support' in x]
    mean_columns=[x for x in area_imputation_county_df.columns if 'mean' in x]
    median_columns=[x for x in area_imputation_county_df.columns if 'median' in x]
    
    state_supportdf = area_imputation_county_df.groupby('state')[sum_columns].sum().reset_index()
    state_meandf = area_imputation_county_df.groupby('state')[mean_columns].mean().reset_index()
    state_mediandf = area_imputation_county_df.groupby('state')[median_columns].median().reset_index()
    
    us_supportdf = area_imputation_county_df[sum_columns].sum().reset_index()
    us_meandf = area_imputation_county_df[mean_columns].mean().reset_index()
    us_mediandf = area_imputation_county_df[median_columns].median().reset_index()
    us_supportdf.columns=['stat_lu','value']
    us_meandf.columns=['stat_lu','value']
    us_mediandf.columns=['stat_lu','value']
    
    not_imputable_counties=not_imputable_countiesdf.not_imputable_counties.values
    
    counter=0
    for csv in os.listdir(infolder):
        counter+=1        
        if 'zip' in csv:
            continue
        county=csv.split('_')[-4]
        state=county[:2]
        
        #if int(county) in not_imputable_counties:
        #    pass
        #else:
        #if counter<277:
        #    continue
        #if county!='47011':
        #    continue
        #sys.exit(0)
        ###########################
        #if not int(county) in [22017,39127,47011,48471,31021,42133]:
        #    continue
        ###########################        
            
        indf_all = pd.read_csv(infolder+os.sep+csv)
        
        if not 'PropertyLandUseStndCode' in indf_all.columns:
            indf_all['PropertyLandUseStndCode']=='RR101'
        #if indf_all.PropertyLandUseStndCode.unique().shape[0]==1:# and np.isnan(indf_all.PropertyLandUseStndCode.unique()[0]):
        indf_all.PropertyLandUseStndCode = indf_all.PropertyLandUseStndCode.fillna('RR101')    
        
        indf_all['lu_superclass']=indf_all.PropertyLandUseStndCode.map(str).str.slice(0,2)

        try:
            indf_all.BuildingAreaSqFt = indf_all.BuildingAreaSqFt.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
        except:
            indf_all['BuildingAreaSqFt']=np.nan
        
        indf_all['BuildingAreaSqFt_imp_lu_mean']=0
        indf_all['BuildingAreaSqFt_imp_lu_median']=0
        indf_all['BuildingAreaSqFt_imp_lu_support']=0
        indf_all['BuildingAreaSqFt_imp_lu_sourcelevel']=0
        for lu in lus:
            if not int(county) in not_imputable_counties: 
                curr_support=area_imputation_county_df[area_imputation_county_df.county==int(county)]['support_%s' %lu].values[0]
                curr_mean=area_imputation_county_df[area_imputation_county_df.county==int(county)]['areamean_%s' %lu].values[0]
                curr_median=area_imputation_county_df[area_imputation_county_df.county==int(county)]['areamedian_%s' %lu].values[0]
                if curr_support>100 and curr_mean!=np.nan and curr_median!=np.nan:              
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_mean']=curr_mean
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_median']=curr_median
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_support']=curr_support
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_sourcelevel']='county'
                else:
                    curr_support=state_supportdf[state_supportdf.state==state]['support_%s' %lu].values[0]
                    curr_mean=state_meandf[state_meandf.state==state]['areamean_%s' %lu].values[0]
                    curr_median=state_mediandf[state_mediandf.state==state]['areamedian_%s' %lu].values[0]
                    if curr_support>100 and curr_mean!=np.nan and curr_median!=np.nan:              
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_mean']=curr_mean
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_median']=curr_median
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_support']=curr_support 
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_sourcelevel']='state'
                    else:
                        curr_support=us_supportdf[us_supportdf.stat_lu=='support_%s' %lu].value.values[0]
                        curr_mean=us_meandf[us_meandf.stat_lu=='areamean_%s' %lu].value.values[0]
                        curr_median=us_mediandf[us_mediandf.stat_lu=='areamedian_%s' %lu].value.values[0]
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_mean']=curr_mean
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_median']=curr_median
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_support']=curr_support
                        indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_sourcelevel']='country'                         
            else:
                curr_support=state_supportdf[state_supportdf.state==state]['support_%s' %lu].values[0]
                curr_mean=state_meandf[state_meandf.state==state]['areamean_%s' %lu].values[0]
                curr_median=state_mediandf[state_mediandf.state==state]['areamedian_%s' %lu].values[0]
                if curr_support>100 and curr_mean!=np.nan and curr_median!=np.nan:              
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_mean']=curr_mean
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_median']=curr_median
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_support']=curr_support 
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_sourcelevel']='state'
                else:
                    curr_support=us_supportdf[us_supportdf.stat_lu=='support_%s' %lu].value.values[0]
                    curr_mean=us_meandf[us_meandf.stat_lu=='areamean_%s' %lu].value.values[0]
                    curr_median=us_mediandf[us_mediandf.stat_lu=='areamedian_%s' %lu].value.values[0]
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_mean']=curr_mean
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_median']=curr_median
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_support']=curr_support
                    indf_all.loc[np.logical_and(indf_all.BuildingAreaSqFt.isnull(),indf_all.lu_superclass==lu),'BuildingAreaSqFt_imp_lu_sourcelevel']='country'                         
            #sys.exit(0)
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_mean']=indf_all.loc[indf_all.BuildingAreaSqFt!=np.nan]['BuildingAreaSqFt']
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_median']=indf_all.loc[indf_all.BuildingAreaSqFt!=np.nan]['BuildingAreaSqFt']
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_support']=0
        indf_all.loc[np.logical_not(indf_all.BuildingAreaSqFt.isnull()),'BuildingAreaSqFt_imp_lu_sourcelevel']='not_imputed'                         
                     
        outfile=outfolder+os.sep+csv.replace('.csv','_imputed_bldgarea.csv')
        indf_all.to_csv(outfile,index=False)
        print(counter,csv)
        #sys.exit(0)  
            
    
    
    
    