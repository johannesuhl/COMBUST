# -*- coding: utf-8 -*-
"""
Created on Tue Feb  9 05:11:03 2021

@author: Johannes
"""
import pandas as pd
import geopandas as gp    
import os,sys
import numpy as np

do_raster_multitemp=False
incr2cum=False 
do_contemp_layer=False
do_raster_components=False
do_raster_components_proportions=False
do_temporal_metrics=False
prepare_data_submission=True
validate=False

import os,sys
import pandas as pd
import scipy.stats
import geopandas as gp
from osgeo import gdal
#from gdalconst import GA_ReadOnly
import subprocess
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
#####################################    

template_raster = r'H:\BU_RASTER_CREATION\ALL\V3_SD_SUBMISSION_DATA\UPLOAD\FBUY\data\FBUY.tif' ### template  
infolder=r'F:\ZTRAX_2021\ZTRAX_CSV_COUNTY_RELEVANT_ATTRIBUTES_RL4_imp_indoor_area_combmass'
area_attribute='BuildingAreaSqFt_imp_lu_mean'
surface_folder = r'H:\ZTRAX_surfaces_2022\surfaces_fuel'
#bitdepth = gdal.GDT_Float32 ## or gdal.GDT_Int16, whatever is suitable ### OVErRIDEM
crs_coords = '+proj=longlat +ellps=clrk66 +datum=NAD27 +no_defs' #source SRS
crs_grid = '+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=23.0 +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs' #target SRS
gdal_edit = r'C:\Users\Johannes\miniconda3\Scripts\gdal_edit.py'
xcoo_col = 'PropertyAddressLongitude'
ycoo_col = 'PropertyAddressLatitude'
bitdepth = gdal.GDT_Float32
years=np.arange(1999,2021,1)
            
 
def gdalNumpy2floatRaster_compressed(array,outname,template_georef_raster,x_pixels,y_pixels,px_type):
    
    #use px_type = gdal.GDT_Int16 or gdal.GDT_Float32)
    
    dst_filename = outname

    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(dst_filename,x_pixels, y_pixels, 1, px_type)   
    dataset.GetRasterBand(1).WriteArray(array)                
    mapraster = gdal.Open(template_georef_raster, gdal.GA_ReadOnly)
    proj=mapraster.GetProjection() #you can get from a existing tif or import 
    dataset.SetProjection(proj)
    dataset.FlushCache()
    dataset=None                

    #set bounding coords
    ulx, xres, xskew, uly, yskew, yres  = mapraster.GetGeoTransform()
    lrx = ulx + (mapraster.RasterXSize * xres)
    lry = uly + (mapraster.RasterYSize * yres)            
    mapraster = None
                    
    gdal_cmd = gdal_edit+' -a_ullr %s %s %s %s "%s"' % (ulx,uly,lrx,lry,outname)
    print(gdal_cmd)
    response=subprocess.check_output(gdal_cmd, shell=True)
    print(response)
    
    outname_lzw=outname.replace('.tif','_lzw.tif')
    gdal_translate = r'gdal_translate %s %s -co COMPRESS=LZW' %(outname,outname_lzw)
    print(gdal_translate)
    response=subprocess.check_output(gdal_translate, shell=True)
    print(response)
    os.remove(outname)
    os.rename(outname_lzw,outname)


