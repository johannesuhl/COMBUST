# -*- coding: utf-8 -*-
"""
Created on Tue Jun 25 14:11:51 2024

@author: Johannes H. Uhl 2022 - 2026
"""

# COMBUST: Gridded estimates of the combustible mass of the built environment in the conterminous U.S. (1975-2020)

import os,sys, shutil
try:
    import pandas as pd
    import scipy.stats
    import matplotlib.pyplot as plt
except:
    True
import geopandas as gp
import numpy as np
import subprocess
try:
    from osgeo import gdal 
except:
    import gdal
import rasterio
from rasterio import features
import seaborn as sns
from shapely.geometry import box
import zipfile
import matplotlib
plt.style.use('default')
matplotlib.rcParams['font.sans-serif'] = "Arial"
matplotlib.rcParams['font.family'] = "sans-serif" 

########################################################################################
preprocessing_OSM_Raffineries_GasStations_rasterize=True    #conversion into tons of comb mass
preprocessing_resample_SpawnData=True                       #data from https://www.nature.com/articles/s41597-020-0444-4
preproecessing_rasterize_climatezones=True                  #data from https://atlas.eia.gov/datasets/eia::climate-zones-doe-building-america-program/about 
######### MODEL COMPUTATION ###############################################################
assemble_all_data_frantzetal=True                           #creates a data frame from all rasterized data, computed building fuel from material components, writes results to parquet files.
write_relevant_geotiffs=True                                #writes variables relevant for final calculation to geotiffs.
impute_indoor_cm_and_compute_total=True                      #imputes building content fuel where missing, writes final surface, calculates high-level stats for plausibility checks.
disaggregate_cm_by_bldg_type_contemp=True                   #produces contemp total fuel disaggr by frantz et al bldg type.
produce_vehicle_fuel_layers_contemp=True                    #uses GHS-POP to infer CM and rubble of cars. Davis and Boundy, 2021, contemporary
produce_vehicle_fuel_layers_backcast=True                   #uses GHS-POP to infer CM and rubble of cars. Davis and Boundy, 2021, historical
convert_biomass_to_fuel=True                                #takes the spawn et al resampled in preprocessing_resample_SpawnData, converts mG C / ha into tons per grid cell.
######### HINDCASTING #####################################################################
hindcast_total_combmass_layer_GHSL=True                     #produces combust 1975,5,2020 by applying change rates from GHS-BUILT-V
hindcast_total_combmass_layer_HISDAC=True                   #produces combust 1999,1,2020 and 1975,5,2020 by applying change rates from HISDAC-US V1 union V2 BUI and FBUY.
######### FINAL OUTPUT ####################################################################
copy_rename_final_outputs=True                              #copy final geotiffs to output folder 
get_final_layer_list=True                                   #get a csv of all files produced, to facilitate automated zipping.
zip_files=True                                              #produce zip archives.
######### DATA SANITY AND PLAUSIBILITY CHECKS #############################################
test_nonbackcastable=True                                   #check non-backcastable cm
produce_mass_per_capita_stats_unitemp_mutemp_rucc=True      #Calculates statistics (cm/capita) to test plausibility.
vis_mass_per_capita_stats_mutemp_rucc=True                  #visualize results

###########################################################################################

# Paths:
building_vol_grid_tiff_templ = r'' #outputs of script 04
indoor_fuel_grids = r'' #outputs of script 03    
ghsl_dir = r'' #path with GHS-BUILT-V R2023A data (100m)
data_input_dir = './input'
outputs_temp = './output_temp'
outputs_final = './output_final'

# path to GHSL data: (downloadable from https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/)
ghsl_vol_template = ghsl_dir+os.sep+'GHS_BUILT_V_EYYYY_GLOBE_R2023A_54009_100_V1_0\GHS_BUILT_V_EYYYY_GLOBE_R2023A_54009_100_V1_0.tif'
ghsl_busurf_template = ghsl_dir+os.sep+'GHS_BUILT_S_EYYYY_GLOBE_R2023A_54009_100_V1_0\GHS_BUILT_S_EYYYY_GLOBE_R2023A_54009_100_V1_0.tif'
ghsl_pop_template = ghsl_dir+os.sep+'GHS_POP_EYYYY_GLOBE_R2023A_54009_100_V1_0\GHS_POP_EYYYY_GLOBE_R2023A_54009_100_V1_0.tif'

# path to Spawn et al. biomass data (downloadable from https://doi.org/10.3334/ORNLDAAC/1763):
inrast_spawn_above = data_input_dir + os.sep + 'Global_Maps_C_Density_2010_1763\data\aboveground_biomass_bon_2010.tif'
inrast_spawn_below = data_input_dir + os.sep + 'Global_Maps_C_Density_2010_1763\data\belowground_biomass_bon_2010.tif'

# other input data:
gas_stations_osm_gpkg = './geo/amenity-fuel_combined_CONUS_by_County.geojson' #output from script 05   
climate_zones_shp = './geo/Climate_Zones_-_DOE_Building_America_Program.shp' #can be obtained from https://atlas.eia.gov/datasets/eia::climate-zones-doe-building-america-program/about
in_surface_fips_codes = data_input_dir+os.sep+'fips_codes_county.tif' # CONUS counties FIPS rasterized in target grid
in_surface_rucc_codes = data_input_dir+os.sep+'rucc_codes_county.tif' # CONUS counties USDA rural-urban continuum code rasterized in target grid
raffineries_csv = '' #can be obtained from https://www.arcgis.com/home/item.html?id=bca9cc67d6664282900d7d31014a2bfe

# hisdac-us data:
hisdacus_v1_bui_template= './HISDAC_US/HISDAC_US_V1_BUI/BUI_YYYY.tif'    #https://doi.org/10.7910/DVN/1WB9E4
hisdacus_v2_bui_template= './HISDAC_US/HISDAC_US_V2_BUI/YYYY_BUI.tif'    #https://doi.org/10.7910/DVN/CSLOJP
hisdacus_v1_bupl_template= './HISDAC_US/HISDAC_US_V1_BUPL/BUPL_YYYY.tif' #https://doi.org/10.7910/DVN/SJ213V
hisdacus_v2_bupl_template= './HISDAC_US/HISDAC_US_V2_BUPL/YYYY_BUPL.tif' #https://doi.org/10.7910/DVN/U2P66Z

# input data (tables and crosswalk files):
crosswalk_csv_climate_zones =  './csv/climate_zones_crosswalk.csv'
crosswalk_csv_frantz_material =  './csv/frantz_etal_zenodo_USA_MaterialIntensities.csv'
crosswalk_csv_frantz_buildingtypes =  './csv/frantz_crosswalk_tiff_BT.csv'
car_data_csv = './csv/cars_pop.csv'
cars_per_pop_csv = './csv/cars_per_pop.csv'

# some temporary output files
out_surface_gas_stat_count = data_input_dir+os.sep+'osm_gas_stations_count.tif'
out_surface_raffineries_count = data_input_dir+os.sep+'osm_raffineries_count.tif'
out_surface_climatezones = data_input_dir+os.sep+'climate_zones.tif'
inrast_spawn_above_clip = outputs_temp + os.sep + 'aboveground_biomass_carbon_2010_clip.tif'
inrast_spawn_below_clip = outputs_temp + os.sep + 'belowground_biomass_carbon_2010_clip.tif'
inrast_spawn_above_res = outputs_temp + os.sep + 'aboveground_biomass_carbon_2010_resample.tif'
inrast_spawn_below_res = outputs_temp + os.sep + 'belowground_biomass_carbon_2010_resample.tif'

########################################################################################
template_raster = '' # template raster, dicates target grid
gdal_edit = r'gdal_edit.py' #path to gdal_edit
gdalwarp = r'C:\OSGeo4W\bin\gdalwarp.exe'#path to gdalwarp
resample_factor=250 #set to resolution of template_raster, target resolution of model in m
mi_scenarios=['low','mean','high'] #scenarios from frantz et al to be processed  
export_columns=['combust_total_mass_ext','comb_mass_raffineries', 'comb_mass_gas_stations','ind_bldg_combmass_contemp'] #columns to be exported to geotiff, as input for final computation
export_columns_noncombmass=['noncombust_total_mass_ext']
uspop2020 = 331449281 # for per capita stats
uspop1999 = 272690813 # for per capita stats
uspop1990 = 248709873 # for per capita stats
uspop1975 = 213811000 # for per capita stats
mollw_proj4 = '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'
ghsl_years=np.arange(1975,2021,5)

## material list #######################################################################

bldg_content_materials = ['cloth','paper','plastic','wood']
flamm_materials=['timber','other biomass-based materials','bitumen',
                 'all other petrochemical-based materials','other biomass-based materials']

non_flamm_materials=['iron/steel', 'copper','aluminum', 'all other metals', 'concrete (cement + aggregate)', 
                     'bricks', 'glass', 'all other minerals','insulation','all other materials']

########################################################################################

def gdalNumpy2floatRaster_compressed(array,outname,template_georef_raster,x_pixels,y_pixels,px_type):
    # helper function for gridding
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

def raster_subset(inname,outname,ulx,uly,lrx,lry):    
    gdal_cmd = 'gdal_translate -projwin %s %s %s %s -co COMPRESS=LZW "%s" "%s"' % (ulx,uly,lrx,lry,inname,outname)
    print(gdal_cmd)
    response=subprocess.check_output(gdal_cmd, shell=True) 
    return response

def raster_compress(inname,outname):    
    gdal_cmd = 'gdal_translate -co COMPRESS=LZW "%s" "%s"' % (inname,outname)
    print(gdal_cmd)
    response=subprocess.check_output(gdal_cmd, shell=True) 
    return response

def raster_warp(inname,outname,xmin,ymin,xmax,ymax,crs_target,resampling):    
    gdal_cmd = 'gdalwarp -tr 250 250 -te %s %s %s %s -t_srs EPSG:%s -r %s -overwrite -multi -wo NUM_THREADS=ALL_CPUS -co COMPRESS=LZW "%s" "%s"' % (xmin,ymin,xmax,ymax,crs_target,resampling,inname,outname)
    print(gdal_cmd)
    response=subprocess.check_output(gdal_cmd, shell=True) 
    return response
    
##########################################################################################################      
    
if preprocessing_resample_SpawnData:
    
    # clip rasters to CONUS
    with rasterio.open(template_raster) as templ_ds:        
        crs_grid = rasterio.crs.CRS(templ_ds.crs).to_epsg()
        bbox_target = templ_ds.bounds
    geom = box(*bbox_target)
    bbox_target_gdf = gp.GeoDataFrame(geometry=[geom],crs=crs_grid)
    with rasterio.open(inrast_spawn_above) as ds:        
        crs_source = rasterio.crs.CRS(ds.crs).to_epsg() 
    target_bounds  = bbox_target_gdf.total_bounds
    bbox_target_gdf = bbox_target_gdf.to_crs(crs_source)
    bbox_target_gdf.geometry = bbox_target_gdf.geometry.buffer(4) #buffer the polygon by 4 degree, otherwise we cut off relevant stuff.
    extract_bounds = bbox_target_gdf.total_bounds
    ulx = extract_bounds[0]
    uly = extract_bounds[3]
    lrx = extract_bounds[2]
    lry = extract_bounds[1]  
    xmin = target_bounds[0]
    ymin = target_bounds[1]
    xmax = target_bounds[2]
    ymax = target_bounds[3]  
    raster_subset(inrast_spawn_above,inrast_spawn_above_clip,ulx,uly,lrx,lry)
    raster_subset(inrast_spawn_below,inrast_spawn_below_clip,ulx,uly,lrx,lry)
    raster_warp(inrast_spawn_above_clip,inrast_spawn_above_res,xmin,ymin,xmax,ymax,crs_grid,'near')
    raster_warp(inrast_spawn_below_clip,inrast_spawn_below_res,xmin,ymin,xmax,ymax,crs_grid,'near')
    
