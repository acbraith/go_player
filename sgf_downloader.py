
import requests

base_url = 'http://www.yss-aya.com/cgos/9x9/archives/'
datasets = []
for year in range(2015, 2020):
    for month in range(1,13):
        datasets.append('9x9_%d_%02d.tar.bz2' % (year, month))

# Downloading
from tqdm import tqdm
for d in tqdm(datasets, ncols=80):
    print(d)
    url = base_url + d
    r = requests.get(base_url + d)
    if r.status_code == 200:
        open('data/aya/%s' % d, 'wb').write(r.content)