if do_raster_multitemp:

    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster
    
    for year in years:
        #if year>2014:
        #    continue
        
        out_surface=np.zeros((cols,rows)).astype(np.float32)

        #out_surface_missing=np.zeros((cols,rows)).astype(np.float32)
        #out_surface_allcounts=np.zeros((cols,rows)).astype(np.float32)
        
        counter=0
        for csv in os.listdir(infolder):
            
            #if counter<=1493:
            #    continue
            if 'zip' in csv:
                continue
            
            #currfips=csv.split('_')[4]
            #if not currfips in rel_counties:
            #    continue

            counter+=1
            print(year,csv)
            
            #if year==1999:
            #    continue
            
            indf_all = pd.read_csv(infolder+os.sep+csv)
            #indf_all = indf_all[np.logical_and(indf_all[xcoo_col]<0,indf_all[ycoo_col]>0)] 
            
            if year==years[0]:
                indf_all=indf_all[np.logical_and(indf_all.YearBuilt>0,indf_all.YearBuilt<=year)]
            else:
                #indf_all=indf_all[np.logical_and(indf_all.YearBuilt>lower,indf_all.YearBuilt<=year)]
                indf_all=indf_all[indf_all.YearBuilt==year]
            
            try:
                indf_all = indf_all[[xcoo_col,ycoo_col,'combust_mat_mass_TOTAL']].replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
            except:
                continue
            
            indf_all = gp.GeoDataFrame(indf_all,geometry=gp.points_from_xy(indf_all[xcoo_col].values, indf_all[ycoo_col].values))
            indf_all.crs = crs_coords
            indf_all.geometry = indf_all.geometry.to_crs(crs_grid)      
            indf_all[xcoo_col]=indf_all.geometry.x
            indf_all[ycoo_col]=indf_all.geometry.y        
            indf = indf_all.dropna()             
            if not indf.empty:         
                curr_surface = scipy.stats.binned_statistic_2d(indf[xcoo_col].values,indf[ycoo_col].values,indf['combust_mat_mass_TOTAL'].values,np.sum,bins=[cols,rows],range=rasterrange)        
                out_surface = np.add(out_surface,np.nan_to_num(curr_surface.statistic))   
            print(year,counter,csv,len(indf_all),len(indf))#,len(indf_miss))
            #-break
    
        gdalNumpy2floatRaster_compressed(np.rot90(out_surface),surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_increment.tif' %year,template_raster,cols,rows,bitdepth)

if incr2cum:
    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster
    
    years=np.arange(1999,2021,1)
    for year in years:
        curr_incr_tif = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_increment.tif' %year
        
        if year==years[0]:
            curr_cum_surface = gdal.Open(curr_incr_tif).ReadAsArray()
        else:
            curr_cum_surface = curr_cum_surface + gdal.Open(curr_incr_tif).ReadAsArray()
            
        curr_cum_tif = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_cum.tif' %year
        gdalNumpy2floatRaster_compressed(curr_cum_surface,curr_cum_tif,template_raster,cols,rows,bitdepth)
        print('cum',year,'done.')
    
if do_contemp_layer:

    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster

    out_surface=np.zeros((cols,rows)).astype(np.float32)
    #out_surface_missing=np.zeros((cols,rows)).astype(np.float32)
    #out_surface_allcounts=np.zeros((cols,rows)).astype(np.float32)
    
    counter=0
    for csv in os.listdir(infolder):
        
        #if counter<=1493:
        #    continue
        if 'zip' in csv:
            continue
        
        #if '47011' in csv:
        #    continue
        
        #currfips=csv.split('_')[4]
        #if not currfips in rel_counties:
        #    continue

        counter+=1

        indf_all = pd.read_csv(infolder+os.sep+csv)
        #indf_all = indf_all[np.logical_and(indf_all[xcoo_col]<0,indf_all[ycoo_col]>0)] 

        try:
            indf_all = indf_all[[xcoo_col,ycoo_col,'combust_mat_mass_TOTAL']].replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
        except:
            continue
        
        indf_all = gp.GeoDataFrame(indf_all,geometry=gp.points_from_xy(indf_all[xcoo_col].values, indf_all[ycoo_col].values))
        indf_all.crs = crs_coords
        indf_all.geometry = indf_all.geometry.to_crs(crs_grid)
        try:
            indf_all[xcoo_col]=indf_all.geometry.x
            indf_all[ycoo_col]=indf_all.geometry.y  
        except:
            continue
        indf = indf_all.dropna()             
        if not indf.empty:         
            curr_surface = scipy.stats.binned_statistic_2d(indf[xcoo_col].values,indf[ycoo_col].values,indf['combust_mat_mass_TOTAL'].values,np.sum,bins=[cols,rows],range=rasterrange)        
            out_surface = np.add(out_surface,np.nan_to_num(curr_surface.statistic))   
        print(counter,csv,len(indf_all),len(indf))#,len(indf_miss))
        #-break

    gdalNumpy2floatRaster_compressed(np.rot90(out_surface),surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_contemp.tif',template_raster,cols,rows,bitdepth)


if do_raster_components:
    
    ### zo be adjusted
    
    nbu_lu_csv='not_built-up_landuses.csv'
    lu_lookup_csv='lu_lookup.csv'
    lu_matcomp_csv='lu_material_composition_small.csv'
    
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
    
    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster

    outvars=['fuel_energy_MJ', 'combust_mat_mass_Wood', 'combust_mat_mass_Plastic',
           'combust_mat_mass_Paper', 'combust_mat_mass_Cloth',
           'combust_mat_mass_Asphalt']

    outarr_list=[]
    out_surface_template =np.zeros((cols,rows)).astype(np.float32)
    for outvar in outvars:
        outarr_list.append([outvar,out_surface_template.copy()])

    
    counter=0
    for csv in os.listdir(infolder):

        counter+=1
        
        #if counter<=1493:
        #    continue
        if 'zip' in csv:
            continue
        
        indf_all = pd.read_csv(infolder+os.sep+csv)
        indf_all = indf_all[np.logical_and(indf_all[xcoo_col]<0,indf_all[ycoo_col]>0)] 
        
        try:
            indf_all = indf_all[[xcoo_col,ycoo_col,'PropertyLandUseStndCode',area_attribute]].replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
        except:
            if not 'PropertyLandUseStndCode' in indf_all.columns:
                indf_all['PropertyLandUseStndCode']=np.nan
            if not area_attribute in indf_all.columns:
                indf_all[area_attribute]=np.nan                
            indf_all = indf_all[[xcoo_col,ycoo_col,'PropertyLandUseStndCode',area_attribute]].replace('',np.nan).replace(' ',np.nan).replace(0,np.nan)
        
        indf_all = gp.GeoDataFrame(indf_all,geometry=gp.points_from_xy(indf_all[xcoo_col].values, indf_all[ycoo_col].values))
        indf_all.crs = crs_coords
        indf_all.geometry = indf_all.geometry.to_crs(crs_grid)      
        indf_all[xcoo_col]=indf_all.geometry.x
        indf_all[ycoo_col]=indf_all.geometry.y
        
        #### exclude nbu land uses: ##########
        indf_all=indf_all[np.logical_not(indf_all.PropertyLandUseStndCode.isin(exclude_lutypes))]                        
        ######################################    
        
        indf = indf_all.dropna() 
        
        if not indf.empty:       
            indf['bui_sqm']=indf[area_attribute]*0.09290304
            indf['lu_superclass']=indf.PropertyLandUseStndCode.str.slice(0 ,2)
            indf['lu_superclass_mapped']=indf.lu_superclass.map(lu_lookup_dict)
            indf=indf.merge(material_lookupdf,left_on='lu_superclass_mapped',right_on='Label',how='left')    
            #FLD [MJ/sqm] times area = fuel energy
            indf['fuel_energy_MJ']=indf.bui_sqm*indf.FLD_val
            cols_to_add=[]
            for material in list(r_dict.keys()):
                currcol='combust_mat_mass_%s' %material
                indf[currcol]=indf[material]*indf.fuel_energy_MJ/float(r_dict[material])
                cols_to_add.append(currcol)
                
            for stat in outvars:
                curridx=0
                counter2=-1
                for xx in outarr_list:
                    counter2+=1
                    if xx[0]==stat:                                
                        out_surface=xx[1].copy()
                        curridx=counter2
                        break
                        
                curr_surface = scipy.stats.binned_statistic_2d(indf[xcoo_col].values,indf[ycoo_col].values,indf[stat].values,np.sum,bins=[cols,rows],range=rasterrange)        
                out_surface = np.maximum(out_surface,np.nan_to_num(curr_surface.statistic))   
                outarr_list[curridx][1]=out_surface.copy()
                print(counter,csv,len(indf),stat)
    
    for xx in outarr_list:
        stat=xx[0] 
        out_surface=xx[1]                   
        gdalNumpy2floatRaster_compressed(np.rot90(out_surface),surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s.tif' %(stat),template_raster,cols,rows,bitdepth)
  

if do_raster_components_proportions:

    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster
    
    outvars=['combust_mat_mass_Wood', 'combust_mat_mass_Plastic',
           'combust_mat_mass_Paper', 'combust_mat_mass_Cloth',
           'combust_mat_mass_Asphalt']  
    
    for i,stat in enumerate(outvars):
        curr_rast = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s.tif' %(stat)
        if i==0:
            stack = gdal.Open(curr_rast).ReadAsArray()
        else:
            stack = np.dstack((stack,gdal.Open(curr_rast).ReadAsArray()))
    
    sumrast=np.sum(stack,axis=2)
    stack_prop = stack.copy()
    for i in np.arange(stack_prop.shape[2]):
        stack_prop[:,:,i] =  stack_prop[:,:,i]/sumrast
    stack_prop=np.nan_to_num(stack_prop)
    for i in np.arange(stack_prop.shape[2]):
        outname=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_prop.tif' %(outvars[i])
        gdalNumpy2floatRaster_compressed(stack_prop[:,:,i],outname,template_raster,cols,rows,bitdepth)
    
if do_temporal_metrics:

    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster
    
    inrast_1999 = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_cum.tif' %1999    
    inrast_2020 = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_cum.tif' %2020    

    inarr_1999 = gdal.Open(inrast_1999).ReadAsArray()
    inarr_2020 = gdal.Open(inrast_2020).ReadAsArray()

    abs_change = inarr_2020 - inarr_1999

    outname=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_abs_change_1999-2020.tif'
    gdalNumpy2floatRaster_compressed(abs_change,outname,template_raster,cols,rows,bitdepth)

    rel_change = 100 * abs_change / inarr_1999
    rel_change[rel_change==np.inf]=np.nan
    rel_change=np.nan_to_num(rel_change)
    outname=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_rel_change_1999-2020.tif'
    gdalNumpy2floatRaster_compressed(rel_change,outname,template_raster,cols,rows,bitdepth)

    
if prepare_data_submission:

    outdir=r'H:\ZTRAX_surfaces_2022\surfaces_fuel\DATA_SUBMISSION_V2'        

    raster = gdal.Open(template_raster)
    cols = raster.RasterXSize
    rows = raster.RasterYSize
    geotransform = raster.GetGeoTransform()
    topleftX = geotransform[0]
    topleftY = geotransform[3]
    pixelWidth = int(abs(geotransform[1]))
    pixelHeight = int(abs(geotransform[5]))
    rasterrange=[[topleftX,topleftX+pixelWidth*cols],[topleftY-pixelHeight*rows,topleftY]]    
    del raster
    
    for year in years:
        intif = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_cum.tif' %year
        outfile = outdir+os.sep+'urban_fuel_%s.tif'%year
        inarr = gdal.Open(intif).ReadAsArray()
        print(intif,np.min(inarr),np.max(inarr))
        print(inarr[inarr<0].shape[0],inarr.flatten().shape[0])
        inarr[inarr<0]=0
        gdalNumpy2floatRaster_compressed(inarr,outfile,template_raster,cols,rows,bitdepth)
             
    outvars=['combust_mat_mass_Wood', 'combust_mat_mass_Plastic',
           'combust_mat_mass_Paper', 'combust_mat_mass_Cloth',
           'combust_mat_mass_Asphalt']  
    
    for i,stat in enumerate(outvars):
        intif = surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s.tif' %(stat)
        outfile = outdir+os.sep+'urban_fuel_material_%s.tif'%stat.split('_')[-1].lower()
        inarr = gdal.Open(intif).ReadAsArray()
        print(intif,np.min(inarr),np.max(inarr))
        print(inarr[inarr<0].shape[0],inarr.flatten().shape[0])
        inarr[inarr<0]=0
        gdalNumpy2floatRaster_compressed(inarr,outfile,template_raster,cols,rows,bitdepth)
                      
        intif=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_%s_prop.tif' %(stat) 
        outfile = outdir+os.sep+'urban_fuel_material_%s_prop.tif'%stat.split('_')[-1].lower()
        inarr = gdal.Open(intif).ReadAsArray()
        print(intif,np.min(inarr),np.max(inarr))
        print(inarr[inarr<0].shape[0],inarr.flatten().shape[0])
        inarr[inarr<0]=0
        gdalNumpy2floatRaster_compressed(inarr,outfile,template_raster,cols,rows,bitdepth)
               
    intif=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_abs_change_1999-2020.tif'
    outfile = outdir+os.sep+'urban_fuel_change_1999-2020.tif'
    inarr = gdal.Open(intif).ReadAsArray()
    print(intif,np.min(inarr),np.max(inarr))
    print(inarr[inarr<0].shape[0],inarr.flatten().shape[0])
    inarr[inarr<0]=0
    gdalNumpy2floatRaster_compressed(inarr,outfile,template_raster,cols,rows,bitdepth)
                
    intif=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_contemp.tif'  
    outfile = outdir+os.sep+'urban_fuel_contemporary.tif'
    inarr = gdal.Open(intif).ReadAsArray()
    print(intif,np.min(inarr),np.max(inarr))
    print(inarr[inarr<0].shape[0],inarr.flatten().shape[0])
    inarr[inarr<0]=0
    gdalNumpy2floatRaster_compressed(inarr,outfile,template_raster,cols,rows,bitdepth)
        

if validate:
     intif=surface_folder+os.sep+'combustible_mass_250_imparea_median_V2_contemp.tif'      
     counts=surface_folder+os.sep+'count_all_rl3.tif'
     arr_cm = gdal.Open(intif).ReadAsArray()    
     arr_counts = gdal.Open(counts).ReadAsArray()
     
     df = pd.DataFrame({'combmass': arr_cm.flatten()/1000,'counts': arr_counts.flatten()})
     df=df[df.combmass>0]
     df=df[df.counts>0]
     df['mass_building_avg']=df.combmass/df.counts
     df=df[df.mass_building_avg<1000]
     df=df.dropna()
     fig,ax=plt.subplots()
     ax.hist(df.mass_building_avg.values,bins=1000)
     #ax.set_xlim([0,1000])
     ax.set_xscale('log')
     plt.show()
     
     
     
     