import xml.etree.ElementTree as ET
import urllib
import urllib.request as req
import csv
import time
import math
import datetime
from bs4 import BeautifulSoup
		
def getpubs(authors,current,qualifiers,readxml=False, hasauthorids=False):
    """
	    Core function of the library 
	    Pass author names to search as list, current publications as PMID in list to exclude,
	    address qualifiers as text with % encoding, readxml as True to get all data rather than just PMID,
        hasauthorids = True to pass authors in format [ (ID, 'Name'), ... ] default is just ['Name',...]
    """
    
    baseurl = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
    searchurl = 'esearch.fcgi?db=pubmed&term='   
    posturl = 'epost.fcgi?db=pubmed'
    fetchurl = 'efetch.fcgi?db=pubmed&'
    pmidlist = get_ids(authors,current,qualifiers,baseurl+searchurl, hasauthorids)
    
    if readxml: 
        datatable = read_xml(pmidlist,baseurl+posturl,baseurl+fetchurl)
    return (datatable if readxml else pmidlist)

def accessapi(url,postdata=None):
    """
    Access the PubMed API and retrieve xml tree.
    """
    t0 = time.time()
    retries = 0
    while retries < 10:
        try:
            wp = req.urlopen(url,postdata)
            wpdata = wp.read()
            tree = ET.fromstring(wpdata)
            wp.close()

            if (time.time() - t0) < 0.4:
                time.sleep(0.3)
            if (tree[0].tag == 'ERROR'):
                retries += 1
            else:
                return tree
        except:
            retries += 1
    print('Error: Maximum retries exceeded')

def get_ids(authors,currentpubs,qualifiers,url, hasauthorids):
    """
    Loop through the list of authors and search Pubmed.
    Discard PMIDs if found previously
    Link multiple authors on same publication
    Return list of new PMIDs and associated authors in form [ID, Author ID] or [ID, Author Name] depending on hasauthorids
    """
    pmidlist = []
    while len(authors):
        if qualifiers:
            if hasauthorids:
                querystring = "[ad]+OR+".join(qualifiers)  + "[ad]+AND+" + "".join(authors[0][1]) + "[au]&retmax=10000"
            else:
                querystring = "[ad]+OR+".join(qualifiers)  + "[ad]+AND+" + "".join(authors[0]) + "[au]&retmax=10000"
        else:
            if hasauthorids:
                querystring = "".join(authors[0][0]) + "[au]&retmax=10000"
            else:
                querystring = "".join(authors[0]) + "[au]&retmax=10000"  
        ausearch = accessapi(url + querystring)
        idlist = get_elem(ausearch,'IdList')
        for uid in idlist:
            if uid.text not in currentpubs: 
                if uid.text not in [pmidlist[x][0] for x,v in enumerate(pmidlist)]:
                    if hasauthorids:
                        pmidlist.append([uid.text,[(authors[0][0],authors[0][1])]])
                    else:
                        pmidlist.append([uid.text,[authors[0]]])
                else:
                    for i in pmidlist:               
                        if i[0] == uid.text:
                            if hasauthorids:
                                pmidlist[pmidlist.index(i)][1].append((authors[0][0],authors[0][1]))
                            else:
                                pmidlist[pmidlist.index(i)][1].append(authors[0])
        
        print(str(datetime.datetime.now()), '| Found ', len(pmidlist), ', remaining: ', len(authors))
        authors.pop(0)
    return pmidlist

def get_elem(root,lookfor):
    """ 
    Find particular element in XML tree
    """
    try:
        itertree = root.iter()
        elem = itertree.__next__()
        while elem.tag != lookfor: 
            elem = itertree.__next__()
    except StopIteration:
        elem = None
    return elem

def create_trees(idlist,url):
    """
    API prevents posting > 10k IDs
    """
    
    datatrees = []
    treesreq = math.ceil(len(idlist) / 10000)
    for i in range(0,treesreq):
        dt = accessapi(url,create_post_data([l[0] for l in idlist[i*10000:(i*10000)+10000]]))
        datatrees.append(dt)
    print(str(datetime.datetime.now()),"| Created trees")
    return datatrees

def create_post_data(publist):
    """
    Parse the list of PMIDs into dict for HTTP POST request
    """
    mydict = {}
    mydict['id'] = []
    for uid in publist:
        mydict['id'] .append(uid)
    mydict = urllib.parse.urlencode(mydict)
    mydict = mydict.encode('utf-8')
    return mydict

def fetchdata(baseurl, datatree):
    """
    Retrieve the storage location parameters from the posted data
    """
    qkey = datatree.find('QueryKey').text
    webenv = datatree.find('WebEnv').text
    params = 'query_key=' + qkey + '&WebEnv=' + webenv
    dlurl = baseurl + params + '&rettype=xml&retmode=xml&retmax=20000>'  
    print(dlurl)
    print(str(datetime.datetime.now()),"| Fetching data")
    return dlurl

def read_xml(idlist,posturl, fetchurl):
    """
    Look up article metadata from list of PMIDs
    Posts list of IDs to server then fetches metadata
    """
    publications = []
    if idlist:
        datatrees = create_trees(idlist,posturl)
        for dt in datatrees:
            articletree = fetchdata(fetchurl,dt)
            pubs = req.urlopen(articletree).read()
            pubs = list(BeautifulSoup(pubs).find_all('pubmedarticle'))

        return idlist, pubs
    else:
        return None