########################################################################################   
if preprocessing_OSM_Raffineries_GasStations_rasterize:
    do_gasstations=True
    do_raffineries=True
    with rasterio.open(template_raster) as templ_ds:        
        crs_grid = rasterio.crs.CRS(templ_ds.crs).to_epsg()
    surface_folder=data_input_dir #folder to store output tifs.
    #################################################################################################################
    if do_gasstations:
        osm_gas_gdf = gp.read_file(gas_stations_osm_gpkg)    
        osm_gas_gdf.geometry = osm_gas_gdf.geometry.centroid
        osm_gas_gdf = osm_gas_gdf.to_crs(crs_grid)
        indf = osm_gas_gdf
        xcoo_col,ycoo_col = 'x','y'      
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
        statistic=np.nansum
        bitdepth=gdal.GDT_Int32
        indf[xcoo_col]=indf.geometry.x
        indf[ycoo_col]=indf.geometry.y
        indf['count']=1
        # # # # # # # # # # # # # # # # # # # # # # # # # #         
        indf['count'] = 106.2775 #in tons: 35000 gallons of gasoline are 212555 lbs, times 0.0005 are 106.2775 t per gas station (https://calculator.academy/gasoline-weight-calculator/)
        # # # # # # # # # # # # # # # # # # # # # # # # # #  
        
        out_surface_gasstation_count =np.zeros((cols,rows),dtype=np.uint16)   
        target_variable='count'
        indf[target_variable]=indf[target_variable].map(float).map(np.int32)
        indf=indf[indf[target_variable]>0]
        indf = indf.dropna(subset=[target_variable])
        statsvals = indf[target_variable].values.astype(np.int32)  
        curr_surface = scipy.stats.binned_statistic_2d(indf[xcoo_col].values,indf[ycoo_col].values,statsvals,statistic,bins=[cols,rows],range=rasterrange).statistic     
        curr_surface = np.nan_to_num(curr_surface).astype(np.int32)         
        gdalNumpy2floatRaster_compressed(np.rot90(curr_surface),out_surface_gas_stat_count,template_raster,cols,rows,bitdepth)
    
    if do_raffineries:
        indf = pd.read_csv(raffineries_csv)
        ingdf = gp.GeoDataFrame(indf,geometry=gp.points_from_xy(indf.Longitude.values,indf.Latitude.values,crs=4326))
        indf = ingdf.to_crs(epsg=crs_grid)     
        xcoo_col,ycoo_col = 'x','y'      
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
        statistic=np.nansum
        bitdepth=gdal.GDT_Int32
        indf[xcoo_col]=indf.geometry.x
        indf[ycoo_col]=indf.geometry.y
        indf['count']=1
        # calculate metric tons from volume in barrels, using a Density of 0.710 g/mL, which is 0.710 kg/l
        indf['count']= 0.710*(indf['Capacity (Barrels per day)']*158.987295)/1000
         
        out_surface_gasstation_count =np.zeros((cols,rows),dtype=np.uint16)   
        target_variable='count'
        indf[target_variable]=indf[target_variable].map(float).map(np.int32)
        indf=indf[indf[target_variable]>0]
        indf = indf.dropna(subset=[target_variable])
        statsvals = indf[target_variable].values.astype(np.int32)  
        curr_surface = scipy.stats.binned_statistic_2d(indf[xcoo_col].values,indf[ycoo_col].values,statsvals,statistic,bins=[cols,rows],range=rasterrange).statistic     
        curr_surface = np.nan_to_num(curr_surface).astype(np.int32)         
        gdalNumpy2floatRaster_compressed(np.rot90(curr_surface),out_surface_raffineries_count,template_raster,cols,rows,bitdepth)

if preproecessing_rasterize_climatezones:
    climate_zones_gdf = gp.read_file(climate_zones_shp)
    with rasterio.open(template_raster) as templ_ds:
        crs_grid = rasterio.crs.CRS(templ_ds.crs).to_epsg()
        meta = templ_ds.meta.copy()
    meta.update(compress='lzw')
    climate_zones_gdf = climate_zones_gdf.to_crs(epsg=crs_grid)
    uq_codes = climate_zones_gdf.BA_Climate.unique()
    uq_codedf = pd.DataFrame()
    uq_codedf['BA_Climate']=uq_codes
    uq_codedf['BA_Climate_code']=np.arange(1,uq_codes.shape[0]+1)  
    climate_zones_gdf = climate_zones_gdf.merge(uq_codedf,on='BA_Climate',how='left')
    with rasterio.open(out_surface_climatezones, 'w+', **meta) as out:
        out_arr = out.read(1)    
        shapes = ((geom,value) for geom, value in zip(climate_zones_gdf.geometry, climate_zones_gdf.BA_Climate_code))   
        burned = features.rasterize(shapes=shapes, fill=0, out=out_arr, transform=out.transform)
        print(np.unique(burned))
        out.write_band(1, burned)  
    climate_zones_gdf.to_file(climate_zones_shp)        

if assemble_all_data_frantzetal:


    do_noncomb_volume=False
    
    comb_mass_per_gas_station=1 ### calculated already in preprocessing_OSM_Raffineries_GasStations_rasterize
    comb_mass_per_raffinery=1 ### calculated already in preprocessing_OSM_Raffineries_GasStations_rasterize
    ########################################################################v
    
    ### add stratification variables:
    counties_id_rast = gdal.Open(in_surface_fips_codes).ReadAsArray()
    counties_rucc_rast = gdal.Open(in_surface_rucc_codes).ReadAsArray()
        
    allmodeldf = pd.DataFrame()
    allmodeldf['county_fips']=counties_id_rast.flatten()
    allmodeldf['county_rucc']=counties_rucc_rast.flatten()
    rasteridxs=np.indices(counties_id_rast.shape)
    allmodeldf['raster_idx0']=rasteridxs[0].flatten()
    allmodeldf['raster_idx1']=rasteridxs[1].flatten()
    
    crosswalk_df_material = pd.read_csv(crosswalk_csv_frantz_material)
    crosswalk_df_buildingtypes = pd.read_csv(crosswalk_csv_frantz_buildingtypes)    
    crosswalk_df_climatezones = pd.read_csv(crosswalk_csv_climate_zones)
    crosswalk_df_climatezones = crosswalk_df_climatezones[['climate_zone_MI', 'BA_Climate_code']] #'description_text', 'BA_Climate', 
    crosswalk_df_climatezones.BA_Climate_code = crosswalk_df_climatezones.BA_Climate_code.map(np.uint8)
    
    bldg_type_lookup = dict(zip(crosswalk_df_buildingtypes.tiff_type,crosswalk_df_buildingtypes.mi_category))    
    for butype in crosswalk_df_buildingtypes.tiff_type.unique():
        currtiff = building_vol_grid_tiff_templ.replace('BUTYPE',butype)
        curr_arr = gdal.Open(currtiff).ReadAsArray()
        allmodeldf['ext_bldg_volume_%s' %bldg_type_lookup[butype]] = curr_arr.flatten().astype(np.int32) 
        print(butype)
         
    allmodeldf['gas_stat_count'] = gdal.Open(out_surface_gas_stat_count).ReadAsArray().astype(np.int16).flatten()
    allmodeldf['raffineries_count'] = gdal.Open(out_surface_raffineries_count).ReadAsArray().astype(np.int16).flatten()
    allmodeldf['BA_Climate_code'] = gdal.Open(out_surface_climatezones).ReadAsArray().astype(np.int8).flatten() 

    print(len(allmodeldf))
    allmodeldf = allmodeldf[allmodeldf.county_fips>-1]
    print(len(allmodeldf))
    
    allmodeldf['comb_mass_raffineries'] = allmodeldf['raffineries_count']*comb_mass_per_raffinery
    allmodeldf['comb_mass_gas_stations'] = allmodeldf['gas_stat_count']*comb_mass_per_gas_station
        
    #need to impute BA_Climate_code where missing
    allmodeldf.loc[allmodeldf.county_fips.isin([12086,12087]),'BA_Climate_code']=1
    allmodeldf.BA_Climate_code = allmodeldf.BA_Climate_code.replace(0,5)
    
    BA_Climate_codes = allmodeldf.BA_Climate_code.unique()
    for cz, czdf in allmodeldf.groupby('BA_Climate_code'):
        czdf.to_parquet(outputs_temp+os.sep+'combmass_df_mi_scenario_temp_%s.parquet' %(cz))  
        
    
    del allmodeldf
   
    climate_zone_lookup = dict(zip(crosswalk_df_climatezones.BA_Climate_code,
                                   crosswalk_df_climatezones.climate_zone_MI))
    for mi_scenario in mi_scenarios:
        crosswalk_df_material_cur = crosswalk_df_material[crosswalk_df_material.scenario==mi_scenario]
           
        for cz in BA_Climate_codes:
            picklefile=outputs_temp+os.sep+'combmass_df_mi_scenario_temp_%s.parquet' %(cz)
            czdf = currdf = pd.read_parquet(picklefile)

            climate_zone_MI = climate_zone_lookup[cz]
            crosswalk_df_material_cur2 = crosswalk_df_material_cur[crosswalk_df_material_cur['climate zone'].isin([climate_zone_MI,'All zones'])]
            allbldgtypes = crosswalk_df_material_cur2['stock type'].unique()
            
            #combustible mass:
            sum_allbldgs=np.zeros((len(czdf)))
            for bldgtype in allbldgtypes:
                bldg_material_df = crosswalk_df_material_cur2[crosswalk_df_material_cur2['stock type']==bldgtype]
                incol = 'ext_bldg_volume_%s' %bldgtype 
                sum_bldgtype=np.zeros((len(czdf)))
                for flamm_material in flamm_materials:
                    outcol = 'combust_bldg_%s_mass_%s' %(bldgtype,flamm_material) 
                    currval = float(bldg_material_df[flamm_material].values[0]) #here we get the density of the material
                    czdf[outcol] = np.multiply(czdf[incol],currval).astype(np.int32) #her we convert volume to mass
                    sum_bldgtype = np.add(sum_bldgtype,czdf[outcol]).astype(np.int32)
                    print(mi_scenario,cz,bldgtype,flamm_material,currval)
                # calculate sums of ext combmass per building type and overall                     
                bldgtype_sum_col = 'combust_bldg_%s_mass_ext' %(bldgtype) #in kg
                czdf[bldgtype_sum_col] = sum_bldgtype.astype(np.int32)
                sum_allbldgs = np.add(sum_allbldgs,sum_bldgtype).astype(np.int32)
                del sum_bldgtype
            total_sum_col = 'combust_total_mass_ext'
            czdf[total_sum_col] = sum_allbldgs.astype(np.int32)    

            #non-combustible mass:
            sum_allbldgs_nc=np.zeros((len(czdf)))
            for bldgtype in allbldgtypes:
                bldg_material_df = crosswalk_df_material_cur2[crosswalk_df_material_cur2['stock type']==bldgtype]
                incol = 'ext_bldg_volume_%s' %bldgtype 
                sum_bldgtype=np.zeros((len(czdf)))
                for non_flamm_material in non_flamm_materials:
                    outcol = 'noncombust_bldg_%s_mass_%s' %(bldgtype,non_flamm_material) 
                    currval = float(bldg_material_df[non_flamm_material].values[0]) #here we get the density of the material
                    czdf[outcol] = np.multiply(czdf[incol],currval).astype(np.int32) #her we convert volume to mass
                    sum_bldgtype = np.add(sum_bldgtype,czdf[outcol]).astype(np.int32)
                    print(mi_scenario,cz,bldgtype,non_flamm_material)
                # calculate sums of ext combmass per building type and overall                     
                bldgtype_sum_col = 'noncombust_bldg_%s_mass_ext' %(bldgtype) #in kg
                czdf[bldgtype_sum_col] = sum_bldgtype.astype(np.int32)
                sum_allbldgs_nc = np.add(sum_allbldgs_nc,sum_bldgtype).astype(np.int32)
                del sum_bldgtype
            total_sum_col = 'noncombust_total_mass_ext'
            czdf[total_sum_col] = sum_allbldgs_nc.astype(np.int32) 
            
            if do_noncomb_volume:
                
                #non-combustible volume:
                sum_allbldgs_nc=np.zeros((len(czdf)))
                for bldgtype in allbldgtypes:
                    bldg_material_df = crosswalk_df_material_cur2[crosswalk_df_material_cur2['stock type']==bldgtype]
                    incol = 'ext_bldg_volume_%s' %bldgtype 
                    sum_bldgtype=np.zeros((len(czdf)))
                    for non_flamm_material in non_flamm_materials:
                        outcol = 'noncombust_bldg_%s_volume_%s' %(bldgtype,non_flamm_material) 
                        #currval = float(bldg_material_df[flamm_material].values[0]) #here we get the density of the material
                        czdf[outcol] = czdf[incol] #np.multiply(czdf[incol],currval).astype(np.int32) #her we convert volume to mass
                        sum_bldgtype = np.add(sum_bldgtype,czdf[outcol]).astype(np.int32)
                        print(mi_scenario,cz,bldgtype,non_flamm_material)
                    # calculate sums of ext combmass per building type and overall                     
                    bldgtype_sum_col = 'noncombust_bldg_%s_volume_ext' %(bldgtype) #in kg
                    czdf[bldgtype_sum_col] = sum_bldgtype.astype(np.int32)
                    sum_allbldgs_nc = np.add(sum_allbldgs,sum_bldgtype).astype(np.int32)
                    del sum_bldgtype
                total_sum_col = 'noncombust_total_volume_ext'
                czdf[total_sum_col] = sum_allbldgs_nc.astype(np.int32)  
    
            # export the df for the current mi_scenario  and climate zone      
            czdf.to_parquet(outputs_temp+os.sep+'combmass_df_mi_scenario_%s_%s.parquet' %(mi_scenario,cz))    
            del czdf,sum_allbldgs

    #delete temp files:
    for cz in BA_Climate_codes:
        os.remove(outputs_temp+os.sep+'combmass_df_mi_scenario_temp_%s.parquet' %(cz))  

