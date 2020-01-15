#!/usr/bin/env bash
if [ "$#" -ne 2 ]; then
    echo "Illegal number of parameters: need 2 (configdir, logdir)"
    exit 2
fi

configdir=$1
logdir=$2

echo "[*] Starting all spiders in background"
echo "  > Configuration directory:            $1"
echo "  > Main configuration file:            $1/config.yml"
echo "  > Log file directory:                 $2"

xargs -I {} -n1 -P 0 -a config/spider_list.txt python scripts/run_spider.py --config $1/config.yml $1/{}.yml --logdir $2 --spider {}
