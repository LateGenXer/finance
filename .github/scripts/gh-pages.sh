#!/bin/sh

set -eux

mkdir -p _site
python download.py 'https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D1A' _site/dmo-D1A.xml text/xml
python download.py 'https://www.ons.gov.uk/generator?format=csv&uri=/economy/inflationandpriceindices/timeseries/chaw/mm23' _site/rpi-series.csv
python -m data.lse > _site/gilts-closing-prices.csv
python -m data.boe && mv data/boe-yield-curves.csv _site/boe-yield-curves.csv
