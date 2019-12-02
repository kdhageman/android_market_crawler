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
$ python3 main.py --config {path to config file} --spider {name of spider, see spider_list.txt for available spiders} --logdir {directory where to store logs}  
```
Alternatively, you can run all spiders as separate processes by running `./run_all.sh`.

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
