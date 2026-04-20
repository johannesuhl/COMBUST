# COMBUST: Gridded combustible mass estimates of the built environment in the conterminous United States 1975-2020 - supplementary code

These scripts document the production of the COMBUST dataset. They consist of the following components:

- **01_ztrax_impute_building_indoor_area.py**: Prepares ZTRAX data and imputed missing data

- **02_ztrax_compute_building_content_cm.py**: Calculates building content combustible mass based on the method proposed [here](https://doi.org/10.1016/j.enbuild.2020.110609).

- **03_rasterize_building_content_cm.py**: Gridifies building content estimates into a 250-m grid.

- **04_downsample_msmc_data.py**: Resamples the 10-m building mass/volume estimates from [Frantz et al. (2023)](https://doi.org/10.1038/s41467-023-43755-5) to the 250-m grid.

- **05_get_osm_gas_stations.py**: Downloads locations of gas stations from OpenStreetMap.

- **06_combust_model_main.py**: Merges these and other input data sources, produces all COMBUST layers and analyzes them.

Dataset available at https://doi.org/10.5281/zenodo.15611963

Data descriptor preprint available at: https://doi.org/10.48550/arXiv.2511.08893

Data citation:

Uhl, J. H., Cook, M., Amaral, C., Leyk, S., Balch, J. K., Robock, A., & Toon, O. B. (2025). COMBUST: Gridded combustible mass estimates of the built environment in the conterminous United States (1975-2020) [Data set]. https://doi.org/10.5281/zenodo.15611963

Data descriptor citation:

Uhl, J. H., Cook, M. C., Amaral, C., Leyk, S., Balch, J. K., Robock, A., & Toon, O. B. (2025). COMBUST: Gridded combustible mass estimates of the built environment in the conterminous United States (1975-2020). arXiv preprint arXiv:2511.08893. https://doi.org/10.48550/arXiv.2511.08893

Note: the production of COMBUST-PLUS is not covered in this repository.


