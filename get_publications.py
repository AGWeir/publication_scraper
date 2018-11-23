import xml.etree.ElementTree as ET
import urllib
import urllib.request as req
import csv
import time
import math
import datetime
		
class publication:
    def __init__(self,pmid):
        self.pmid = pmid
        self.abstract = ''
        self.title = ''
        self.journal = ''
        self.year = ''
        self.month = ''
        self.authors = ''
        self.doi = ''
        self.meshheadings = ''
        self.status = ''
		
    def __repr__(self):
        return str(self.pmid)
        
        
class journal:
    def __init__(self, name):
        self.name = name
        self.issue = ''
        self.volume = ''
        
    def __repr__(self):
        return str(self.name)
        
class author:
    def __init__(self, initials,forename, surname, affiliation='None'):
        self.initials = initials
        self.forename = forename
        self.surname = surname
        self.affiliation = affiliation
        self.uid = 0
        if forename:
            self.searchname = surname.replace("'","%27").replace(" ","%20") + "+" + forename[0]
        else:
            self.searchname = surname
        self.brc = False
    
    def __repr__(self):
        return str(self.surname)
    
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

def get_text(root, lookfor):
    """
    Get value of selected element
    """
    elem = get_elem(root, lookfor)
    return (elem.text if elem is not None else 'err')

def get_authors(root, matchedauthors):
    """
    Get the complete author list and affiliations
    """
    articleauthors = []
    authorlist = get_elem(root,'AuthorList')
    if authorlist is not None: 
        authorlist = authorlist.findall('Author')
        for au in authorlist:
            collective = get_elem(au,'CollectiveName')
            if collective is not None:
                articleauthors.append(author('Collective','Collective',collective.text,'Collective'))
            else:
                current_author = author(
                    get_text(au,'Initials'),
                    get_text(au,'ForeName'),
                    get_text(au,'LastName'),
                    get_text(au,'Affiliation')
                )
                for a in matchedauthors:
                    print(a)
                    if current_author.searchname == a[1]:
                        print('brc authors found', a)
                        current_author.brc = True
                        current_author.uid = a[0]

                articleauthors.append(current_author)
        return articleauthors
    else:
        return [author('None','None','None','None')]

def get_doi(root):
    """ 
    Get the article DOI
    Separate method from get_elem because it's held by attribute
    """

    elem = get_elem(root,'ArticleIdList')
    ids = elem.findall('ArticleId')  
    doi = None   
    for idtype in ids:
        try:
            if idtype.attrib['IdType'] == 'doi':
                doi = idtype.text
        except AttributeError:
            pass  
    return doi


def get_mesh(root):
    """
    Get a list of all the MESH headings
    """
    meshheadings = []
    meshlist = get_elem(root, 'MeshHeadingList')
    if meshlist:
        meshlist = meshlist.findall('MeshHeading')
        for m in meshlist:
            meshheadings.append(m.find('DescriptorName').text)
    return meshheadings

def read_xml(idlist,posturl, fetchurl):
    """
    Look up article metadata from list of PMIDs
    Posts list of IDs to server then fetches metadata
    """
    publications = []
    if idlist:
        datatrees = create_trees(idlist,posturl)
        for dt in datatrees:
            articletree = accessapi(fetchdata(fetchurl,dt))
            print(str(datetime.datetime.now()),"| Got data")
            for article in articletree:
                if article.tag == 'PubmedArticle':
                    pub = publication(get_text(article,'PMID'))
                    pub.title = get_text(article,'ArticleTitle')
                    pub.abstract = get_text(article, 'AbstractText')
                    pub.journal = journal(get_text(article,'ISOAbbreviation'))
                    pub.journal.volume = get_text(article,'Volume')
                    pub.journal.issue = get_text(article, 'Issue') 
                    pub.year = get_text(get_elem(article,'PubDate'),'Year')
                    pub.month = get_text(get_elem(article,'PubDate'),'Month')

                    
                    # just pass the list of matched search names for this pub only rather than all
                    
                    for x in idlist:
                        if x[0] == pub.pmid:
                            pub.authors = get_authors(article, x[1])                             

                    pub.doi = get_doi(article) 
                    pub.meshheadings = get_mesh(article)
                    pub.status = get_text(article,'PublicationStatus')
                    publications.append(pub)   
                else:
                    ## Not an article
                    pass         
        return publications
    else:
        return None
        

