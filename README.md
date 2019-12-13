# PyStoreCrawler
A crawler that retrieves Android application meta-data and APK files from a selection of markets.
Based on the Scrapy framework.

#### Quickstart
Requirements:
- Python 3.6+ (tested with 3.7.3)

##### Configuration
Prepare the configuration file, by copying/changing `config/config.template.yml` to your needs.
The `package_files` are text file of package name where each line contains a single package name:
```bash
com.example.chat
com.example.text
com.example.camera
```
Note that not all spiders are able to respect this list of package, as their markets are not crawl-able based on package names.
Those crawlers simply ignore the lists and have their own package discovery mechanisms builtin.       

##### Running
Run the following commands from the root of the project directory:
```bash
$ pip3 install -r requirements.txt
$ python scripts/run_spider.py --help
usage: run_spider.py [-h] [--config CONFIG] --spider SPIDER [--logdir LOGDIR]
                     [--user_agents_file USER_AGENTS_FILE]
                     [--proxies_file PROXIES_FILE]

Android APK market crawler

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG       Path to YAML configuration file
  --spider SPIDER       Spider to run
  --logdir LOGDIR       Directory in which to store the log files
  --user_agents_file USER_AGENTS_FILE
                        Path to file of user agents
  --proxies_file PROXIES_FILE
                        Path to file of proxy addresses
  
```
Alternatively, you can run all spiders as separate processes by running `./run_all.sh`.

After having downloaded a set of APKs and their associated meta data, the following scripts can be run:
```bash
$ python scripts/combine_json.py --help
usage: combine_json.py [-h] [--dir DIR] [--outfile OUTFILE]
                       [--spidertxt SPIDERTXT]

Aggregates JSON outputs from "run_spider.py" scripts

optional arguments:
  -h, --help            show this help message and exit
  --dir DIR             Directory to traverse
  --outfile OUTFILE     Name of output file
  --spidertxt SPIDERTXT
                        File which contains names of spiders
```
and 
```bash
$ python scripts/analyze_apks.py --help
usage: analyze_apks.py [-h] [--dir DIR] [--spidertxt SPIDERTXT]
                       [--outfile OUTFILE]

Analyze all APKs

optional arguments:
  -h, --help            show this help message and exit
  --dir DIR             Directory to traverse
  --spidertxt SPIDERTXT
                        File which contains names of spiders
  --outfile OUTFILE     Name of output file
```
The following depends on the apk analysis script
```bash
$ python scripts/download_assetlinks.py  --help
usage: download_assetlinks.py [-h] [--infile INFILE] [--outfile OUTFILE]

Downloads the asset-links.json for the output file of "analyze_apks.py"

optional arguments:
  -h, --help         show this help message and exit
  --infile INFILE    path of input file
  --outfile OUTFILE  path of output file
```

#### Supported markets
A diverse set of markets is being crawled, both from the west and China. 

##### Western
- SlideME 
- F-Droid
- APKMirror
- APKMonk
- Google Play (only package detection, not meta-data and APK crawling)

##### Chinese
- Tencent
- Xiaomi Mi
- 360
- Baidu
- Huawei  

##### Markets on the TODO list
- OPPO
- Samsung Galaxy Apps
