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
In order to crawl Google's Play Store, a local API must be running (see [README](api/README.md) for more info) 

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

##### NOTE
Right now, the `idna` library used by `Twisted` is too strict in handling internationalized domain names (IDNs), i.e. is too generous in raising errors.
This is a significant problem for the Play Store, in which the URL of downloading an APK is an invalid IDN, but which is accepted by `cURL` and browsers regardless.
To circumvent this problem temporarily (until a better solution is found), we manually disable the first if-check in the `check_hyphen_ok(label)` function in the library, located in `core.py` in the `idna` library. 

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
