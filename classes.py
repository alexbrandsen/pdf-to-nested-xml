import sys
import re

# import element tree; to parse xml
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

class Document:
    "Class to hold all information about a document"

    docCount = 0

    def __init__(self, fileLocation):
        Document.docCount += 1

        self.fileLocation = fileLocation

        with open(fileLocation, 'r') as myfile:
            xmlstring = myfile.read().replace('</regi\non>', '</region>') #pdf-extract sometimes randomly puts a linebreak in the region tag!
        xmlstring = Document.invalid_xml_remove(xmlstring,'')
        #print xmlstring
        self.root = ET.fromstring(xmlstring)

        # TODO first go over the file to try and find a TOC

        # set up new xml structure
        self.section = {}
        self.exportroot = ET.Element("doc")
        self.references = ET.SubElement(Document.exportroot, "references")
        self.section['preamble'] = ET.SubElement(Document.exportroot, "section", name="preamble")
        self.section['toc'] = ET.SubElement(Document.exportroot, "section", name="toc")
        self.section['main'] = ET.SubElement(Document.exportroot, "section", name="main")
        self.section['bibliography'] = ET.SubElement(Document.exportroot, "section", name="bibliography")
        self.section['images'] = ET.SubElement(Document.exportroot, "section", name="images")
        self.section['appendices'] = ET.SubElement(Document.exportroot, "section", name="appendices")

        self.currentsection = "preamble"

        self.introfound = False
        self.bibfound = False
        self.tocpagestart = 0

        self.lineheights = {}

        self.nextnodedefined = False
        self.currentnodedefined = False

        self.headerareas = {}
        self.footerareas = {}
        self.nodeduplicatetest = []

        self.plaintext = ''

        self.issn = ''
        self.issnnode = False
        self.isbn = ''
        self.isbnnode = False

        self.tocAllText = ''

        self.documenttitle = ''
        self.largesttextsizefrontpage = 0
        self.author1 = False
        self.authors = False
        self.firstpagealltext = ''

        self.medianlineheight = 0

    # to remove invalid characters
    def invalid_xml_remove(self, c, replacement=' '):
        # http://stackoverflow.com/questions/1707890/fast-way-to-filter-illegal-xml-unicode-chars-in-python
        illegal_unichrs = [(0x00, 0x08), (0x0B, 0x1F), (0x7F, 0x84), (0x86, 0x9F),
                           (0xD800, 0xDFFF), (0xFDD0, 0xFDDF), (0xFFFE, 0xFFFF),
                           (0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF), (0x3FFFE, 0x3FFFF),
                           (0x4FFFE, 0x4FFFF), (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
                           (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF), (0x9FFFE, 0x9FFFF),
                           (0xAFFFE, 0xAFFFF), (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
                           (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF), (0xFFFFE, 0xFFFFF),
                           (0x10FFFE, 0x10FFFF)]

        illegal_ranges = ["%s-%s" % (unichr(low), unichr(high))
                          for (low, high) in illegal_unichrs
                          if low < sys.maxunicode]

        illegal_xml_re = re.compile(u'[%s]' % u''.join(illegal_ranges))
        if illegal_xml_re.search(c) is not None:
            # Replace with replacement
            return replacement
        else:
            return c

    def findDocumentNumber(self,node,prevNode,nextNode,type):

        if type == 'isbn':
            pattern = "(?:[0-9]{3}-)?[0-9]{1,5}-[0-9]{1,7}-[0-9]{1,6}-[0-9]"
        elif type == 'issn'
            pattern = "[\d]{4}\-([\d]{4}|[\d]{3}[xX])"

        match = re.search(pattern, node.text)
        if match:
            result = match.group(0)
        else:
            # check prev and next node
            match = re.search(pattern, prevNode.text)
            if match:
                result = match.group(0)
            else:
                match = re.search(pattern, nextNode.text)
                if match:
                    result = match.group(0)
                else:
                    result = False

        if type == 'isbn':
            self.isbn = result
        elif type == 'issn':
            self.issn = result

    def getMedianLineHeight(self):
        maxlineheightcount = 0
        for lineheight in self.lineheights:
            if self.lineheights[lineheight] > maxlineheightcount:
                maxlineheightcount = self.lineheights[lineheight]
                self.medianlineheight = lineheight

        return self.medianlineheight
