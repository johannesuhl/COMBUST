# -*- coding: utf-8 -*-
"""
Created on Tue Feb  9 05:11:03 2021

@author: Johannes
"""
import os,sys
import pandas as pd
import scipy.stats
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
#####################################    
nbu_lu_csv='not_built-up_landuses.csv'
lu_lookup_csv='lu_lookup.csv'
lu_matcomp_csv='lu_material_composition_small.csv'
template_raster = r'H:\BU_RASTER_CREATION\ALL\V3_SD_SUBMISSION_DATA\UPLOAD\FBUY\data\FBUY.tif' ### template  
popcsv=r'F:\URBAN_SCALING_ROADNETWORKS_USC\all_county_census_MSA.csv'  ## to get test counties      

infolder=r'F:\ZTRAX_2021\ZTRAX_CSV_COUNTY_RELEVANT_ATTRIBUTES_RL3_imp_indoor_area'
outfolder=r'F:\ZTRAX_2021\ZTRAX_CSV_COUNTY_RELEVANT_ATTRIBUTES_RL4_imp_indoor_area_combmass'

area_attribute='BuildingAreaSqFt_imp_lu_median'
xcoo_col = 'PropertyAddressLongitude'
ycoo_col = 'PropertyAddressLatitude'

#Material	R (MJ/kg) #calorific_value 
r_dict={'Wood':15.72,
    'Plastic':35.27,
    'Paper':15.63,
    'Cloth':21.15,
    'Asphalt':34.05}             

lu_lookup_df=pd.read_csv(lu_lookup_csv)
lu_lookup_dict=dict(zip(list(lu_lookup_df.ZTRAX_LU1.values),list(lu_lookup_df.TARGET.values)))
material_lookupdf=pd.read_csv(lu_matcomp_csv)   
nbu_lu_df=pd.read_csv(nbu_lu_csv)
exclude_lutypes=nbu_lu_df[nbu_lu_df.is_builtup=='n']['StndCode'].values

counter=0
for csv in os.listdir(infolder):
    
    #if counter<=1493:
    #    continue
    if 'zip' in csv:
        continue
    
    currfips=csv.split('_')[-6]
    #if not currfips in rel_counties:
    #    continue
    #sys.exit(0)
    ###########################
    #if not int(currfips) in [22017,39127,47011,48471,31021,42133]:
    #    continue
    ###########################   

    counter+=1
    print(csv)
    indf_all = pd.read_csv(infolder+os.sep+csv)
    
    try:
        indf_all = indf_all.replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
    except:
        if not 'PropertyLandUseStndCode' in indf_all.columns:
            indf_all['PropertyLandUseStndCode']='RR101'
              
    #### exclude nbu land uses: ##########
    indf=indf_all[np.logical_not(indf_all.PropertyLandUseStndCode.isin(exclude_lutypes))]                        
    ######################################
    
    if not indf.empty:       
        indf['bui_sqm']=indf[area_attribute]*0.09290304
        indf['lu_superclass']=indf.PropertyLandUseStndCode.str.slice(0 ,2)
        indf['lu_superclass_mapped']=indf.lu_superclass.map(lu_lookup_dict)
        indf=indf.merge(material_lookupdf,left_on='lu_superclass_mapped',right_on='Label',how='left')    
        #FLD [MJ/sqm] times area = fuel energy
        #indf['fuel_energy_MJ']=indf.bui_sqm*indf.FLD_val
        indf['fuel_energy_MJ']=indf.bui_sqm*indf.FLD_val_frishcosy        
        
        cols_to_add=[]
        for material in list(r_dict.keys()):
            currcol='combust_mat_mass_%s' %material
            indf[currcol]=indf[material]*indf.fuel_energy_MJ/float(r_dict[material])
            cols_to_add.append(currcol)
        indf['combust_mat_mass_TOTAL']=np.sum(indf[cols_to_add],axis=1)    
   
    indf.to_csv(outfolder+os.sep+csv.replace('.csv','_wCombMass.csv'),index=False)
    print(counter,csv,len(indf_all),len(indf))
    
