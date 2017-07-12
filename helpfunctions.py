import re

# import element tree; to parse xml
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

#import subprocess; to call pdf-extract
import subprocess

# import os; to loop through files
import os

# import multithreading
from multiprocessing.dummy import Pool as ThreadPool

# logging settings
import logging
logger = logging.getLogger('pdf-extract')
hdlr = logging.FileHandler('pdf-extract.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)




#indents xml output
#not great, but better than unformatted xml
def indent(elem, level=0):
    i = "\n" + level*"    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

#calculate probability of node being a title, return true if higher than cutoff
def is_heading(xmlnode,medianlineheight,cutoff=1):
    if len(xmlnode.text) == 0:
        return False
    else:
        probability = 0
        font = xmlnode.attrib['font'].lower()
        if \
            'bold' in font[len(font)-4:len(font)] \
            or 'medium' in font[len(font)-6:len(font)] \
            or 'black' in font[len(font)-5:len(font)] :
                probability += 0.8
        if xmlnode.text.isupper() and len(xmlnode.text) > 5:
            probability += 0.3
            print xmlnode.text
        if float(xmlnode.attrib['line_height']) > float(medianlineheight):
            probability += 0.8
            print xmlnode.text
        #the below rule excludes situations where the number of a heading ends up in the prev/next node..
        #if not re.search('[a-zA-Z]', xmlnode.text):
            #probability -= 1
        if len(xmlnode.text) < 5 and not xmlnode.text.isdigit():
            probability -= 0.5
            #print '<5',xmlnode.text

        #print xmlnode.text, xmlnode.attrib['line_height'], medianlineheight, probability

        if probability >= cutoff:
            return True
        else:
            return False


#detect if text is indented
def is_indented(currentnode, prevnode):
    if currentnode.attrib['x'] > prevnode.attrib['x']:
        return True

#create reference code from full reference text
def makereferencecode(reference):
    firstauthorlastname = reference.split(',')
    if len(firstauthorlastname):
        firstauthorlastname = firstauthorlastname[0]
    else:
        firstauthorlastname = "****"

    year = re.findall('(\d{4})', reference)
    if len(year):
        year = year[0]
        title20chars = reference.split(year)[1].replace(':', '').replace(' ', '')
        if len(title20chars):
            title20chars = title20chars[0:20]
        else:
            title20chars = "*" * 20
    else:
        year = "****"
        title20chars = "*" * 20


    return firstauthorlastname+'|'+year+'|'+title20chars

def cleanFileNames(dir):
    # loop through each file in dir
    for directory, subdirectories, files in os.walk(dir):
        for file in files:
            file_location = os.path.join(directory, file)
            clean_file_location = file_location.replace(' ', '_')
            if file_location != clean_file_location:
                print file_location, ' renamed to ', clean_file_location
                os.rename(file_location,clean_file_location)
    print "All filenames cleaned"

def pdf2xml(xml_dir='pdf/', numberOfThreads = 1):

    fileNameArray = []

    # loop through each file in dir
    for directory, subdirectories, files in os.walk(xml_dir):
        for file in files:

            file_location = os.path.join(directory, file)

            #create sub directory if needed
            xmlDirectory = directory.replace('pdf/', 'xml/')
            if not os.path.exists(xmlDirectory):
                os.makedirs(xmlDirectory)

            fileNameArray.append(file_location)

    # multi threading!
    pool = ThreadPool(numberOfThreads)
    pool.map(pdf2xml1file, fileNameArray)



def pdf2xml1file(file):
    errormsg = False

    # pdf-extract first
    # if xml does not already exist
    if not os.path.isfile('xml/' + file.replace('.pdf', '.xml').replace('pdf/', '')):

        print "Converting " + file + " to xml"

        try:
            cmnd = 'pdf-extract extract --references --headers --footers --no-lines --regions --set char_slop:0.4 ' + file.replace(' ', '\ ') + ' > ' + file.replace('pdf/','xml/').replace('.pdf', '.xml').replace(' ','\ ')
            output = subprocess.check_output(
                cmnd, stderr=subprocess.STDOUT, shell=True,
                universal_newlines=True)
        except subprocess.CalledProcessError as exc:
            if "undefined method `*' for nil:NilClass" in exc.output:
                #problem with reference extraction, try without reference extraction
                try:
                    cmnd = 'pdf-extract extract --headers --footers --no-lines --regions --set char_slop:0.4 ' + file.replace(
                        ' ', '\ ') + ' > ' + file.replace('pdf/', 'xml/').replace('.pdf', '.xml').replace(' ', '\ ')
                    output = subprocess.check_output(
                        cmnd, stderr=subprocess.STDOUT, shell=True,
                        universal_newlines=True)
                except subprocess.CalledProcessError as exc:
                    #still an error present
                    errormsg = "pdf-extract error for file " + file + " " + exc.output
                else:
                    print "Converted " + file + " to xml! (no references)"
            else:
                errormsg = "pdf-extract error for file " + file + " " + exc.output

            if errormsg:
                # error in pdf-extract, discard output file and write to log
                print errormsg
                logger.error(errormsg)
                os.remove(file.replace('pdf/','xml/').replace('.pdf', '.xml'))
        else:
            print "Converted " + file + " to xml!"
    else:
        print file.replace('pdf/','xml/').replace('.pdf', '.xml') + " already exists, skipping"

    #then do html conversion
    # TODO maybe use md5 of file for folder name to stop clashes?
    htmlDir = 'html/' + file.replace('.pdf', '').replace('pdf/', '')
    if not os.path.isdir(htmlDir):
        # first create folder for html to go in

        _mkdir(htmlDir)

        try:
            cmnd = 'pdftohtml -c -nodrm ' + file.replace(' ', '\ ') + ' ' + htmlDir + '/index.html'
            output = subprocess.check_output(
                cmnd, stderr=subprocess.STDOUT, shell=True,
                universal_newlines=True)
        except subprocess.CalledProcessError as exc:
            errormsg = "pdftohtml error for file " + file + " " + exc.output
            print errormsg
            logger.error(errormsg)
            os.rmdir(htmlDir)
        else:
            print "Converted " + file + " to html!"

    else:
        print file + " html folder already exists, skipping"


def _mkdir(_dir):
    if os.path.isdir(_dir): pass
    elif os.path.isfile(_dir):
        raise OSError("%s exists as a regular file." % _dir)
    else:
        parent, directory = os.path.split(_dir)
        if parent and not os.path.isdir(parent): _mkdir(parent)
        if directory: os.mkdir(_dir)



