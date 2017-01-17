#! /usr/bin/python3
from functools import reduce
from operator import or_
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

def sectionToJSON(section):
    return {
            "prof" : section.prof,
            "sem"  : section.sem,
            "day"  : section.day
            }

def classToJSON(clss):
    return {
            "title"    : clss.title,
            "sections" : map(sectionToJSON, clss.sections),
            "dept"     : clss.dept,
            "code"     : clss.code,
            "books"    : list(clss.books) if clss.books else []
            }


def truncate(docid):
    """
    Truncate a document id to 12 digits
    The document ID should be based on a
    hash of unique identifiers
    """
    return int(str(docid)[0:12])

def hashsec(course):
    """
    Hash a course into a usable id
    """
    if not course["code"]:
        code = ""
    else:
        code = course["code"]
    if not course["title"]:
        title = ""
    else:
        title = course["title"]

    if not course["sections"] or len(course["sections"]) < 1:
        course["sections"][0] = ""

    if not (code or title):
        raise UnIndexable(course)

    h = sha1()
    h.update(code + title + course["sections"][0]["sem"])
    return int(h.hexdigest(), 16)

def createIndex(name):
    """
    This creates a new index in elasticsearch
    An index is like a schema in a regular database
    """
    indices = elasticsearch.client.IndicesClient(es)

    print(indices.create(name))
    with open("../course.json", "r") as mapping:
        print(indices.put_mapping("course", loads(mapping.read()), name))

def indexListing(course):
    """
    Index a specific course in the database (using the courses index)
    example,
    {
     'books': [],
     'dept': 'COLLAB',
     'code': '2C03',
     'sections': [
                    {
                     'prof': 'Lisa Pender',
                     'sem': '2015/09/08 - 2015/12/08',
                     'day': 'Mo'
                     },
                     {
                      'prof': 'Staff',
                      'sem': '2015/09/08 - 2015/12/08',
                      'day': 'Th'
                      }
                  ],
     'title': 'COLLAB 2C03 - Sociology I'
     }

    """
    json_course = classToJSON(course)
    courseID = hashsec(json_course)
    print(es.index(index="oersearch",
            doc_type="course",
            id=courseID,
            body=json_course))

def termSearch(field):
    """
    Make a term search (exact match)
    """
    def t(term):
        q = Q("term",
                **{
                    "sections."+field : term
                    })
        return q
    return t

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

def join(x, y):
    """
    Join two queries
    """
    return x & y

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
    q = reduce(join, qs)

    s = (Search(using=es, index="oersearch")
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
        # Add the truncated course id
        # This is used to point to the resource page for that course
        secs["id"] = truncate(obj.meta.id)
        secs["title"] = obj.title
        if obj["dept"] not in secs["title"]:
            secs["dept"] = obj.dept
        if obj.books:
            secs["books"] = [
                             {
                               "booktitle"  : book[0],
                               "bookauthor" : book[1],
                               "bookprice"  : book[2]
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
