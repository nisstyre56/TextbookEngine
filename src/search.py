#! /usr/bin/python3
from functools import reduce
from operator import or_, and_
from hashlib import sha1
from sys import exit, stderr
from json import loads
from itertools import chain
from syslog import syslog

import elasticsearch
from elasticsearch_dsl import FacetedSearch, Search, Q
from elasticsearch_dsl.aggs import Terms, DateHistogram

from textbookExceptions import UnIndexable

# Generic instance of elasticsearch right now
es = elasticsearch.Elasticsearch()

def summarize(text):
    splitted = text.split(" ")
    if len(splitted) > 6:
        return " ".join(splitted[0:6]) + ".."
    return text

def search(field):
    """
    Make a match search
    """
    def s(term):
        q = Q("match",
                 **{
                     field : term
                    })
        return q
    return s

def filterSem(term):
    return Q("terms",
            **{
                "sections.sem" : [term]
                })

def filterSections(secs):
    """
    Get rid of tutorial sections
    because they almost always have "Staff" as the instructor
    This is just a heuristic of course
    """
    filtered = [s for s in secs.sections if "Staff" not in s.prof]
    if len(filtered) > 0:
        return filtered
    return False

def search_courses(terms):
    """
    Run a search for courses
    """
    syslog(repr(terms))

    # A list of all the queries we want to run
    qs = [searchers[field](term) for
            field, term in
            terms.items() if
                term and field in searchers]

    if not qs:
        # No queries = no results
        return []

    # Reduce joins all of the queries into one query
    # It will search for the conjunction of all of them
    # So that means it cares about each query equally
    q = reduce(and_, qs)

    s = (Search(using=es, index="course_test")
        .query(q))[0:100] # only return up to 100 results for now

    results = s.execute()
    syslog(repr(results))

    filtered = [
                 (secs, filterSections(secs)[0].to_dict()) # get rid of tutorials
                  for secs in results
                    if filterSections(secs)
               ]
    results = []
    for obj, secs in filtered:
        secs["title"] = obj.title
        if obj["dept"] not in secs["title"]:
            secs["dept"] = obj.dept
        if "books" in obj:
            secs["books"] = [
                             {
                               "booktitle"  : book["title"],
                               "bookauthor" : book["author"],
                               "bookprice"  : book["price"]
                             }
                                for book in obj.books
                            ]
        else:
            secs["books"] = ""
        results.append(secs)

    return results

searchers = {
    "title" : search("title"),
    "loc"   : search("loc"),
    "time"  : search("time"),
    "prof"  : search("prof"),
    "day"   : search("day"),
    "sem"   : filterSem
    }
