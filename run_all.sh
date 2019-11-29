#!/usr/bin/env bash
if [ "$#" -ne 2 ]; then
    echo "Illegal number of parameters: need 2"
    exit 2
fi

configfile=$1
logdir=$2

echo "[*] Starting all spiders in background"
echo "  > Configuration file: $1"
echo "  > Log file directory: $2"

xargs -n1 -P 0 -a spider_list.txt python run_spider.py --config $1 --logdir $2 --spider