if write_relevant_geotiffs:

    with rasterio.open(out_surface_gas_stat_count) as templ_ds:        
        meta = templ_ds.meta
    width = meta['width']
    height = meta['height']
    
    #produce indoor cm (building contents from frishcosy) from components:
    for contentmat in bldg_content_materials:
        gtiff = os.path.join(indoor_fuel_grids, 'urban_fuel_material_%s.tif' %contentmat)
        arr = gdal.Open(gtiff).ReadAsArray()
        if bldg_content_materials.index(contentmat)==0:
            outarr = arr.copy()
        else:
            outarr = outarr + arr

    meta.update(
        dtype=rasterio.float32,
        count=1,
        compress='lzw') 
    for mi_scenario in mi_scenarios:
        with rasterio.open(os.path.join(outputs_temp, 'combust_component_mi_%s_ind_bldg_combmass_contemp.tif' %mi_scenario), 'w', **meta) as dst:
            dst.write_band(1, outarr.astype(rasterio.float32))
        

    for mi_scenario in mi_scenarios:
        for flamm_mat in flamm_materials:
            export_column = 'total_cm_%s' %flamm_mat
            print(mi_scenario,flamm_mat)
            outarr=np.zeros((height,width))
            picklefiles=[]
            for file in os.listdir(outputs_temp):
                if 'combmass_df_mi_scenario_%s_' %(mi_scenario) in file:
                    picklefiles.append(outputs_temp+os.sep+file)                 
            for iii,picklefile in enumerate(picklefiles):
                if iii==0:
                    tempdf=pd.read_parquet(picklefile)
                    currdf_columns = tempdf.columns    
                    del tempdf
                print(picklefile)
                relcols=[x for x in currdf_columns if flamm_mat in x]
                for iii,relcol in enumerate(relcols):
                    currdf = pd.read_parquet(picklefile,columns=['raster_idx0', 'raster_idx1',relcol])                    
                    outarr[currdf.raster_idx0.values,currdf.raster_idx1.values]+=currdf[relcol].values
                del currdf
            meta.update(
                dtype=rasterio.float32,
                count=1,
                compress='lzw') 
            with rasterio.open(os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,export_column.replace(' ','_').replace('-','_'))), 'w', **meta) as dst:
                dst.write_band(1, (outarr/1000.0).astype(rasterio.float32))#to tons
            print(mi_scenario,flamm_mat,'done')
            del outarr
                                      
    for mi_scenario in mi_scenarios:
        for export_column in export_columns[:-1]:
            outarr=np.zeros((height,width))
            picklefiles=[]
            for file in os.listdir(outputs_temp):
                if 'combmass_df_mi_scenario_%s_' %(mi_scenario) in file:
                    picklefiles.append(outputs_temp+os.sep+file)
            for picklefile in picklefiles:
                currdf = pd.read_parquet(picklefile,columns=['raster_idx0', 'raster_idx1',export_column])
                outarr[currdf.raster_idx0.values,currdf.raster_idx1.values]=currdf[export_column].values
                del currdf
            #plt.imshow(np.log(1+outarr))
            #plt.show()                         
             # Write to TIFF
            meta.update(
                dtype=rasterio.float32,
                count=1,
                compress='lzw') 
            with rasterio.open(os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,export_column)), 'w', **meta) as dst:
                dst.write_band(1, outarr.astype(rasterio.float32))                           

    for mi_scenario in mi_scenarios:
        
        for export_column in export_columns_noncombmass:
            if 'mass' in export_column:
                target_unit='t'
                divideby=1000.0
            if 'volume' in export_column:
                target_unit='m3'
                divideby=1.0
                
            outarr=np.zeros((height,width))
            picklefiles=[]
            for file in os.listdir(outputs_temp):
                if 'combmass_df_mi_scenario_%s_' %(mi_scenario) in file:
                    picklefiles.append(outputs_temp+os.sep+file)
            for picklefile in picklefiles:
                currdf = pd.read_parquet(picklefile,columns=['raster_idx0', 'raster_idx1',export_column])
                outarr[currdf.raster_idx0.values,currdf.raster_idx1.values]=currdf[export_column].values
                del currdf
            outarr=outarr/divideby #to tons
            #plt.imshow(np.log(1+outarr))
            #plt.show()                         
             # Write to TIFF
            meta.update(
                dtype=rasterio.float32,
                count=1,
                compress='lzw') 
            with rasterio.open(os.path.join(outputs_temp, 'combust_noncombust_mi_%s_%s_%s.tif' %(mi_scenario,export_column,target_unit)), 'w', **meta) as dst:
                dst.write_band(1, outarr.astype(rasterio.float32))                  
            
if impute_indoor_cm_and_compute_total:
    cm_per_cap_stats=[]
    for mi_scenario in mi_scenarios:
        conusdf=pd.DataFrame()             
        for export_column in export_columns:
            gtiff = os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,export_column))
            arr = gdal.Open(gtiff).ReadAsArray()
            conusdf[export_column]=arr.flatten()
            print('loaded',mi_scenario,export_column)

        ###add indices:
        idx_arr_0,idx_arr_1 = np.indices(arr.shape)
        conusdf['raster_idx0']=idx_arr_0.flatten() 
        conusdf['raster_idx1']=idx_arr_1.flatten() 

        conusdf['combust_total_mass_ext_t'] = conusdf.combust_total_mass_ext/1000.0         
        conusdf['ind_bldg_combmass_contemp_t'] = conusdf.ind_bldg_combmass_contemp/1000.0         
        
        conusdf_w_indoorcm = conusdf[np.logical_and(conusdf.combust_total_mass_ext_t>0,
                                                   conusdf.ind_bldg_combmass_contemp_t>0)]
        conusdf_wo_indoorcm = conusdf[np.logical_and(conusdf.combust_total_mass_ext_t>0,
                                                   conusdf.ind_bldg_combmass_contemp_t==0)]
 
        conusdf3=conusdf_w_indoorcm[np.logical_and(conusdf_w_indoorcm.ind_bldg_combmass_contemp>0,conusdf_w_indoorcm.combust_total_mass_ext>0)]        
        median_content_cm_per_bldg_cm = np.nanmedian(conusdf3.ind_bldg_combmass_contemp/conusdf3.combust_total_mass_ext)
        print(mi_scenario,median_content_cm_per_bldg_cm)
            
        conusdf_wo_indoorcm['ind_bldg_combmass_contemp_t'] = median_content_cm_per_bldg_cm*conusdf_wo_indoorcm['combust_total_mass_ext_t']

        print(np.sum(conusdf_wo_indoorcm['ind_bldg_combmass_contemp_t']))

        conusdf_imputed = pd.concat([conusdf_wo_indoorcm,conusdf_w_indoorcm])
        conusdf_imputed['cm_overall_t'] = conusdf_imputed.ind_bldg_combmass_contemp_t + conusdf_imputed.combust_total_mass_ext_t + conusdf_imputed.comb_mass_raffineries.fillna(0) + conusdf_imputed.comb_mass_gas_stations.fillna(0)

        content_cm_cap = conusdf_imputed.ind_bldg_combmass_contemp_t.sum()/uspop2020
        print(content_cm_cap)
        
        #### export the imputed building content and overall CM geotiff: ########################

        with rasterio.open(gtiff) as templ_ds:        
            meta = templ_ds.meta
        width = meta['width']
        height = meta['height']        

        addtl_export_var='cm_overall_t'
        gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_%s.tif' %(mi_scenario,addtl_export_var))
        outarr=np.zeros((height,width))
        outarr[conusdf_imputed.raster_idx0.values,conusdf_imputed.raster_idx1.values]=conusdf_imputed[addtl_export_var].values
        plt.imshow(np.log(1+outarr))
        plt.show()                         
         # Write to TIFF
        meta.update(
            dtype=rasterio.float32,
            count=1,
            compress='lzw')            
        with rasterio.open(gtiff, 'w', **meta) as dst:
            dst.write_band(1, outarr.astype(rasterio.float32))  

        addtl_export_var='ind_bldg_combmass_contemp_t'
        gtiff = os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,'ind_bldg_combmass_contemp_t_orig_and_imputed_values'))
        outarr=np.zeros((height,width))
        outarr[conusdf_imputed.raster_idx0.values,conusdf_imputed.raster_idx1.values]=conusdf_imputed[addtl_export_var].values
        plt.imshow(np.log(1+outarr))
        plt.show()                         
         # Write to TIFF
        meta.update(
            dtype=rasterio.float32,
            count=1,
            compress='lzw')            
        with rasterio.open(gtiff, 'w', **meta) as dst:
            dst.write_band(1, outarr.astype(rasterio.float32))  
            
        addtl_export_var='ind_bldg_combmass_contemp_t'
        gtiff = os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,'ind_bldg_combmass_contemp_t_orig_values'))
        outarr=np.zeros((height,width))
        outarr[conusdf_w_indoorcm.raster_idx0.values,conusdf_w_indoorcm.raster_idx1.values]=conusdf_w_indoorcm[addtl_export_var].values
        plt.imshow(np.log(1+outarr))
        plt.show()                         
         # Write to TIFF
        meta.update(
            dtype=rasterio.float32,
            count=1,
            compress='lzw')            
        with rasterio.open(gtiff, 'w', **meta) as dst:
            dst.write_band(1, outarr.astype(rasterio.float32))              
            
        addtl_export_var='ind_bldg_combmass_contemp_t'
        gtiff = os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,'ind_bldg_combmass_contemp_t_imputed_values'))
        outarr=np.zeros((height,width))
        outarr[conusdf_wo_indoorcm.raster_idx0.values,conusdf_wo_indoorcm.raster_idx1.values]=conusdf_wo_indoorcm[addtl_export_var].values
        plt.imshow(np.log(1+outarr))
        plt.show()                         
        # Write to TIFF
        meta.update(
             dtype=rasterio.float32,
             count=1,
             compress='lzw')            
        with rasterio.open(gtiff, 'w', **meta) as dst:
             dst.write_band(1, outarr.astype(rasterio.float32))             
 
        #### calculate some overall statistics, to test if CM per capita yields plausible results: ########
        
        cm_capita_overall = conusdf_imputed['cm_overall_t'].sum() / uspop2020#
        cm_capita_indoor = conusdf_imputed['ind_bldg_combmass_contemp_t'].sum() / uspop2020
        cm_capita_ext = conusdf_imputed['combust_total_mass_ext_t'].sum() / uspop2020
        cm_capita_raff = conusdf_imputed['comb_mass_raffineries'].sum() / uspop2020
        cm_capita_gasst = conusdf_imputed['comb_mass_gas_stations'].sum() / uspop2020

        cm_per_cap_stats.append([mi_scenario,'imputed','cm_capita_indoor',cm_capita_indoor])
        cm_per_cap_stats.append([mi_scenario,'imputed','cm_capita_ext',cm_capita_ext])
        cm_per_cap_stats.append([mi_scenario,'imputed','cm_capita_overall',cm_capita_overall])
        cm_per_cap_stats.append([mi_scenario,'imputed','cm_capita_raff',cm_capita_raff])
        cm_per_cap_stats.append([mi_scenario,'imputed','cm_capita_gasst',cm_capita_gasst])
 
        conusdf['cm_overall'] = conusdf.ind_bldg_combmass_contemp_t + conusdf.combust_total_mass_ext_t + conusdf.comb_mass_raffineries.fillna(0) + conusdf.comb_mass_gas_stations.fillna(0)
        cm_capita_overall = conusdf['cm_overall'].sum() / uspop2020#
        cm_capita_indoor = conusdf['ind_bldg_combmass_contemp_t'].sum() / uspop2020
        cm_capita_ext = conusdf['combust_total_mass_ext_t'].sum() / uspop2020
        cm_capita_raff = conusdf['comb_mass_raffineries'].sum() / uspop2020
        cm_capita_gasst = conusdf['comb_mass_gas_stations'].sum() / uspop2020

        cm_per_cap_stats.append([mi_scenario,'not_imputed','cm_capita_indoor',cm_capita_indoor])
        cm_per_cap_stats.append([mi_scenario,'not_imputed','cm_capita_ext',cm_capita_ext])
        cm_per_cap_stats.append([mi_scenario,'not_imputed','cm_capita_overall',cm_capita_overall])
        cm_per_cap_stats.append([mi_scenario,'not_imputed','cm_capita_raff',cm_capita_raff])
        cm_per_cap_stats.append([mi_scenario,'not_imputed','cm_capita_gasst',cm_capita_gasst])   
       
        del conusdf
        del conusdf_imputed
        del conusdf_wo_indoorcm
        del conusdf_w_indoorcm
    
    cm_per_cap_statsdf=pd.DataFrame(cm_per_cap_stats,columns=['mi_scenario','imputed','component','cm_capita'])
    cm_per_cap_statsdf.to_csv(outputs_final+os.sep+'cm_per_cap_overall.csv',index=False)

