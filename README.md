# CDSE Copernicus DEM downloader

## Introduction

The aim of this project is to develop a light CDSE (Copernicus DataSpace Ecosystem) Copernicus DEM downloader tool to allow the Sen2Cor Users to search, access and download the Copernicus DEM at 30 m or 90 m, necessary for Sen2Cor standard processing.

Main functionalities:
- User Authentication, Token generation for CDSE Copernicus DEM data access and download;
- Searching the Copernicus DEM tiles covering Sentinel-2 MGRS tiles;
- Downloading the Copernicus DEM necessary files related to a given MGRS Sentinel-2 Tile;
(Tile_ID or SAFE format string name as command line or as a list within the txt file);
- Extracting and storing the retrieved files within the Sen2Cor DEM directory (to be given as input).


## Credentials

### Prerequisites

- A valid CDSE user account is required from https://dataspace.copernicus.eu/
- Login credentials are:
  - username (email address)
  - password

### Privacy Handling

- User will be prompted to insert username and password (once)
- Password is encrypted using RSA encryption and stored in credentials.yaml file
- The credentials.yaml file can then be reused for other runs of the tool by the same user
- Credentials can be deleted with the dedicated command line option (--reset)

### CDSE Token generation

- Credentials are used to generate CDSE token required for CDSE data download
- CDSE token has a validity time of 10 minutes
- CDSE token can be refreshed 5 times for a maximum overall token validity time of 60 minutes
- After a maximum of 60 minutes of operations, the CDSE Copernicus DEM downloader tool will stop when the token validity is expired.

## Installation and Configuration

### Prerequisites

- Python >=3.12 is supported.

- Clone repository into your local file system:
    
    ```bash
    git clone https://github.com/telespazio-tim/cdse-copernicus-dem-downloader.git
    ```

- External Copernicus Sentinel-2 tiling system KML file is required.
  -  Download the Copernicus Sentinel-2 tiling system KML file from the following link:
[Copernicus Sentinel-2 KML](https://sentinel.esa.int/documents/247904/1955685/S2A_OPER_GIP_TILPAR_MPC__20151209T095117_V20150622T000000_21000101T000000_B00.kml);
  - Place the KML file in the following directory `./cdse-copernicus-dem-downloader/auxiliary`;

- For the installation of prerequisite dependencies you need to create a dedicated conda environment.
  - To do so, install [conda](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html) or [miniconda](https://docs.conda.io/en/latest/miniconda.html), then run the following command to create the _cdse-copernicus-dem-downloader_ conda env

  ```bash
  conda env create -f environment.yml
  ```

- The cdse-copernicus-dem-downloader env is activated with: 

    ```bash
    conda activate cdse-copernicus-dem-downloader
    ```
## Usage examples

Type:

```console
python cdse_copernicus_dem_downloader.py --help
```

The help menu is visualised:

```console
DEM Downloader Version: 1.0 Release Date: 10-October-2024.
options:
  -h, --help         show this help message and exit
  --config [CONFIG]  set the path to the Config file. If blank, read the parameters from the configuration/configuration.xml
  --r {30,90}        set the (r)esolution of the DEM: 30 or 90 (m)
  --m {DTED,DGED}    set the (m)odel of the DEM: DTED or DGED
  --o O              set the (o)utput directory for storing the DEM. If blank, store into the Tool's Output_Dir
  --i I              set the path for the (i)nput file containing the tiles list. If blank, read from the Tool's configuration/input_tiles.txt
  --t T              specify a single required MGRS (t)ile. e.g. 32UMA or Product (SAFE)
  --reset [RESET]    reset credentials
```

The help menu returns the available options. The software can be operated via command line, or by filling the `configuration.xml`
 with the desired parameters. An example of a query using a command line is the following:

```console
python cdse_copernicus_dem_downloader.py --m DGED --r 90 --t 32UMA --o /Users/Sen2Cor/dem/CopernicusDEM90_DGED 
```

This will retrieve  `(--m)` DGED-type DEM files at `(--r)` 90 m resolution that intersect the `(--t)` MGRS tile 32UMA and store them in the `(--o)` indicated output directory.

A more complete CDSE DEM Downloader Quick User Guide is available at the following link: [Link Here]()

Credentials. User is prompted to insert username and password (one time):

```console
[log-info] Retrieval of public and private keys
Enter your username: xxxx
Enter your password:
Re-enter your password:
[log-info] Password has been stored in credentials.yaml for username xxxx
```

## Important Note for Sen2Cor Users

Sen2Cor Toolbox v2.12.03 (and previous versions) supports CDSE-DGED DEM types. CDSE-DTED DEM types are not supported. 

## Useful Links

- Information on the Copernicus Digital Elevation Model:
[Copernicus Digital Elevation Model Website](https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model);

- Information on the Copernicus DataSpace Ecosystem (CDSE):
[CDSE Website](https://documentation.dataspace.copernicus.eu/Home.html);

- Information on the APIs services provided by CDSE:
[CDSE APIs Reference Page](https://documentation.dataspace.copernicus.eu/APIs.html);

- To report bugs, or for further questions, please visit the ESA STEP Forum page dedicated to Sen2Cor:
[Sen2Cor SNAP Forum](https://forum.step.esa.int/c/optical-toolbox/sen2cor/).
