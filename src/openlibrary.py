#! /usr/bin/python3

from urllib.parse import quote
from json import loads, dumps

import requests as req

#query = "https://openlibrary.org/query.json?type=/type/edition&title=%s&author=%s"
searchurl = 'http://openlibrary.org/search.json?author=%s&title=%s'

def bookUrls(title, author):
    print(title, author)
    if ":" in title:
        title = title.split(":")[0]
    requrl = searchurl % (quote(author), quote(title))
    results = loads(req.get(requrl).text)
    for result in results["docs"][0:2]:
        if "edition_key" in result:
            yield "https://openlibrary.org/books/%s" % result["edition_key"][0]

# 'http://openlibrary.org/query.json?type=/type/edition&title=The+Personality+Puzzle'

#for book in bookUrls("Philosophy Of Physics", "Tim Maudlin"):
    #print book