if disaggregate_cm_by_bldg_type_contemp:

    # use grid-cell proportions of building volume per building type to disaggregate proportionally:
    crosswalk_df_buildingtypes = pd.read_csv(crosswalk_csv_frantz_buildingtypes)    
    bldg_type_lookup = dict(zip(crosswalk_df_buildingtypes.tiff_type,crosswalk_df_buildingtypes.mi_category))    
    
    for i,butype in enumerate(crosswalk_df_buildingtypes.tiff_type.unique()):
        currtiff = building_vol_grid_tiff_templ.replace('BUTYPE',butype)
        curr_arr = gdal.Open(currtiff).ReadAsArray()
        if i==0:
            buvol_stack=curr_arr.copy()
        else:
            buvol_stack=np.dstack([buvol_stack,curr_arr.copy()])
        print(butype)
    
    buvolsum=np.nansum(buvol_stack,axis=2)    
    buvolprop_stack=np.zeros(buvol_stack.shape)
    for i,butype in enumerate(crosswalk_df_buildingtypes.tiff_type.unique()):
        buvolprop_stack[:,:,i]=np.divide(buvol_stack[:,:,i],buvolsum)
        print(butype)

    with rasterio.open(template_raster) as templ_ds:        
        meta = templ_ds.meta
        
    buvolprop_stack[np.isnan(buvolprop_stack)]=0
            
    for ii,mi_scenario in enumerate(mi_scenarios):
        gtiff_total = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
        gtiff_gasstat = os.path.join(outputs_temp, 'combust_component_mi_%s_comb_mass_gas_stations.tif' %(mi_scenario))
        gtiff_raffin = os.path.join(outputs_temp, 'combust_component_mi_%s_comb_mass_raffineries.tif' %(mi_scenario))

        cm_total_arr = gdal.Open(gtiff_total).ReadAsArray()
        cm_gasstat_arr = gdal.Open(gtiff_gasstat).ReadAsArray()
        cm_raffin_arr = gdal.Open(gtiff_raffin).ReadAsArray()
        
        cm_total_arr[np.isnan(cm_total_arr)]=0
        cm_gasstat_arr[np.isnan(cm_gasstat_arr)]=0
        cm_raffin_arr[np.isnan(cm_raffin_arr)]=0
       
        cm_bldgs_arr = cm_total_arr - cm_gasstat_arr - cm_raffin_arr

        for i,butype in enumerate(crosswalk_df_buildingtypes.tiff_type.unique()):
            cm_bldgs_arr_curr_bldg_type = cm_bldgs_arr*buvolprop_stack[:,:,i]            
            # Write to TIFF
            outfile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_disaggr_bldgtype_t_%s.tif' %(mi_scenario,butype))
            meta.update(
                 dtype=rasterio.float32,
                 count=1,
                 compress='lzw')            
            with rasterio.open(outfile, 'w', **meta) as dst:
                 dst.write_band(1, cm_bldgs_arr_curr_bldg_type.astype(rasterio.float32))  
            print('disaggregated',mi_scenario,butype)

    outstats=[]
    # cm per capita stats
    for ii,mi_scenario in enumerate(mi_scenarios):
        for i,butype in enumerate(crosswalk_df_buildingtypes.tiff_type.unique()):
            outfile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_disaggr_bldgtype_t_%s.tif' %(mi_scenario,butype))
            cm_arr = gdal.Open(outfile).ReadAsArray()
            cm_cap = np.nansum(cm_arr) / uspop2020#
            print(mi_scenario,butype,cm_cap)
            outstats.append([mi_scenario,butype,cm_cap])
    outstatsdf=pd.DataFrame(outstats)
    outstatsdf.to_csv(outputs_final+os.sep+'cm_per_cap_disaggr_bldgtype.csv',index=False)
    
if convert_biomass_to_fuel:

    counties_id_rast = gdal.Open(in_surface_fips_codes).ReadAsArray()

    with rasterio.open(template_raster) as templ_ds:        
        meta = templ_ds.meta 
        
    inarr = gdal.Open(inrast_spawn_above_res).ReadAsArray()  
    inarr[inarr==65535]=0
    inarr=inarr*2 #since carbon is only 50percent of fuel
    inarr=inarr*6.25 #unit is mG C per hectare. we convert the density to the total per 250 m cell (250mx250m=62500 sqm = 6.25 ha)
    inarr[counties_id_rast==-1]=0   
    above = inarr.copy()
    outfile = os.path.join(outputs_temp, 'combustible_biomass_aboveground_t_2010.tif' )
    meta.update(
         dtype=rasterio.float32,
         count=1,
         compress='lzw')            
    with rasterio.open(outfile, 'w', **meta) as dst:
         dst.write_band(1, inarr.astype(rasterio.float32))     

    inarr = gdal.Open(inrast_spawn_below_res).ReadAsArray()  
    inarr[inarr==65535]=0
    inarr=inarr*2 #since carbon is only 50percent of fuel
    inarr=inarr*6.25 #unit is mG C per hectare. we convert the density to the total per 250 m cell (250mx250m=62500 sqm = 6.25 ha)
    inarr[counties_id_rast==-1]=0  
    below = inarr.copy()
    outfile = os.path.join(outputs_temp, 'combustible_biomass_belowground_t_2010.tif' )
    meta.update(
         dtype=rasterio.float32,
         count=1,
         compress='lzw')            
    with rasterio.open(outfile, 'w', **meta) as dst:
         dst.write_band(1, inarr.astype(rasterio.float32))
         
    ####combined above and below ground combustible biomass:
    biomass_total = above + below 
    outfile = os.path.join(outputs_temp, 'combustible_biomass_total_t_2010.tif' )
    meta.update(
         dtype=rasterio.float32,
         count=1,
         compress='lzw')            
    with rasterio.open(outfile, 'w', **meta) as dst:
         dst.write_band(1, biomass_total.astype(rasterio.float32))    
         
    comb_biomass_aboveground_per_capita = np.sum(above) / uspop2020#
    comb_biomass_belowground_per_capita = np.sum(below) / uspop2020#
    comb_biomass_combined_per_capita = np.sum(biomass_total) / uspop2020#
    print('comb_biomass_aboveground_per_capita',comb_biomass_aboveground_per_capita)
    print('comb_biomass_belowground_per_capita',comb_biomass_belowground_per_capita)
    print('comb_biomass_combined_per_capita',comb_biomass_combined_per_capita)

    cm_total_mean = os.path.join(outputs_temp, 'combust_imputed_mi_ALL_cm_overall_t_mean.tif' )
    cm_total_mean_arr = gdal.Open(cm_total_mean).ReadAsArray()  

    comb_biomass_aboveground_per_capita = np.sum(above[cm_total_mean_arr>0]) / uspop2020#
    comb_biomass_belowground_per_capita = np.sum(below[cm_total_mean_arr>0]) / uspop2020#
    comb_biomass_combined_per_capita = np.sum(biomass_total[cm_total_mean_arr>0]) / uspop2020#
    print('comb_biomass_aboveground_per_capita, in built-up areas',comb_biomass_aboveground_per_capita)
    print('comb_biomass_belowground_per_capita, in built-up areas',comb_biomass_belowground_per_capita)
    print('comb_biomass_combined_per_capita, in built-up areas',comb_biomass_combined_per_capita)        

