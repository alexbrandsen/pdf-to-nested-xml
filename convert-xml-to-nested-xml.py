# import element tree; to parse xml
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

# import os; to loop through pdf/xml files
import os

#import re; for finding year in references
import re

#language detection
from langdetect import detect

#for getting isbn/issn info
import urllib2

#url encoding
import urllib

#fuzzy matching
from fuzzywuzzy import fuzz

# logging settings
import logging
logger = logging.getLogger('xml2nested')
hdlr = logging.FileHandler('xml2nested.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)

#import misc help functions
import helpfunctions


print '---------- clean filenames --------------'

helpfunctions.cleanFileNames('pdf/')

print '---------- pdf-extract & pdftohtml ------------'

#convert pdf to xml via pdf-extract + pdf to html
helpfunctions.pdf2xml('pdf/', 2)

print ''
print '---------- begin xml to nested xml conversion ------------'

# set dir xml resides in
xml_dir = 'xml/'

# loop through each file in dir
for directory, subdirectories, files in os.walk(xml_dir):
    for file in files:
        print 'Working on: '+os.path.join(directory, file)

        file_location = os.path.join(directory, file)

        with open(file_location, 'r') as myfile:
            xmlstring = myfile.read().replace('</regi\non>', '</region>') #pdf-extract sometimes randomly puts a linebreak in the region tag!
        xmlstring = helpfunctions.invalid_xml_remove(xmlstring,'')
        #print xmlstring
        root = ET.fromstring(xmlstring)

        #tree = ET.ElementTree(file=file_location)
        #root = tree.getroot()

        # first go over the file to try and find a TOC
        # TO-DO

        # set up new xml structure
        section = {}
        exportroot = ET.Element("doc")
        references = ET.SubElement(exportroot, "references")
        section['preamble'] = ET.SubElement(exportroot, "section", name="preamble")
        section['toc'] = ET.SubElement(exportroot, "section", name="toc")
        section['main'] = ET.SubElement(exportroot, "section", name="main")
        section['bibliography'] = ET.SubElement(exportroot, "section", name="bibliography")
        section['images'] = ET.SubElement(exportroot, "section", name="images")
        section['appendices'] = ET.SubElement(exportroot, "section", name="appendices")

        currentsection = "preamble"

        introfound = False
        bibfound = False
        tocpagestart = 0

        lineheights = {}

        nextnodedefined = False
        currentnodedefined = False

        headerareas = {}
        footerareas = {}
        nodeduplicatetest = []

        plaintext = ''

        issn = ''
        issnnode = False
        isbn = ''
        isbnnode = False

        tocAllText = ''

        # STAGE 1 -----------------------------------------------------------------------------------

        documenttitle = ''
        largesttextsizefrontpage = 0
        author1 = False
        authors = False
        firstpagealltext = ''
        # parse front page first, try and find title and/or author
        if root.find('page'):
            for node in root.find('page'):
                if node.text:

                    # find title
                    if float(node.attrib['height']) > largesttextsizefrontpage:
                        documenttitle = node.text
                        largesttextsizefrontpage = float(node.attrib['height'])
                    elif float(node.attrib['height']) == largesttextsizefrontpage:
                        # same size as before, add this node to title
                        documenttitle += ' | ' + node.text

                    # find author
                    match = re.search("([A-Z]\.)+\s[a-zA-Z-. ]+", node.text)
                    if match and not author1:
                        author1 = match.group(0)
                        authors = node.text.split(',') #TODO better author split

                    firstpagealltext += ' ' + node.text
        else:
            # this is an empty xml file, cancel everything and log it
            errormsg = 'File '+os.path.join(directory, file)+' has no pages, skipping'
            print errormsg
            logger.error(errormsg)
            break


        if documenttitle:
            if len(documenttitle) < 300 and len(documenttitle) > 5: #just checking what we found is within reasonable limits for a title
                print 'Title found: ', documenttitle
            else:
                documenttitle = False
        else:
            print 'No title found'

        if not author1:
            # try page 2
            for node in root.findall('page')[1]:
                if(node.text):
                    match = re.search("([A-Z]\.)+\s[a-zA-Z-. ]+", node.text)
                    if match and not author1:
                        author1 = match.group(0)
                        authors = node.text.split(',') #TODO better author split

        if author1:
            print 'Author found: ', author1
            print 'All authors: ', authors

        # loop through elements and put in correct structure
        for page in root:
            nodenumberonpage = 0

            #handle references
            if page.tag == 'reference':
                referencecode = helpfunctions.makereferencecode(page.text)
                page.set('referenceid',referencecode)
                references.append(page)

            for node in page:

                nodenumberonpage += 1
                #print nodenumberonpage, node.text
                #set up node window
                if currentnodedefined:
                    prevnode = currentnode
                if nextnodedefined:
                    currentnode = nextnode
                    currentnodedefined = True
                nextnode = node
                nextnodedefined = True

                # get header/footer x value so we can put header/footer text in separate node types
                if currentnodedefined and currentnode.tag == 'header':
                    headerareas[page.attrib['number']] = currentnode
                elif currentnodedefined and currentnode.tag == 'footer':
                    footerareas[page.attrib['number']] = currentnode

                elif currentnodedefined and currentnode.text:

                    plaintext = plaintext + ' ' + currentnode.text

                    if len(currentnode.attrib['line_height']):
                        #put rounded line-heights and number of chars in that height in dictionary
                        roundedlh = round(float(currentnode.attrib['line_height']),1)
                        lineheights[roundedlh] = lineheights.get(roundedlh,0) + len(currentnode.text)

                    if currentnode.tag == "region" and currentnode.text:
                        # detect toc
                        if \
                            ('inhoudsopgave' in currentnode.text.lower() and len(currentnode.text) < 17)\
                            or ('inhoud' in currentnode.text.lower() and len(currentnode.text) < 9):
                                currentsection = 'toc'
                                tocpagestart = page.attrib['number']
                        # detect introduction
                        if \
                            'inleiding' in currentnode.text.lower()  \
                            and len(currentnode.text) < 15 \
                            and introfound == False \
                            and (currentsection == 'preamble' or (currentsection == 'toc' and tocpagestart != page.attrib['number'])) \
                            and nodenumberonpage < 5:
                                introfound = True
                                currentsection = 'main'
                        # detect bibliography
                        if \
                            ('literatuur' in currentnode.text.lower() or 'bibliografie' in currentnode.text.lower() or 'referenties' in currentnode.text.lower()) \
                            and len(currentnode.text) < 15 \
                            and currentsection != 'toc' \
                            and bibfound == False:
                                bibfound = True
                                currentsection = 'bibliography'
                        # detect images section after bibliography
                        if \
                            ('afbeelding' in currentnode.text[0:11].lower()) \
                            and len(currentnode.text) < 15 \
                            and bibfound == True:
                                currentsection = 'images'
                        # detect appendices
                        if \
                            ('appendix' in currentnode.text.lower() or 'appendices' in currentnode.text.lower() or 'bijlage' in currentnode.text.lower()) \
                            and len(currentnode.text) < 15:
                                currentsection = 'appendices'

                        #add page number to node
                        currentnode.set('pagestart', page.attrib['number'])

                        #get rid of line breaks in node text
                        currentnode.text = currentnode.text.replace('\n',' ')

                        # if node has same page number, x, y, and first 5 chars, it's a duplicate, get rid of the node
                        if node.text is not None:
                            nodeidentification = page.attrib['number'] + node.attrib['x'] + node.attrib[
                                'y'] + node.text[0:5].replace(' ', '')
                            if nodeidentification not in nodeduplicatetest:
                                nodeduplicatetest.append(nodeidentification)
                                #add element to output xmltree
                                section[currentsection].append(currentnode)

                        if currentsection == 'toc':
                            tocAllText += currentnode.text+' '

                        # print text.tag, text.attrib, text.text

                        # check for isbn/issn in node
                        if currentsection == 'preamble':
                            if 'isbn' in currentnode.text.lower() and not isbn:
                                match = re.search("(?:[0-9]{3}-)?[0-9]{1,5}-[0-9]{1,7}-[0-9]{1,6}-[0-9]", currentnode.text)
                                if match:
                                    isbn = match.group(0)
                                else:
                                    #check prev and next node
                                    match = re.search("(?:[0-9]{3}-)?[0-9]{1,5}-[0-9]{1,7}-[0-9]{1,6}-[0-9]", nextnode.text)
                                    if match:
                                        isbn = match.group(0)
                                    else:
                                        match = re.search("(?:[0-9]{3}-)?[0-9]{1,5}-[0-9]{1,7}-[0-9]{1,6}-[0-9]", prevnode.text)
                                        if match:
                                            isbn = match.group(0)
                            elif 'issn' in currentnode.text.lower() and not issn:
                                match = re.search("[\d]{4}\-([\d]{4}|[\d]{3}[xX])", currentnode.text)
                                if match:
                                    issn = match.group(0)
                                else:
                                    #check prev and next node
                                    match = re.search("[\d]{4}\-([\d]{4}|[\d]{3}[xX])", nextnode.text)
                                    if match:
                                        issn = match.group(0)
                                    else:
                                        match = re.search("[\d]{4}\-([\d]{4}|[\d]{3}[xX])", prevnode.text)
                                        if match:
                                            issn = match.group(0)

        print tocAllText

        #get median line height, to be used in heading determinition
        maxlineheightcount = 0
        medianlineheight = 0
        for lineheight in lineheights:
            if lineheights[lineheight] > maxlineheightcount:
                maxlineheightcount = lineheights[lineheight]
                medianlineheight = lineheight
        print 'Median lineheight: ', medianlineheight

        # detect language
        lang = detect(plaintext)

        #indent and output
        helpfunctions.indent(exportroot)
        exporttree = ET.ElementTree(exportroot)
        stage1url = "temp/" + file.replace('.xml','-STAGE1.xml')
        exporttree.write(stage1url)



        #STAGE 2 -----------------------------------------------------------------------------------



        #put paragraphs in headings, tag footercontent
        tree = ET.ElementTree(file=stage1url)
        root = tree.getroot()

        #add language to doc
        root.attrib['lang'] = lang

        # add namespaces for non standard xml tags
        namespaces = {
            'srw': 'http://www.loc.gov/zing/srw/',
            'srw_dc': 'info:srw/schema/1/dc-v1.1',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        # issn / isbn lookup and add to doc if found
        if issn:
            # get info from worldcat
            issnxml = urllib2.urlopen(
                'http://xissn.worldcat.org/webservices/xid/issn/' + issn + '?method=getEditions&format=xml')
            data = issnxml.read()
            issnxml.close()
            issnxml = ET.fromstring(data)
            issnnode = issnxml.getchildren()[0].getchildren()[0]
            # print issnnode

            root.attrib['issn'] = issn
            if issnnode:
                issnnode.tag = 'issn'
                root.append(issnnode)

        # isbn = '978-94-664-791-8'
        if isbn:
            # try RCE first
            isbnxml = urllib2.urlopen(
                'http://cultureelerfgoed.adlibsoft.com/harvest/wwwopac.ashx?database=books&search=pointer%201964%20and%20ISBN=' + isbn.replace(
                    '-', '') + '&limit=10&xmltype=grouped')
            data = isbnxml.read()
            isbnxml.close()
            isbnxml = ET.fromstring(data)
            if len(isbnxml.getchildren()[0].findall('record')):
                isbnnode = isbnxml.getchildren()[0].getchildren()[0]
            else:
                # try KB? TODO
                # try worldcat
                isbnxml = urllib2.urlopen('http://xissn.worldcat.org/webservices/xid/isbn/' + isbn + '?method=getMetadata&format=xml&fl=*')
                data = isbnxml.read()
                print data
                isbnxml.close()
                isbnxml = ET.fromstring(data)
                if isbnxml.attrib['stat'] != "invalidId":
                    isbnnode = isbnxml.getchildren()[0]

            root.attrib['isbn'] = isbn
            if isbnnode:
                isbnnode.tag = 'isbn'
                root.append(isbnnode)
        else:
            # try and find publication by issn and/or title and/or author

            # first try, get publications by issn from KB TODO
            issnxml = urllib2.urlopen('http://jsru.kb.nl/sru/sru?version=1.1&operation=searchRetrieve&x-collection=GGC&query=dcterms:isPartOf=' + issn + '&recordSchema=dcx&maximumRecords=9999')
            data = issnxml.read()
            issnxml.close()
            issnxml = ET.fromstring(data)
            numResults = issnxml.find(".//srw:numberOfRecords",namespaces)
            if int(numResults.text) > 0:
                kbResults = issnxml.find(".//srw:records", namespaces)
                for result in kbResults:
                    dcRecord = result.find(".//srw_dc:dc", namespaces)
                    dcCreators = dcRecord.findall(".//dc:creator", namespaces)
                    dcTitle = dcRecord.find(".//dc:title", namespaces)
                    if fuzz.partial_ratio(dcTitle.text, documenttitle) > 90:
                        print dcTitle.text

            # if no luck, try RCE database
            if author1:
                #take out BA/MA/MSc, get just last name
                author1 = author1.replace(' MA','').replace(' BA','').replace(' MSc','')
                authorLastName = author1.split('. ')
                authorLastName = authorLastName[len(authorLastName)-1]

                resultxml = urllib2.urlopen(
                    'http://cultureelerfgoed.adlibsoft.com/harvest/wwwopac.ashx?database=books&search=pointer%201964%20and%20au="*' + urllib.quote(
                        authorLastName).replace('"', '') + '*"&limit=10&xmltype=grouped')
                data = resultxml.read()
                resultxml.close()
                resultxml = ET.fromstring(data)
                if len(resultxml.getchildren()[0].findall('record')):
                    for doc in resultxml.getchildren()[0].findall('record'):
                        resultTitle = doc.find('title').find('value').text.split(' : ')[0]
                        if resultTitle in firstpagealltext or fuzz.ratio(resultTitle,documenttitle) > 95:
                            doc.tag = 'rcerecord'
                            root.append(doc)
                            break

            elif documenttitle:
                resultxml = urllib2.urlopen(
                    'http://cultureelerfgoed.adlibsoft.com/harvest/wwwopac.ashx?database=books&search=pointer%201964%20and%20ti="*' + urllib.quote(documenttitle).replace('"','') + '*"&limit=10&xmltype=grouped')
                data = resultxml.read()
                print data
                resultxml.close()
                resultxml = ET.fromstring(data)
                if len(resultxml.getchildren()[0].findall('record')):
                    rceresultnode = resultxml.getchildren()[0].getchildren()[0]
                    print rceresultnode



        mainwithheadings = ET.SubElement(root, "section", name="mainwithheadings")

        nextnodedefined = False
        currentnodedefined = False
        lastnodewasheading = False

        # loop through elements in main and put in correct structure
        main = root.find('.//section[@name="main"]')
        for node in main:
            # set up node window
            if currentnodedefined:
                prevnode = currentnode
            if nextnodedefined:
                currentnode = nextnode
                currentnodedefined = True
            nextnode = node
            nextnodedefined = True


            if currentnodedefined:

                # check for text in header, to ignore recurring text
                if headerareas != None and currentnode.attrib['pagestart'] in headerareas:
                    if float(currentnode.attrib['y']) >= float(
                            headerareas[currentnode.attrib['pagestart']].attrib['y']):
                        currentnode.set('possiblefooterheader', '1')

                # check for text in footer, to ignore recurring text and page numbers
                if footerareas != None and currentnode.attrib['pagestart'] in footerareas:
                    if float(currentnode.attrib['y']) <= float(
                            footerareas[currentnode.attrib['pagestart']].attrib['y']):
                        currentnode.set('possiblefooter', '1')

                if 'possiblefooter' in currentnode.attrib or 'possibleheader' in currentnode.attrib:
                    if re.findall("^[0-9]+$", currentnode.text):
                        # it's numerical, check if number in node is +/- 5 from pagestart attribute
                        if int(currentnode.text) in range(int(currentnode.attrib['pagestart']) - 5,
                                                          int(currentnode.attrib['pagestart'])):
                            # it's probably a page number
                            currentnode.set('pagenumbernode', '1')

                if helpfunctions.is_heading(currentnode,medianlineheight):
                    #print currentnode.text
                    # check if we need to concatenate the heading text and number
                    if lastnodewasheading and re.match("^[0-9.\s]+$", currentnode.text):
                        #number in node after text, add number to heading
                        headingtext.text = currentnode.text+' '+headingtext.text
                    elif lastnodewasheading and re.match("^[0-9.\s]+$", headingtext.text):
                        #number in node before text, add text to heading
                        headingtext.text = headingtext.text + ' ' + currentnode.text
                    else:
                        currentheading = ET.SubElement(mainwithheadings, "heading")
                        currentheading.set('pagestart',currentnode.attrib['pagestart'])
                        #headingtext = ET.SubElement(currentheading, "headingtext")
                        headingtext = currentnode
                        headingtext.tag = 'headingtext'
                        currentheading.append(headingtext)

                        lastnodewasheading = True
                else:

                    currentnode.tag = 'paragraph'

                    #add node in new structure
                    if currentheading:
                        currentheading.append(currentnode)
                    else:
                        mainwithheadings.append(currentnode)

                    lastnodewasheading = False

        #delete 'main' section
        #root.remove(main)

        #indent and output
        helpfunctions.indent(root)
        exporttree = ET.ElementTree(root)
        stage2url = "temp/" + file.replace('.xml', '-STAGE2.xml')
        exporttree.write(stage2url)


        #STAGE 3 -----------------------------------------------------------------------------------
        #create nested structure in main section
        tree = ET.ElementTree(file=stage2url)
        root = tree.getroot()

        mainnested = ET.SubElement(root, "section", name="mainnested")

        nextnodedefined = False
        currentnodedefined = False
        lastnodewasheading = False

        # loop through elements in main and put in correct structure
        mainwithheadings = root.find('.//section[@name="mainwithheadings"]')

        lvl = 0
        currentheadingnumber = 0

        currentheading = {}

        for currentnode in mainwithheadings:

            #print currentnode.tag

            headingtext = currentnode.find('.//headingtext').text
            #print headingtext

            headingnumberwithdot = re.findall("[0-9]{1,2}\.[0-9.]+", headingtext)
            headingnumberwithoutdot = re.findall("^[0-9]+", headingtext)

            #check for number with dot first, as some headings have other numbers in them (from superscript for example)
            if headingnumberwithdot:
                #sub level heading
                #print headingnumberwithdot
                lvl = headingnumberwithdot[0].count('.') + 1
                currentnode.set('headinglevel', str(lvl))
                currentnode.set('headingnumber', str(headingnumberwithdot[0]))
                #print lvl

                currentheading[lvl-1].append(currentnode)
                currentheading[lvl] = currentnode

            elif headingnumberwithoutdot:
                #top level heading
                #print headingnumberwithoutdot
                lvl = 1
                currentnode.set('headinglevel', str(lvl))
                currentnode.set('headingnumber', str(headingnumberwithoutdot[0]))
                mainnested.append(currentnode)
                #print currentnode.text
                currentheading[lvl] = currentnode

            else:
                #heading without number, don't nest, keep level
                #print headingtext
                currentheading[lvl] = currentnode

        # delete 'mainwithheadings' section
        #root.remove(mainwithheadings)

        #indent and output
        helpfunctions.indent(root)
        exporttree = ET.ElementTree(root)
        stage3url = "temp/" + file.replace('.xml', '-STAGE3.xml')
        exporttree.write(stage3url)


        #save to output folder, in correct language folder
        outputdir = "nested-xml/"+lang
        if not os.path.exists(outputdir):
            os.makedirs(outputdir)
        outputurl = outputdir + "/" + file
        exporttree.write(outputurl)

        print '---------------------'
