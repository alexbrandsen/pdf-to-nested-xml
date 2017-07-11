#import os; to loop through files
import os

#import misc help functions
import helpfunctions

#set dir xml resides in
xml_dir = 'xml/'

#loop through each file in dir
for directory, subdirectories, files in os.walk(xml_dir):
    for file in files:
        #print os.path.join(directory, file)
        file_location = os.path.join(directory, file)

        #clean illegal chars
        newxml = "";
        with open(file_location) as f:
            for line in f:
                for c in line:
                    newxml = newxml + helpfunctions.invalid_xml_remove(c)
        #resave file
        text_file = open(file_location, "w")
        text_file.write(newxml)
        text_file.close()