if produce_vehicle_fuel_layers_contemp:
    
    ########### car CONTEMP combustible mass estimates from Toon et al (in prep), Davis and Boundy, 2021 Table 4.20
    cars_per_person = 0.84
    cm_avg_car_total_kg = 461
    cm_avg_car_plastic_kg = 155 
    cm_avg_car_rubber_kg = 93 
    cm_avg_car_fuel_lubricants_fluids_kg = 100 
    total_mass_avg_car_kg = 1793.051
    #############################################################################

    ghs_pop_tif = outputs_temp + os.sep + 'ghs_pop_%s_res.tif' %2020
    pop_arr = gdal.Open(ghs_pop_tif).ReadAsArray() 
    pop_arr[pop_arr<0]=0
    
    mi_scenario='mean'
    gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
    cm_arr = gdal.Open(gtiff).ReadAsArray()     
    pop_arr[np.logical_not(cm_arr>0)]=0 # need to set MX and CAN to zero
    
    non_comb_mass_avg_car_kg =total_mass_avg_car_kg - cm_avg_car_total_kg
    
    outarr_car_cm_total = pop_arr.copy()
    outarr_car_cm_total*= cars_per_person*cm_avg_car_total_kg / 1000.0
    outarr_car_cm_plastic = pop_arr.copy()
    outarr_car_cm_plastic*= cars_per_person*cm_avg_car_plastic_kg / 1000.0
    outarr_car_cm_rubber = pop_arr.copy()
    outarr_car_cm_rubber*= cars_per_person*cm_avg_car_rubber_kg / 1000.0   
    outarr_car_cm_fuel_etc = pop_arr.copy()
    outarr_car_cm_fuel_etc*= cars_per_person*cm_avg_car_fuel_lubricants_fluids_kg  / 1000.0  
    outarr_car_non_combmass = pop_arr.copy()
    outarr_car_non_combmass*= cars_per_person*non_comb_mass_avg_car_kg / 1000.0 
    
    outarrays=[]
    outarrays.append([outarr_car_cm_total,'car_cm_total_t'])
    outarrays.append([outarr_car_cm_plastic,'car_cm_plastic_t'])
    outarrays.append([outarr_car_cm_rubber,'car_cm_rubber_t'])
    outarrays.append([outarr_car_cm_fuel_etc,'car_cm_fluidlubricants_etc_t'])
    outarrays.append([outarr_car_non_combmass,'car_non_combmass_t'])
        
    with rasterio.open(template_raster) as templ_ds:        
        meta = templ_ds.meta 
        
    for outarray in outarrays:
        outfile = os.path.join(outputs_temp, 'combust_%s_2020.tif' % outarray[1])
        meta.update(
             dtype=rasterio.float32,
             count=1,
             compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
             dst.write_band(1, outarray[0].astype(rasterio.float32))        
        print('exported', outarray[1]) 

if produce_vehicle_fuel_layers_backcast:
    
    ########## now do MULTITEMPORAL ##########
    x_interpol = np.arange(1970,2021,1)
    years_backcast_car_fuel = np.arange(1975,2016,5)
    
    car_data_df=pd.read_csv(car_data_csv)
    mean_cm_car = 0.5*(car_data_df.loc[car_data_df.year==1995,'cm_car_kg'].values[0]+car_data_df.loc[car_data_df.year==2000,'cm_car_kg'].values[0])
    mean_tm_car = 0.5*(car_data_df.loc[car_data_df.year==1995,'total_m_car_kg'].values[0]+car_data_df.loc[car_data_df.year==2000,'total_m_car_kg'].values[0])

    mean_cm_car_plastic = 0.5*(car_data_df.loc[car_data_df.year==1995,'cm_car_kg_plastic'].values[0]+car_data_df.loc[car_data_df.year==2000,'cm_car_kg_plastic'].values[0])
    mean_cm_car_rubber = 0.5*(car_data_df.loc[car_data_df.year==1995,'cm_car_kg_rubber'].values[0]+car_data_df.loc[car_data_df.year==2000,'cm_car_kg_rubber'].values[0])
    mean_cm_car_fluidlubricants = 0.5*(car_data_df.loc[car_data_df.year==1995,'cm_car_kg_fluidlubricants'].values[0]+car_data_df.loc[car_data_df.year==2000,'cm_car_kg_fluidlubricants'].values[0])

    row19975=[[1997.5,np.nan,np.nan,mean_cm_car,mean_tm_car,mean_cm_car_plastic,mean_cm_car_rubber,mean_cm_car_fluidlubricants]]
    row19975df=pd.DataFrame(row19975,columns=car_data_df.columns)
    car_data_df=pd.concat([car_data_df,row19975df])
    car_data_df=car_data_df.sort_values(by='year')
    car_data_df['combmass_rate']=car_data_df.cm_car_kg/car_data_df.total_m_car_kg
    
    yeardf=pd.DataFrame()
    yeardf['year']=x_interpol
    car_data_df_interpol = pd.merge(yeardf,car_data_df,on='year',how='left')
    cars_per_pop_df=pd.read_csv(cars_per_pop_csv)    
    car_data_df_interpol = car_data_df_interpol.merge(cars_per_pop_df,on='year',how='left')
    

    for incol in ['cm_car_kg', 'total_m_car_kg', 'combmass_rate','cm_car_kg_plastic','cm_car_kg_rubber','cm_car_kg_fluidlubricants']:
        x=car_data_df_interpol.dropna(subset=[incol]).year.values 
        y=car_data_df_interpol.dropna(subset=[incol])[incol].values
        m,b = np.polyfit(x, y, 1)
        incol_interpol_1975 = b+m*1970
        car_data_df_interpol.loc[car_data_df_interpol.year==1970,incol]=incol_interpol_1975
        
    for incol in ['veh_per_1k_pop','cm_car_kg', 'total_m_car_kg', 'combmass_rate','cm_car_kg_plastic','cm_car_kg_rubber','cm_car_kg_fluidlubricants']:
        x=car_data_df_interpol.dropna(subset=[incol]).year.values 
        y=car_data_df_interpol.dropna(subset=[incol])[incol].values
        m,b = np.polyfit(x, y, 1)
        incol_interpol_2020 = b+m*2020
        car_data_df_interpol.loc[car_data_df_interpol.year==2020,incol]=incol_interpol_2020
        
    for incol in ['veh_per_1k_pop','cm_car_kg', 'total_m_car_kg', 'combmass_rate','cm_car_kg_plastic','cm_car_kg_rubber','cm_car_kg_fluidlubricants']:
        outcol=incol+'_interpol'
        car_data_df_interpol[outcol]=car_data_df_interpol[incol].interpolate()
        print(car_data_df_interpol[outcol].values)

    for year in years_backcast_car_fuel:
        ########### car BACKCAST combustible mass estimates from Toon et al (in prep), Davis and Boundy, 2021 Table 4.20 and table 3.8
        cars_per_person = car_data_df_interpol[car_data_df_interpol.year==year].veh_per_1k_pop_interpol.values[0]/1000.0
        cm_avg_car_total_kg = car_data_df_interpol[car_data_df_interpol.year==year].cm_car_kg_interpol.values[0]
        total_mass_avg_car_kg = car_data_df_interpol[car_data_df_interpol.year==year].total_m_car_kg_interpol.values[0]

        cm_avg_car_plastic_kg = car_data_df_interpol[car_data_df_interpol.year==year].cm_car_kg_plastic_interpol.values[0]
        cm_avg_car_rubber_kg = car_data_df_interpol[car_data_df_interpol.year==year].cm_car_kg_rubber_interpol.values[0]
        cm_avg_car_fuel_lubricants_fluids_kg = car_data_df_interpol[car_data_df_interpol.year==year].cm_car_kg_fluidlubricants_interpol.values[0]

        #############################################################################
        
        print(year,cars_per_person,cm_avg_car_total_kg,total_mass_avg_car_kg,cm_avg_car_plastic_kg,cm_avg_car_rubber_kg,cm_avg_car_fuel_lubricants_fluids_kg)
    
        ghs_pop_tif = outputs_temp + os.sep + 'ghs_pop_%s_res.tif' %year
        pop_arr = gdal.Open(ghs_pop_tif).ReadAsArray() 
        pop_arr[pop_arr<0]=0
        
        mi_scenario='mean'
        gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
        cm_arr = gdal.Open(gtiff).ReadAsArray()     
        pop_arr[np.logical_not(cm_arr>0)]=0 # need to set MX and CAN to zero
        
        non_comb_mass_avg_car_kg =total_mass_avg_car_kg - cm_avg_car_total_kg
        
        outarr_car_cm_total = pop_arr.copy()
        outarr_car_cm_total*= cars_per_person*cm_avg_car_total_kg / 1000.0
        outarr_car_cm_plastic = pop_arr.copy()
        outarr_car_cm_plastic*= cars_per_person*cm_avg_car_plastic_kg / 1000.0
        outarr_car_cm_rubber = pop_arr.copy()
        outarr_car_cm_rubber*= cars_per_person*cm_avg_car_rubber_kg / 1000.0   
        outarr_car_cm_fuel_etc = pop_arr.copy()
        outarr_car_cm_fuel_etc*= cars_per_person*cm_avg_car_fuel_lubricants_fluids_kg  / 1000.0  
        outarr_car_non_combmass = pop_arr.copy()
        outarr_car_non_combmass*= cars_per_person*non_comb_mass_avg_car_kg / 1000.0 
        
        outarrays=[]
        outarrays.append([outarr_car_cm_total,'car_cm_total_t'])
        outarrays.append([outarr_car_cm_plastic,'car_cm_plastic_t'])
        outarrays.append([outarr_car_cm_rubber,'car_cm_rubber_t'])
        outarrays.append([outarr_car_cm_fuel_etc,'car_cm_fluidlubricants_etc_t'])
        outarrays.append([outarr_car_non_combmass,'car_non_combmass_t'])
            
        with rasterio.open(template_raster) as templ_ds:        
            meta = templ_ds.meta 
            
        for outarray in outarrays:
            outfile = os.path.join(outputs_temp, 'combust_%s_%s.tif' % (outarray[1],year))
            meta.update(
                 dtype=rasterio.float32,
                 count=1,
                 compress='lzw')            
            with rasterio.open(outfile, 'w', **meta) as dst:
                 dst.write_band(1, outarray[0].astype(rasterio.float32))        
            print('exported', outarray[1])   
        
if hindcast_total_combmass_layer_GHSL:
    
    warp_clip_ghsl=False #run in gdalnew env, we need gdalwarp with sum resampling
    hindcast_combust=True
    if hindcast_combust:
        use_volume_gradient=True
        use_surface_gradient=False
    
    if warp_clip_ghsl: 
    
        # warp ghs-pop and ghs-built-v to the hisdac grid using gdalwarp sum resampling

        for year in ghsl_years:       
            in_ghs_vol = ghsl_dir + os.sep + ghsl_vol_template.replace('YYYY',str(year))
            in_ghs_bu = ghsl_dir + os.sep + ghsl_busurf_template.replace('YYYY',str(year))
            in_ghs_pop = ghsl_dir + os.sep + ghsl_pop_template.replace('YYYY',str(year))
            
            in_ghs_vol_clip=outputs_temp + os.sep + 'ghs_v_%s_clip.tif' %year
            in_ghs_vol_res=outputs_temp + os.sep + 'ghs_v_%s_res.tif' %year
    
            in_ghs_bu_clip=outputs_temp + os.sep + 'ghs_s_%s_clip.tif' %year
            in_ghs_bu_res=outputs_temp + os.sep + 'ghs_s_%s_res.tif' %year
            
            in_ghs_pop_clip=outputs_temp + os.sep + 'ghs_pop_%s_clip.tif' %year
            in_ghs_pop_res=outputs_temp + os.sep + 'ghs_pop_%s_res.tif' %year
            
            # clip rasters to CONUS
            with rasterio.open(template_raster) as templ_ds:        
                crs_grid = rasterio.crs.CRS(templ_ds.crs).to_epsg()
                bbox_target = templ_ds.bounds
            geom = box(*bbox_target)
            bbox_target_gdf = gp.GeoDataFrame(geometry=[geom],crs=crs_grid)
            crs_source = mollw_proj4
            target_bounds  = bbox_target_gdf.total_bounds
            bbox_target_gdf = bbox_target_gdf.to_crs(crs_source)
            bbox_target_gdf.geometry = bbox_target_gdf.geometry.buffer(400000) #buffer the polygon by 400km, otherwise we cut off relevant stuff.
            extract_bounds = bbox_target_gdf.total_bounds
            ulx = extract_bounds[0]
            uly = extract_bounds[3]
            lrx = extract_bounds[2]
            lry = extract_bounds[1]  
            xmin = target_bounds[0]
            ymin = target_bounds[1]
            xmax = target_bounds[2]
            ymax = target_bounds[3] 
            
            raster_subset(in_ghs_vol,in_ghs_vol_clip,ulx,uly,lrx,lry)
            raster_warp(in_ghs_vol_clip,in_ghs_vol_res,xmin,ymin,xmax,ymax,crs_grid,'sum')
    
            raster_subset(in_ghs_bu,in_ghs_bu_clip,ulx,uly,lrx,lry)
            raster_warp(in_ghs_bu_clip,in_ghs_bu_res,xmin,ymin,xmax,ymax,crs_grid,'sum')
    
            raster_subset(in_ghs_pop,in_ghs_pop_clip,ulx,uly,lrx,lry)
            raster_warp(in_ghs_pop_clip,in_ghs_pop_res,xmin,ymin,xmax,ymax,crs_grid,'sum')            
            
        
    if hindcast_combust:
        
        # load ghs-built-v-250m_conus into stack
        for year in ghsl_years:   
            if use_volume_gradient:
                in_ghs_vol_res=outputs_temp + os.sep + 'ghs_v_%s_res.tif' %year
            if use_surface_gradient:
                in_ghs_vol_res=outputs_temp + os.sep + 'ghs_s_%s_res.tif' %year
                
            if year==1975:
                ghs_v_stack=gdal.Open(in_ghs_vol_res).ReadAsArray()
            else:
                ghs_v_stack=np.dstack((ghs_v_stack,gdal.Open(in_ghs_vol_res).ReadAsArray()))
            print('read ghsl volume %s' %year)

        # calculate change w.r.t. 2020        
        ghs_v_stack_wrt2020=np.zeros(ghs_v_stack.shape)
        ghsl_ref_epoch = ghs_v_stack[:,:,-1]
        for i,year in enumerate(ghsl_years):
            ghs_v_stack_wrt2020[:,:,i]=np.divide(ghs_v_stack[:,:,i],ghsl_ref_epoch)
            print(year)
        ghs_v_stack_wrt2020[np.isnan(ghs_v_stack_wrt2020)]=0       
        
        # apply changes to the 2020 COMBUST surface
            
        with rasterio.open(template_raster) as templ_ds:        
            meta = templ_ds.meta
        del ghs_v_stack

        for i,mi_scenario in enumerate(mi_scenarios):
            gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
            combust_2020_arr = gdal.Open(gtiff).ReadAsArray()
            
            for i,year in enumerate(ghsl_years):
                multiplic_surface=ghs_v_stack_wrt2020[:,:,i]
                multiplic_surface[combust_2020_arr==0]=0 # we disregard cells >0 in GHSL but ==0 in combust.
                combust_backcasted=combust_2020_arr*multiplic_surface

                force_nbu=False
                if force_nbu:
                    # set not built-up in ghsl explicitly to 0 in combust
                    # does not work because ghs-built-s never switches to NBU.
                    in_ghs_s_res=outputs_temp + os.sep + 'ghs_s_%s_res.tif' %year
                    in_ghs_s_arr=gdal.Open(in_ghs_s_res).ReadAsArray()
                    combust_backcasted[in_ghs_s_arr<100]=0 #using a threshold >0 erases valid rural settlements.
                    
                # Write to TIFF
                if use_volume_gradient:
                    outfile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_ghsvol_%s.tif' %(mi_scenario,year))
                if use_surface_gradient:
                    outfile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_ghssurf_%s.tif' %(mi_scenario,year))
                                
                meta.update(
                     dtype=rasterio.float32,
                     count=1,
                     compress='lzw')            
                with rasterio.open(outfile, 'w', **meta) as dst:
                     dst.write_band(1, combust_backcasted.astype(rasterio.float32))          
                
                print('backcasted %s %s' %(mi_scenario,year))
                
        #cm per capita cross check over time
        popvals=[uspop1975,uspop1990,uspop2020]
        for i,mi_scenario in enumerate(mi_scenarios):
            for ii,year in enumerate([1975,1990,2020]):
                if use_volume_gradient:
                    infile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_ghsvol_%s.tif' %(mi_scenario,year))
                if use_surface_gradient:
                    infile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_ghssurf_%s.tif' %(mi_scenario,year))
                                
                cm_arr = gdal.Open(infile).ReadAsArray()
                cm_arr[cm_arr == np.inf] = 0
                cm_sum = np.nansum(cm_arr)
                cm_per_cap = cm_sum / popvals[ii]
                print(mi_scenario,year,'cm per cap',cm_per_cap)
   
        for i,mi_scenario in enumerate(mi_scenarios):
            gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
            combust_2020_arr = gdal.Open(gtiff).ReadAsArray()    
            cm_sum = np.nansum(combust_2020_arr)
            cm_per_cap = cm_sum / uspop2020
            print(mi_scenario,2020,'cm per cap 2020 orig',cm_per_cap)   
            
            
            
if hindcast_total_combmass_layer_HISDAC: ####################################################################

    do_backcast_based_on_bui_rates = True
    do_backcast_based_on_BUPL_rates = True
                
    if do_backcast_based_on_bui_rates:
        
        hisdac_backcast_years=np.arange(1975,2021,5)

        with rasterio.open(template_raster) as templ_ds:        
            meta = templ_ds.meta
            
        for year in hisdac_backcast_years:
            if year==2020:
                bui_v1 = hisdacus_v1_bui_template.replace('YYYY',str(year-5))
            else:
                bui_v1 = hisdacus_v1_bui_template.replace('YYYY',str(year))  
            bui_v2 = hisdacus_v2_bui_template.replace('YYYY',str(year))
            bui_v1_arr = gdal.Open(bui_v1).ReadAsArray() 
            bui_v2_arr = gdal.Open(bui_v2).ReadAsArray() 
            bui_conflated = np.maximum(bui_v1_arr,bui_v2_arr)
            if year==hisdac_backcast_years[0]:
                bui_stack=bui_conflated
            else:
                bui_stack=np.dstack((bui_stack,bui_conflated))
            print('read hisdac-us bui %s, conflate v1 and v2' %year)
            
            
        # calculate change w.r.t. 2020        
        bui_stack_wrt2020=np.zeros(bui_stack.shape)
        bui_ref_epoch = bui_stack[:,:,-1]
        for i,year in enumerate(hisdac_backcast_years):
            bui_stack_wrt2020[:,:,i]=np.divide(bui_stack[:,:,i],bui_ref_epoch)
            print(year)
        bui_stack_wrt2020[np.isnan(bui_stack_wrt2020)]=0       
        
        # apply changes to the 2020 COMBUST surface

        del bui_stack

        for i,mi_scenario in enumerate(mi_scenarios):
            gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
            combust_2020_arr = gdal.Open(gtiff).ReadAsArray()
            
            for i,year in enumerate(ghsl_years):
                multiplic_surface=bui_stack_wrt2020[:,:,i]
                multiplic_surface[combust_2020_arr==0]=0 # we disregard cells >0 in bui but ==0 in combust.
                combust_backcasted=combust_2020_arr*multiplic_surface

                # Write to TIFF
                outfile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_hisdac_bui_%s_v2.tif' %(mi_scenario,year))
                meta.update(
                     dtype=rasterio.float32,
                     count=1,
                     compress='lzw')            
                with rasterio.open(outfile, 'w', **meta) as dst:
                     dst.write_band(1, combust_backcasted.astype(rasterio.float32))          
                
                print('backcasted %s %s' %(mi_scenario,year))
                   

    if do_backcast_based_on_BUPL_rates:
        
        hisdac_backcast_years=np.arange(1975,2021,5)

        with rasterio.open(template_raster) as templ_ds:        
            meta = templ_ds.meta
            
        for year in hisdac_backcast_years:
            if year==2020:
                bui_v1 = hisdacus_v1_bupl_template.replace('YYYY',str(year-5))
            else:
                bui_v1 = hisdacus_v1_bupl_template.replace('YYYY',str(year))                
            bui_v2 = hisdacus_v2_bupl_template.replace('YYYY',str(year))
            bui_v1_arr = gdal.Open(bui_v1).ReadAsArray().astype(np.int16)
            bui_v2_arr = gdal.Open(bui_v2).ReadAsArray().astype(np.int16) 
            bui_conflated = np.maximum(bui_v1_arr,bui_v2_arr).astype(np.int16)
            if year==hisdac_backcast_years[0]:
                bui_stack=bui_conflated
            else:
                bui_stack=np.dstack((bui_stack,bui_conflated))
            print('read hisdac-us bupl %s, conflate v1 and v2' %year)
            
            
        # calculate change w.r.t. 2020        
        bui_stack_wrt2020=np.zeros(bui_stack.shape)
        bui_ref_epoch = bui_stack[:,:,-1]
        for i,year in enumerate(hisdac_backcast_years):
            bui_stack_wrt2020[:,:,i]=np.divide(bui_stack[:,:,i],bui_ref_epoch)
            print(year)
        bui_stack_wrt2020[np.isnan(bui_stack_wrt2020)]=0       
        
        # apply changes to the 2020 COMBUST surface

        del bui_stack

        for i,mi_scenario in enumerate(mi_scenarios):
            gtiff = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
            combust_2020_arr = gdal.Open(gtiff).ReadAsArray()
            
            for i,year in enumerate(ghsl_years):
                multiplic_surface=bui_stack_wrt2020[:,:,i]
                multiplic_surface[combust_2020_arr==0]=0 # we disregard cells >0 in bui but ==0 in combust.
                combust_backcasted=combust_2020_arr*multiplic_surface

                # Write to TIFF
                outfile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_hisdac_bupl_%s.tif' %(mi_scenario,year))
                meta.update(
                     dtype=rasterio.float32,
                     count=1,
                     compress='lzw')            
                with rasterio.open(outfile, 'w', **meta) as dst:
                     dst.write_band(1, combust_backcasted.astype(rasterio.float32))          
                
                print('backcasted %s %s' %(mi_scenario,year))
      

    
if copy_rename_final_outputs:
    
    outputs_final_orig=outputs_final
    outputs_final=outputs_final+os.sep+'GEOTIFF'   
    years_car_materials_disaggr = np.arange(1995,2021,5)
    years_car_overall = np.arange(1975,2021,5)
    years_combust_backcasted_hisdac = np.arange(1999,2021,1)
    years_combust_backcasted_ghsl = np.arange(1975,2021,5)
   
    ####################
    
    crosswalk_df_buildingtypes = pd.read_csv(crosswalk_csv_frantz_buildingtypes)    
    bldg_type_lookup = dict(zip(crosswalk_df_buildingtypes.tiff_type,crosswalk_df_buildingtypes.mi_category))      
    with rasterio.open(template_raster) as templ_ds:        
        meta = templ_ds.meta
        
    #################### biomass, population, model std dev      
        
    infile = os.path.join(outputs_temp, 'combustible_biomass_total_t_2010.tif' )
    outfile = os.path.join(outputs_final, 'combust_plus_combustible_biomass_total_2010.tif' )
    shutil.copy2(infile, outfile)    
    infile = os.path.join(outputs_temp, 'combustible_biomass_aboveground_t_2010.tif' )
    outfile = os.path.join(outputs_final, 'combust_plus_combustible_biomass_aboveground_2010.tif' )
    shutil.copy2(infile, outfile)    
    infile = os.path.join(outputs_temp, 'combustible_biomass_belowground_t_2010.tif' )
    outfile = os.path.join(outputs_final, 'combust_plus_combustible_biomass_belowground_2010.tif' )
    shutil.copy2(infile, outfile)
    for year in np.arange(1975,2021,5):
        infile = outputs_temp + os.sep + 'ghs_pop_%s_res.tif' %year
        outfile = os.path.join(outputs_final, 'combust_plus_resident_population_%s.tif' %year)
        
        inarr=gdal.Open(infile).ReadAsArray()
        inarr[inarr==-200]=0        
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw',
              nodata=-200)            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, inarr.astype(rasterio.float32))         
        # shutil.copy2(infile, outfile) 
                 
    #################### CAR data ####################
    
    outarrays=[]
    outarrays.append(['car_cm_total_t'])
    outarrays.append(['car_cm_plastic_t'])
    outarrays.append(['car_cm_rubber_t'])
    outarrays.append(['car_cm_fluidlubricants_etc_t'])
    outarrays.append(['car_non_combmass_t'])
    for outarray in outarrays:
        infile = os.path.join(outputs_temp, 'combust_%s_2020.tif' % outarray[0])
        outfile = os.path.join(outputs_final, 'combust_cm_%s_2020.tif' % outarray[0].replace('_cm_','_').replace('_etc',''))        
        if 'combust_cm_car_non_combmass_t_2020.tif' in outfile:
            outfile = os.path.join(outputs_final, 'combust_noncombust_car_non_combmass_t_2020.tif')            
        shutil.copy2(infile, outfile)  
        
    for year in years_car_materials_disaggr:
        for outarray in outarrays:
            infile = os.path.join(outputs_temp, 'combust_%s_%s.tif' %(outarray[0],year))
            outfile = os.path.join(outputs_final, 'combust_cm_%s_%s.tif' % (outarray[0].replace('_cm_','_').replace('_etc',''),year))      
            if 'combust_cm_car_non_combmass_t_%s.tif' %year in outfile:
                outfile = os.path.join(outputs_final, 'combust_noncombust_car_non_combmass_t_%s.tif' %year)            
            shutil.copy2(infile, outfile)          

    outarrays=[]
    outarrays.append(['car_cm_total_t'])
    outarrays.append(['car_non_combmass_t'])

    for year in years_car_overall:
        for outarray in outarrays:
            infile = os.path.join(outputs_temp, 'combust_%s_%s.tif' %(outarray[0],year))
            outfile = os.path.join(outputs_final, 'combust_cm_%s_%s.tif' % (outarray[0].replace('_cm_','_').replace('_etc',''),year))      
            if 'combust_cm_car_non_combmass_t_%s.tif' %year in outfile:
                outfile = os.path.join(outputs_final, 'combust_noncombust_car_non_combmass_t_%s.tif' %year)            
            shutil.copy2(infile, outfile)  
            
    #################### COMBMASS merged with CAR combmass and other components CONTEMP
    
    for ii,mi_scenario in enumerate(mi_scenarios):
        
        infile1 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
        infile2 = os.path.join(outputs_final, 'combust_cm_car_total_t_2020.tif')
        outfile = os.path.join(outputs_final, 'combust_cm_total_scenario_%s_2020.tif' %(mi_scenario))
        # need to add the total car cm to that:
        inarr1=gdal.Open(infile1).ReadAsArray()
        inarr2=gdal.Open(infile2).ReadAsArray()
        outarr=inarr1+inarr2   
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, outarr.astype(rasterio.float32)) 

        infile = os.path.join(outputs_temp, 'combust_component_mi_%s_comb_mass_gas_stations.tif' %(mi_scenario))
        outfile = os.path.join(outputs_final, 'combust_cm_gasstations_2020.tif')
        shutil.copy2(infile, outfile)     

        infile = os.path.join(outputs_temp, 'combust_component_mi_%s_comb_mass_raffineries.tif' %(mi_scenario))
        outfile = os.path.join(outputs_final, 'combust_cm_refineries_2020.tif')
        shutil.copy2(infile, outfile)   
        
        infile = os.path.join(outputs_temp, 'combust_component_mi_%s_%s.tif' %(mi_scenario,'ind_bldg_combmass_contemp_t_orig_and_imputed_values'))
        outfile = os.path.join(outputs_final, 'combust_cm_buildingcontent_total_2020.tif' )
        shutil.copy2(infile, outfile)  

        infile = os.path.join(outputs_temp, 'combust_component_mi_%s_combust_total_mass_ext.tif' %(mi_scenario))
        outfile = os.path.join(outputs_final, 'combust_cm_buildingmaterial_all_scenario_%s_2020.tif' %(mi_scenario))
        # shutil.copy2(infile, outfile)    
        # need to convert kg to tons:
        inarr1=gdal.Open(infile).ReadAsArray()
        outarr=inarr1/1000.0   
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, outarr.astype(rasterio.float32)) 
        
    for ii,mi_scenario in enumerate(mi_scenarios):

        for i,butype in enumerate(crosswalk_df_buildingtypes.tiff_type.unique()):
            infile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_disaggr_bldgtype_t_%s.tif' %(mi_scenario,butype))
            outfile = os.path.join(outputs_final, 'combust_cm_building_%s_scenario_%s_2020.tif' %(butype,mi_scenario))
            shutil.copy2(infile, outfile)               
        for export_column in export_columns_noncombmass:
            if 'mass' in export_column:
                target_unit='t'
                divideby=1000.0
            if 'volume' in export_column:
                target_unit='m3'
                divideby=1.0                
            infile = os.path.join(outputs_temp, 'combust_noncombust_mi_%s_%s_%s.tif' %(mi_scenario,export_column,target_unit))
            outfile = os.path.join(outputs_final, 'combust_noncombust_%s_%s_%s.tif' %(mi_scenario,export_column,target_unit))
            shutil.copy2(infile, outfile)               

    ### surfaces by material type (building material)
    for mi_scenario in mi_scenarios:
        for flamm_mat in flamm_materials:
            matname_out = flamm_mat.replace(' ','_').replace('-','_')
            infile = os.path.join(outputs_temp, 'combust_component_mi_%s_total_cm_%s.tif' %(mi_scenario,matname_out))
            outfile = os.path.join(outputs_final, 'combust_cm_buildingmaterial_%s_scenario_%s.tif' %(matname_out,mi_scenario))
            # shutil.copy2(infile, outfile)   
            # need to convert kg to tons:
            inarr=gdal.Open(infile).ReadAsArray()
            outarr=inarr   
            meta.update(
                  dtype=rasterio.float32,
                  count=1,
                  compress='lzw')            
            with rasterio.open(outfile, 'w', **meta) as dst:
                  dst.write_band(1, outarr.astype(rasterio.float32))  
              
    for contentmat in bldg_content_materials:        
        infile = os.path.join(indoor_fuel_grids, 'urban_fuel_material_%s.tif' %contentmat)
        outfile = os.path.join(outputs_final, 'combust_cm_buildingcontent_%s.tif' %(contentmat))
        # shutil.copy2(infile, outfile)   
        # need to convert kg to tons:
        inarr=gdal.Open(infile).ReadAsArray()
        outarr=inarr/1000.0   
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, outarr.astype(rasterio.float32))         
        
    ############# hindcasted layers: #############

    for i,mi_scenario in enumerate(mi_scenarios):
        for i,year in enumerate(years_combust_backcasted_ghsl):
            infile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_ghsvol_%s.tif' %(mi_scenario,year))
            outfile = os.path.join(outputs_final, 'combust_cm_building_all_scenario_%s_backcasted_mod3_ghsl_%s.tif' %(mi_scenario,year))
            shutil.copy2(infile, outfile)               

    for i,mi_scenario in enumerate(mi_scenarios):
        for i,year in enumerate(years_combust_backcasted_ghsl):
            infile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_hisdac_bui_%s_v2.tif' %(mi_scenario,year))
            outfile = os.path.join(outputs_final, 'combust_cm_building_all_scenario_%s_backcasted_mod1_hisdacus_bui_%s.tif' %(mi_scenario,year))
            #shutil.copy2(infile, outfile)  
            # need to fix nan, inf issues:
            inarr=gdal.Open(infile).ReadAsArray()
            inarr[np.isnan(inarr)]=0
            inarr[np.isinf(inarr)]=0
            outarr=inarr  
            meta.update(
                  dtype=rasterio.float32,
                  count=1,
                  compress='lzw')            
            with rasterio.open(outfile, 'w', **meta) as dst:
                  dst.write_band(1, outarr.astype(rasterio.float32))   

    for i,mi_scenario in enumerate(mi_scenarios):
        for i,year in enumerate(years_combust_backcasted_ghsl):
            infile = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_hisdac_bupl_%s.tif' %(mi_scenario,year))
            outfile = os.path.join(outputs_final, 'combust_cm_building_all_scenario_%s_backcasted_mod2_hisdacus_bupl_%s.tif' %(mi_scenario,year))
            #shutil.copy2(infile, outfile)  
            # need to fix nan, inf issues:
            inarr=gdal.Open(infile).ReadAsArray()
            inarr[np.isnan(inarr)]=0
            inarr[np.isinf(inarr)]=0
            outarr=inarr  
            meta.update(
                  dtype=rasterio.float32,
                  count=1,
                  compress='lzw')            
            with rasterio.open(outfile, 'w', **meta) as dst:
                  dst.write_band(1, outarr.astype(rasterio.float32))  
                  
    #non-backcastable fuels for the model 2a (buibased)
    for i,mi_scenario in enumerate(mi_scenarios):                  
        gtiff_fuel2020 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
        combust_2020_arr = gdal.Open(gtiff_fuel2020).ReadAsArray()
        gtiff_backcastable2020 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_hisdac_bui_%s_v2.tif' %(mi_scenario,2020))
        combust_2020_backcastable_arr = gdal.Open(gtiff_backcastable2020).ReadAsArray()
        
        nonbackcastable_fuel=combust_2020_arr-combust_2020_backcastable_arr
        nonbackcastable_fuel[np.isnan(nonbackcastable_fuel)]=0
        nonbackcastable_fuel[np.isinf(nonbackcastable_fuel)]=0   
        
        #### write out non/backcastable fuel:
        outfile = os.path.join(outputs_final, 'combust_cm_building_all_scenario_%s_backcasted_mod1_hisdacus_bui_nonbackcastable.tif' %(mi_scenario))
     
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, nonbackcastable_fuel.astype(rasterio.float32)) 

    #non-backcastable fuels for the model 2b (bupl based)
    for i,mi_scenario in enumerate(mi_scenarios):                  
        gtiff_fuel2020 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
        combust_2020_arr = gdal.Open(gtiff_fuel2020).ReadAsArray()
        gtiff_backcastable2020 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_hisdac_bupl_%s.tif' %(mi_scenario,2020))
        combust_2020_backcastable_arr = gdal.Open(gtiff_backcastable2020).ReadAsArray()

        nonbackcastable_fuel=combust_2020_arr-combust_2020_backcastable_arr
        nonbackcastable_fuel[np.isnan(nonbackcastable_fuel)]=0
        nonbackcastable_fuel[np.isinf(nonbackcastable_fuel)]=0 
                
        #### write out non/backcastable fuel:
        outfile = os.path.join(outputs_final, 'combust_cm_building_all_scenario_%s_backcasted_mod2_hisdacus_bupl_nonbackcastable.tif' %(mi_scenario))
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, nonbackcastable_fuel.astype(rasterio.float32)) 
              
    #non-backcastable fuels for the model 3 (ghs-vol)

    for i,mi_scenario in enumerate(mi_scenarios): 
        gtiff_fuel2020 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t.tif' %(mi_scenario))
        combust_2020_arr = gdal.Open(gtiff_fuel2020).ReadAsArray()
        gtiff_backcastable2020 = os.path.join(outputs_temp, 'combust_imputed_mi_%s_cm_overall_t_backcasted_w_ghsvol_%s.tif' %(mi_scenario,2020))
        combust_2020_backcastable_arr = gdal.Open(gtiff_backcastable2020).ReadAsArray()

        nonbackcastable_fuel=combust_2020_arr-combust_2020_backcastable_arr
        nonbackcastable_fuel[np.isnan(nonbackcastable_fuel)]=0
        nonbackcastable_fuel[np.isinf(nonbackcastable_fuel)]=0 

        #### write out non/backcastable fuel:
        outfile = os.path.join(outputs_final, 'combust_cm_building_all_scenario_%s_backcasted_mod3_ghsl_nonbackcastable.tif' %(mi_scenario))
            
        meta.update(
              dtype=rasterio.float32,
              count=1,
              compress='lzw')            
        with rasterio.open(outfile, 'w', **meta) as dst:
              dst.write_band(1, nonbackcastable_fuel.astype(rasterio.float32)) 
    outputs_final=outputs_final_orig              

