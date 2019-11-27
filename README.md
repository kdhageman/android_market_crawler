# PyStoreCrawler
A crawler that retrieves Android application meta-data and APK files from a selection of markets.
Based on the Scrapy framework.

#### How to run
Requirements:
- Python 3+ (tested with 3.7.3)

Prepare the configuration file, by copying/changing `config/config.template.yml` to your needs, and then running the following commands from the root of the project directory: 
```bash
$ pip install -r requirements.txt
$ python3 main.py --config {path to config file} 
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