if get_final_layer_list:

    allfiles=[]
    for file in os.listdir(outputs_final+os.sep+'GEOTIFF'):
        print(file)
        allfiles.append(file)
    allfilesdf=pd.DataFrame(allfiles,columns=['filename'])    
    allfilesdf.to_csv(outputs_final+os.sep+'filelist.csv',index=False)
    # now open this csv file, add the zipfile1 column as desired, save as xlsx file, run next block.      

if zip_files:
    
    zipfile_df =pd.read_excel(outputs_final+os.sep+'filelist.xlsx')
    for zipfile_name,zdf in zipfile_df.groupby('zipfile1'):
        print(zipfile_name)

        filelist=zdf.filename.values
        indir = outputs_final+os.sep+'GEOTIFF'
        out_zip = outputs_final+os.sep+'ZIP'+os.sep+zipfile_name
        with zipfile.ZipFile(out_zip, mode="w") as archive:
              for filename in filelist:
                  print('zipping',zipfile_name,filename)
                  archive.write(os.path.join(indir,filename),filename)
               

if produce_mass_per_capita_stats_unitemp_mutemp_rucc:
    
    ### add stratification variables:
    counties_id_rast = gdal.Open(in_surface_fips_codes).ReadAsArray()
    counties_rucc_rast = gdal.Open(in_surface_rucc_codes).ReadAsArray()
    
    do_mutemp=True
    do_unitemp=True
    
    if do_mutemp:
            
        stats_per_cap=[]
        zipfile_df =pd.read_excel(outputs_final+os.sep+'filelist.xlsx')
        for zipfile_name,zdf in zipfile_df.groupby('zipfile1'):
            filelist=zdf.filename.values
            indir = outputs_final+os.sep+'GEOTIFF'
            for filename in filelist:
                if 'backcasted' in zipfile_name:
                    print(filename)
                    try:
                        year=int(filename.split('.')[0].split('_')[-1])
                    except:
                        continue
                   
                    cm_arr = gdal.Open(os.path.join(indir,filename)).ReadAsArray()                
                    ghstif=os.path.join(os.path.join(outputs_final,'GEOTIFF'), 'combust_plus_resident_population_%s.tif' %year)
                    poparr=gdal.Open(ghstif).ReadAsArray()
                    poparr[poparr<0]=0
                    for rucc in np.arange(1,10):
                        rucc_cm_sum = np.nansum(cm_arr[counties_rucc_rast==rucc]) 
                        rucc_pop_sum = np.nansum(poparr[np.logical_and(counties_rucc_rast==rucc,cm_arr>0)]) 
                        cm_cap=rucc_cm_sum/rucc_pop_sum
                        stats_per_cap.append([filename,year,rucc,rucc_cm_sum,rucc_pop_sum,cm_cap])
                        print(filename,year,rucc)

                    rucc='all'
                    rucc_cm_sum = np.nansum(cm_arr) 
                    rucc_pop_sum = np.nansum(poparr[cm_arr>0]) 
                    cm_cap=rucc_cm_sum/rucc_pop_sum
                    stats_per_cap.append([filename,year,rucc,rucc_cm_sum,rucc_pop_sum,cm_cap])
                    print(filename,year,rucc)                        
        stats_per_cap_df = pd.DataFrame(stats_per_cap,columns=['filename','year','rucc','cm_total','pop_sum','cm_per_cap'])
        stats_per_cap_df.to_csv(os.path.join(outputs_final,'stats_per_capita_rucc_mutemp.csv'),index=False)
        
    ###### stats for the car and unitemporal cm estimates: ########################
    
    if do_unitemp:
        stats_per_cap2=[]
        zipfile_df =pd.read_excel(outputs_final+os.sep+'filelist.xlsx')
        for zipfile_name,zdf in zipfile_df.groupby('zipfile1'):

            if 'plus' in zipfile_name or ('backcasted' in zipfile_name and not 'car' in zipfile_name) :
                continue
            
            print(zipfile_name)
    
            filelist=zdf.filename.values
            indir = outputs_final+os.sep+'GEOTIFF'
            for filename in filelist:

                if 'backcasted' in zipfile_name and not 'nonbackcastable' in filename:
                    continue

                cm_arr = gdal.Open(os.path.join(indir,filename)).ReadAsArray()                
                total = np.nansum(cm_arr)
                    
                if ('backcasted' in zipfile_name or 'car' in zipfile_name)  or 'combust_noncombust_car_non_combmass_t' in filename:
        
                    if not ('1975' in filename or '1990' in filename or '1999' in filename or '2000' in filename or '2020' in filename):
                        continue
                    if '1975' in filename:
                        ghstif=os.path.join(os.path.join(outputs_final,'GEOTIFF'), 'combust_plus_resident_population_%s.tif' %1975)
                        poparr=gdal.Open(ghstif).ReadAsArray()
                        poparr[poparr<0]=0
                        totpop=np.nansum(poparr[cm_arr>0])                    
                    if '1990' in filename:
                        ghstif = os.path.join(os.path.join(outputs_final,'GEOTIFF'), 'combust_plus_resident_population_%s.tif' %1990) 
                        poparr=gdal.Open(ghstif).ReadAsArray()
                        poparr[poparr<0]=0
                        totpop=np.nansum(poparr[cm_arr>0])                       
                    if '1999' in filename:
                        totpop = uspop1999                    
                    if '2000' in filename:
                        ghstif = os.path.join(os.path.join(outputs_final,'GEOTIFF'), 'combust_plus_resident_population_%s.tif' %2000)
                        poparr=gdal.Open(ghstif).ReadAsArray()
                        poparr[poparr<0]=0
                        totpop=np.nansum(poparr[cm_arr>0])                       
                    if '2020' in filename:
                        ghstif = os.path.join(os.path.join(outputs_final,'GEOTIFF'), 'combust_plus_resident_population_%s.tif' %2020)
                        poparr=gdal.Open(ghstif).ReadAsArray()
                        poparr[poparr<0]=0
                        totpop=np.nansum(poparr[cm_arr>0])  
                    print (totpop)    
                else:
                    totpop=uspop2020
                    total = np.nansum(cm_arr)
    
                cm_per_cap = total / totpop
                print(filename,cm_per_cap)
                scenario='NA'
                if '_high_' in filename:
                    scenario='high'
                if '_mean_' in filename:
                    scenario='mean'                
                if '_low_' in filename:
                    scenario='low'                
                stats_per_cap2.append([zipfile_name,filename,scenario,total,cm_per_cap])


        # get the nonbackcastable cm
        for zipfile_name,zdf in zipfile_df.groupby('zipfile1'):

            if not 'backcasted' in zipfile_name:
                continue
            
            print(zipfile_name)
    
            filelist=zdf.filename.values
            indir = outputs_final+os.sep+'GEOTIFF'
            for filename in filelist:

                if not 'nonbackcastable' in filename:
                    continue

                cm_arr = gdal.Open(os.path.join(indir,filename)).ReadAsArray()                
                total = np.nansum(cm_arr)
                    
                totpop=uspop2020
                total = np.nansum(cm_arr)
    
                cm_per_cap = total / totpop
                print(filename,cm_per_cap)
                scenario='NA'
                if '_high_' in filename:
                    scenario='high'
                if '_mean_' in filename:
                    scenario='mean'                
                if '_low_' in filename:
                    scenario='low'                
                stats_per_cap2.append([zipfile_name,filename,scenario,total,cm_per_cap])

                
        stats_per_cap_df2 = pd.DataFrame(stats_per_cap2,columns=['group','filename','scenario','cm_total','cm_per_cap'])
        # sys.exit(0)
        stats_per_cap_df2.to_csv(os.path.join(outputs_final,'stats_per_capita_not_backcasted.csv'),index=False)
        for scenario, sdf in stats_per_cap_df2.groupby('scenario'):
            sdf.to_csv(os.path.join(outputs_final,'stats_per_capita_not_backcasted_%s.csv' %scenario),index=False)
            
if vis_mass_per_capita_stats_mutemp_rucc:
    stats_per_cap_df = pd.read_csv(os.path.join(outputs_final,'stats_per_capita_rucc_mutemp.csv'))
    stats_per_cap_unitemp_df = pd.read_csv(os.path.join(outputs_final,'stats_per_capita_not_backcasted.csv'))
    
    
    stats_per_cap_df['model']=[x[:-8] for x in stats_per_cap_df.filename]
    stats_per_cap_df['bldg_mass_scenario']='mean'
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('high'),'bldg_mass_scenario']='high'
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('low'),'bldg_mass_scenario']='low'
    stats_per_cap_df['backcast_model']=''
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('mod1'),'backcast_model']='mod1'
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('mod2_'),'backcast_model']='mod2'  
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('mod2a'),'backcast_model']='mod2a'  
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('mod2b'),'backcast_model']='mod2b'
    stats_per_cap_df.loc[stats_per_cap_df.model.str.contains('mod3'),'backcast_model']='mod3'  
    
    #### exclude models that we will not publish:
        
    stats_per_cap_df = stats_per_cap_df[stats_per_cap_df.backcast_model.isin(['mod1','mod2','mod3'])]

    years=stats_per_cap_df.year.unique()
    exclude_years=[x for x in years if x%5!=0]
    stats_per_cap_df=stats_per_cap_df[-stats_per_cap_df.year.isin(exclude_years)]
    
    yearpops=[]
    for year in stats_per_cap_df.year.unique():        
        ghstif=os.path.join(os.path.join(outputs_final,'GEOTIFF'), 'combust_plus_resident_population_%s.tif' %year)
        poparr=gdal.Open(ghstif).ReadAsArray()
        poparr[poparr<0]=0
        yearpops.append([year,np.nansum(poparr)])
    yearpopdict=dict(zip(stats_per_cap_df.year.unique(),yearpops))
                    
    ## for each backcasting model, find the non-backcastable combustible mass:
    totals_corrected=[]
    tot_percap_corrected=[]
    for i,row in stats_per_cap_df.iterrows():
        mod=row.backcast_model
        scen=row.bldg_mass_scenario
        add_total=0
        for j, row2 in stats_per_cap_unitemp_df.iterrows():
            print(row2.filename)
            if 'nonbackcastable' in row2.filename and mod in row2.filename and scen in row2.filename:
                add_total = row2.cm_total
                break            
        totals_corrected.append(row.cm_total+add_total)
        tot_percap_corrected.append((row.cm_total+add_total)/yearpopdict[row.year][1]) # not meaningful
        
    stats_per_cap_df['cm_total_corrected']=totals_corrected
    stats_per_cap_df['cm_per_cap_corrected']=tot_percap_corrected # not meaningful without calculating the historical pop shares affected
   

    plotdir = outputs_final+os.sep+'PLOTS'
    
    units=['tons','t/capita']
    targetvars=['cm_total','cm_per_cap']
    for targetvar in targetvars:
        fig,axs=plt.subplots(3,3,figsize=(12,12),sharex=True,sharey=True) 
        idxs=[[0,0],[0,1],[0,2],[1,0],[1,1],[1,2],[2,0],[2,1],[2,2]]
        rucccount=0
        for rucc,ruccdf in stats_per_cap_df.groupby('rucc'):
            if rucc=='all':
                continue
            rucccount+=1
            idx=idxs[rucccount-1]
            ax=axs[idx[0],idx[1]]
            sns.boxplot(x=ruccdf.year.values,y=ruccdf[targetvar].values,hue=ruccdf['backcast_model'].values,ax=ax,linewidth=0,showmeans=True,showfliers=False)
            meanvals=ruccdf.groupby('year')[targetvar].mean()
            ax.plot(meanvals.values,lw=3,color='black')
            if int(rucc)<4:
                ax.set_title('Metro, RUCC=%s' %rucc)
                if int(rucc)==1:
                    ax.set_title('Metro, RUCC=%s (most urban)' %rucc)
            else:
                ax.set_title('Non-metro, RUCC=%s' %rucc)
                if int(rucc)==9:
                    ax.set_title('Non-metro, RUCC=%s (most rural)' %rucc)  
            ax.set_ylabel(targetvar)
            ax.yaxis.set_tick_params(labelleft=True)
            if targetvar=='cm_total':
                ax.set_yscale('log')
            ax.set_xticklabels(ruccdf.year.unique(),rotation=45)
        plt.suptitle(targetvar+' [%s]' %units[targetvars.index(targetvar)])
        plt.legend()
        plt.show()
        fig.savefig(os.path.join(plotdir,'stats_combust_backcast_rucc_bymodel_%s.png' %targetvar),dpi=300)
        
    palette = {
        'low': 'blue',
        'mean': 'turquoise',
        'high': 'orange',
    }        
    for targetvar in targetvars:
        fig,axs=plt.subplots(3,3,figsize=(12,12),sharex=True,sharey=True) 
        idxs=[[0,0],[0,1],[0,2],[1,0],[1,1],[1,2],[2,0],[2,1],[2,2]]
        rucccount=0
        for rucc,ruccdf in stats_per_cap_df.groupby('rucc'):
            if rucc=='all':
                continue
            rucccount+=1
            idx=idxs[rucccount-1]
            ax=axs[idx[0],idx[1]]
            sns.boxplot(x=ruccdf.year.values,y=ruccdf[targetvar].values,hue=ruccdf['bldg_mass_scenario'].values,hue_order=['high','mean','low'],palette=palette,ax=ax,linewidth=0,showmeans=True,showfliers=False)
            meanvals=ruccdf.groupby('year')[targetvar].mean()
            ax.plot(meanvals.values,lw=3,color='black')
            if int(rucc)<4:
                ax.set_title('Metro, RUCC=%s' %rucc)
                if int(rucc)==1:
                    ax.set_title('Metro, RUCC=%s (most urban)' %rucc)
            else:
                ax.set_title('Non-metro, RUCC=%s' %rucc)
                if int(rucc)==9:
                    ax.set_title('Non-metro, RUCC=%s (most rural)' %rucc)               
            ax.set_ylabel(targetvar)
            ax.yaxis.set_tick_params(labelleft=True)
            if targetvar=='cm_total':
                ax.set_yscale('log')
            ax.set_xticklabels(ruccdf.year.unique(),rotation=45)
        plt.suptitle(targetvar+' [%s]' %units[targetvars.index(targetvar)])
        plt.legend()
        plt.xticks(rotation=45)
        plt.show()
        fig.savefig(os.path.join(plotdir,'stats_combust_backcast_rucc_scenario_%s.png' %targetvar),dpi=300)

    plotyears=np.arange(1975,2021,5)
    #average trend line per rucc, but in one graph instead of multipanel:
    for targetvar in targetvars:
        fig,ax=plt.subplots(figsize=(5,5)) 
        for rucc,ruccdf in stats_per_cap_df.groupby('rucc'):
            if rucc=='all':
                continue
            currcolor=matplotlib.cm.RdYlGn(int(rucc)/9)
            meanvals=ruccdf.groupby('year')[targetvar].mean()
            label=rucc
            if int(rucc)==1:
                label='1 (most urban)'
            if int(rucc)==9:
                label='9 (most rural)'                
            ax.plot(plotyears,meanvals.values,lw=4,color=currcolor,label=label)      
            ax.set_ylabel(targetvar)
            ax.yaxis.set_tick_params(labelleft=True)
            if targetvar=='cm_total':
                ax.set_yscale('log')
        # ax.set_xticklabels(plotyears,rotation=45)
        plt.title(targetvar+' [%s]' %units[targetvars.index(targetvar)])
        plt.legend(bbox_to_anchor=(1,1))
        plt.xticks(rotation=45)
        plt.show()
        fig.savefig(os.path.join(plotdir,'stats_combust_backcast_rucc_average_combined_%s.png' %targetvar),dpi=300,bbox_inches='tight')

    #average trend line per rucc, but in one graph instead of multipanel, for each model and scenario:
    for targetvar in targetvars:
        for model,mdf in stats_per_cap_df.groupby('model'):
            for scen,sdf in mdf.groupby('bldg_mass_scenario'):
                fig,ax=plt.subplots(figsize=(5,5)) 
                for rucc,ruccdf in sdf.groupby('rucc'):
                    if rucc=='all':
                        continue
                    currcolor=matplotlib.cm.RdYlGn(int(rucc)/9)
                    meanvals=ruccdf.groupby('year')[targetvar].mean()
                    label=rucc
                    if int(rucc)==1:
                        label='1 (most urban)'
                    if int(rucc)==9:
                        label='9 (most rural)'                
                    ax.plot(plotyears,meanvals.values,lw=3,color=currcolor,label=label)      
                    ax.set_ylabel(targetvar)
                    # ax.set_ylim([10,50])
                    ax.yaxis.set_tick_params(labelleft=True)
                    if targetvar=='cm_total':
                        ax.set_yscale('log')
                # ax.set_xticklabels(plotyears,rotation=45)
                plt.title(targetvar+' [%s], %s, %s' %(units[targetvars.index(targetvar)],model,scen))
                plt.legend()
                plt.xticks(rotation=45)
                plt.show()
                fig.savefig(os.path.join(plotdir,'stats_combust_backcast_rucc_average_combined_%s_%s_%s.png' %(targetvar,model,scen)),dpi=300)

    #### same plots across all RUCCs:
    allruccdf=stats_per_cap_df[stats_per_cap_df.rucc=='all']

    units=['Gt','t/capita','t/capita']
    targetvars=['cm_total_corrected','cm_per_cap_corrected','cm_per_cap']
    factors=[1/1000000000,1,1]
    for targetvar in targetvars:
        factor=factors[targetvars.index(targetvar)]
        fig,ax=plt.subplots(figsize=(5,5)) 
        sns.boxplot(x=allruccdf.year.values,y=allruccdf[targetvar].values*factor,hue=allruccdf['backcast_model'].values,ax=ax,linewidth=0,showmeans=True,showfliers=False)
        meanvals=allruccdf.groupby('year')[targetvar].mean()*factor
        ax.plot(meanvals.values,lw=3,color='black')
        ax.set_ylabel(targetvar)
        ax.yaxis.set_tick_params(labelleft=True)
        ax.set_xticklabels(allruccdf.year.unique(),rotation=45)
        plt.title(targetvar+' [%s]' %units[targetvars.index(targetvar)])
        plt.legend()
        plt.show()
        fig.savefig(os.path.join(plotdir,'stats_combust_backcast_bymodel_%s.png' %targetvar),dpi=300)

    for targetvar in targetvars:
        factor=factors[targetvars.index(targetvar)]
        fig,ax=plt.subplots(figsize=(5,5)) 
        for group,groupdf in allruccdf.groupby(['backcast_model','bldg_mass_scenario']):
            ax.plot(groupdf.year.values,groupdf[targetvar].values*factor,label=group)
        ax.set_ylabel(targetvar)
        ax.yaxis.set_tick_params(labelleft=True)
        ax.set_xticklabels(allruccdf.year.unique(),rotation=45)
        plt.title(targetvar+' [%s]' %units[targetvars.index(targetvar)])
        plt.legend()
        plt.show()
        fig.savefig(os.path.join(plotdir,'stats_combust_backcast_lineplots_%s.png' %targetvar),dpi=300)
        
        
    palette = {
        'low': 'blue',
        'mean': 'turquoise',
        'high': 'orange',
    }        
    
    for targetvar in targetvars:
        factor=factors[targetvars.index(targetvar)]
        fig,ax=plt.subplots(figsize=(5,5)) 
        sns.boxplot(x=allruccdf.year.values,y=allruccdf[targetvar].values*factor,hue=allruccdf['bldg_mass_scenario'].values,hue_order=['high','mean','low'],palette=palette,ax=ax,linewidth=0,showmeans=True,showfliers=False)
        meanvals=allruccdf.groupby('year')[targetvar].mean()*factor
        ax.plot(meanvals.values,lw=3,color='black')
        ax.set_ylabel(targetvar)
        ax.yaxis.set_tick_params(labelleft=True)
        ax.set_xticklabels(allruccdf.year.unique(),rotation=45)
        plt.title(targetvar+' [%s]' %units[targetvars.index(targetvar)])
        plt.legend()
        plt.show()
        fig.savefig(os.path.join(plotdir,'stats_combust_backcast_scenario_%s.png' %targetvar),dpi=300)
        

    ### CM in metro vs non-metro counties:
    cm_metro_stats=[]  
    stats_per_cap_df_rucc=stats_per_cap_df[stats_per_cap_df.rucc!='all']
    metrodf = stats_per_cap_df_rucc[stats_per_cap_df_rucc.rucc.map(int)<4]
    metrodf = metrodf[metrodf.backcast_model=='mod3']  
    metrodf = metrodf[metrodf.year==1975]
    for scen,scendf in metrodf.groupby('bldg_mass_scenario'):
        print (1975,scen,scendf.cm_total.sum()/1000000000)
        currsum=scendf.cm_total_corrected.sum()/1000000000
        popsum=scendf.pop_sum.sum()
        cm_metro_stats.append(['metro',1975,scen,currsum,popsum])
    
    stats_per_cap_df_rucc=stats_per_cap_df[stats_per_cap_df.rucc!='all']
    metrodf = stats_per_cap_df_rucc[stats_per_cap_df_rucc.rucc.map(int)<4]
    metrodf = metrodf[metrodf.backcast_model=='mod3']    
    metrodf = metrodf[metrodf.year==2020]
    for scen,scendf in metrodf.groupby('bldg_mass_scenario'):
        print (2020,scen,scendf.cm_total.sum()/1000000000)    
        currsum=scendf.cm_total_corrected.sum()/1000000000    
        popsum=scendf.pop_sum.sum()
        cm_metro_stats.append(['metro',2020,scen,currsum,popsum])

    stats_per_cap_df_rucc=stats_per_cap_df[stats_per_cap_df.rucc!='all']        
    metrodf = stats_per_cap_df_rucc[stats_per_cap_df_rucc.rucc.map(int)>3]
    metrodf = metrodf[metrodf.backcast_model=='mod3']  
    metrodf = metrodf[metrodf.year==1975]
    for scen,scendf in metrodf.groupby('bldg_mass_scenario'):
        print (1975,scen,scendf.cm_total.sum()/1000000000)
        currsum=scendf.cm_total_corrected.sum()/1000000000
        popsum=scendf.pop_sum.sum()
        cm_metro_stats.append(['nonmetro',1975,scen,currsum,popsum])
    
    stats_per_cap_df_rucc=stats_per_cap_df[stats_per_cap_df.rucc!='all']
    metrodf = stats_per_cap_df_rucc[stats_per_cap_df_rucc.rucc.map(int)>3]
    metrodf = metrodf[metrodf.backcast_model=='mod3']    
    metrodf = metrodf[metrodf.year==2020]
    for scen,scendf in metrodf.groupby('bldg_mass_scenario'):
        print (2020,scen,scendf.cm_total.sum()/1000000000)  
        currsum=scendf.cm_total_corrected.sum()/1000000000   
        popsum=scendf.pop_sum.sum()
        cm_metro_stats.append(['nonmetro',2020,scen,currsum,popsum])
        
    cm_metro_statsdf=pd.DataFrame(cm_metro_stats,columns=['stratum','year','scenario','cm_Gt','popsum'])
    cm_metro_statsdf.to_csv(os.path.join(outputs_final,'cm_metro_nonmetro.csv'),index=False)                   
