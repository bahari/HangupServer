#############################################################################################################
# File:        hangupserver.py
# Description: Program for handling asterisk call termination from remote site. After each bridging and call 
#              dispatching, operator can request to terminate current connected asterisk call remotely.
#              Remote communication request are done via RestAPI. 
#              ----------------------------------------------------------------------------------------------
# Notes      : Major, Minor and Revision notes:
#              ----------------------------------------------------------------------------------------------
#              Major    - Software major number will counting up each time there is a major changes on the 
#                         software features. Minor number will reset to '0' and revision number will reset
#                         to '1' (on each major changes). Initially major number will be set to '1'
#              Minor    - Software minor number will counting up each time there is a minor changes on the
#                         software. Revision number will reset to '1' (on each minor changes).
#              Revision - Software revision number will counting up each time there is a bug fixing on the
#                         on the current major and minor number.
#              ----------------------------------------------------------------------------------------------
#              Current Features & Bug Fixing Information
#              ----------------------------------------------------------------------------------------------
#              0001      - Provide remote dispatch call termination via REST API executed by dispatcher
#                          web server.
#              0002      - Call termination are executed by using asterisk command that run inside terminal
#                          via python subprocess popen.
#              0003      - Provide call termination status after each termination request by a dispatcher
#                          web server. Dispatcher web server can used this status info for its own notification
#                          process.
#              0004      - Add macro option for log print, log to text file or normal print statement.
#              0005      - Add macro option for REST API request, secure (HTTPS) or not secure (HTTP).
#              0006      - Add REST API GET request to get the updated extensions/contact list from asterisk server.
#              0007      - Add a function to retrieve extensions list from asterisk server and updated the list
#                          in XML format.
#              0008      - Add a function to arrange/prettify the XML file for extensions/contact list.
#              0009      - Add a python data dictionary for extensions list update data status (listUpdtData).
#              0010      - Add a python data dictionary for extensions list update data error status (updateFailed).
#              0011      - Add a python data dictionary for extensions/contact list data array (contactListData).
#              0012      - Add a python data dictionary for webrtc contact list data array (webRtcContListData).
#              0013      - Add REST API PUT request to update python dictionary and XML file for webrtc extensions/
#                          contact list.
#              0014      - Add a reading process for intercom list XML file during daemon load.
#              0015      - Add a function to get a current intercom extensions from asterisk extensions.conf
#                          and update the intercom list of data in XML format.
#              0016      - Add a REST API call back function to update a current intercom list of data based
#                          on any changes inside asterisk extensions.conf when requested by dispatcher
#                          web client.
#              0017      - Add a get current call audio file inside recordings folder and update recordings
#                          XML file via getRecordFile() function call during daemon starts.
#              0018      - Add a function to get a current call audio file from recordings folder and update
#                          the current recordings list of data in XML format.
#              0019      - Add a REST API call back function to update a current recordings list of data based
#                          on any updated inside recordings folder when requested by dispatcher web client.
#              0020      - Remove SIP WebRTC python data dictionary initialization at the get updated contact list 
#                          function (getContactList()).
#              0021      - Add conference type of filter during get intercom list REST API functionality. This changes
#                          allow dispatcher web client to get a conference list from Asterisk extensions.conf file.
#              0022      - Add delete recording file REST API request function from remote MASURI+IPBX - Dispatcher
#                          web client. Upon request with recording file name that need to be deleted, this function
#                          will execute delete file command automatically and refresh the XML list for recording file.
#              0023      - Add script segments to handle writing recording XML files with a default value, when there
#                          is NO recording file exists inside folder.
#              0024      - Add import settings for total audio recordings that need to be retain in the server folder.
#              0025      - Add a script segments logic to limit the total audio recording files that need to be
#                          retain based on the settings.
#              0026      - Refine the scripts logic for limiting number of audio recording file that need to be retain
#                          inside server recording folder. 
#              0027      - Comments out necessary logics and replace with the new script segments during get current
#                          audio recording file request from dispatcher web client.
#              0028      - Add logic script to check first current total audio recording file whether its exist
#                          or not before execute delete record file and copy audio recording file name process. 
#              0029      - Create a separate thread to delete audio recording file during request by dispatcher
#                          web client.
#              0030      - Comments out delete recording file logic inside get recording file function.  
#              0031      - Added getContactListFromSip() function, that reads through sip.conf file, in getting the
#                          needed parameters of the account on that file. The parameters are then appeneded to contactListData
#                          having a combination of users from users.conf and sip.conf. (Mohd Danial Hariz Bin Norazam)
#
#              ----------------------------------------------------------------------------------------------   
# Author : Ahmad Bahari Nizam B. Abu Bakar, Mohd Danial Hariz Bin Norazam
# Version: 1.0.1
# Version: 1.1.1 - Add feature item [0004,0005,0006,0007,0008,0009,0010,0011,0012].
#                  Please refer to above description.
# Version: 1.1.2 - Add feature item [0013]
# Version: 1.1.3 - Add feature item [0014,0015,0016]
# Version: 1.1.4 - Add feature item [0017,0018,0019]
# Version  1.1.5 - Add feature item [0020]
# Version  1.1.6 - Add feature item [0021,0022]
# Version  1.1.7 - Add feature item [0023]
# Version  1.1.8 - Add feature item [0024,0025,0026,0027]
# Version  1.1.9 - Add feature item [0029,0030]
# Version  1.1.10 - Add feature item [0031]
#
# Date   : 29/01/2020 (INITIAL RELEASE DATE)
#          UPDATED - 18/04/2020 - 1.1.1
#          UPDATED - 20/04/2020 - 1.1.2
#          UPDATED - 07/08/2021 - 1.1.3
#          UPDATED - 20/10/2021 - 1.1.4
#          UPDATED - 01/11/2021 - 1.1.5
#          UPDATED - 14/11/2021 - 1.1.6
#          UPDATED - 15/11/2021 - 1.1.7
#          UPDATED - 21/11/2021 - 1.1.8
#          UPDATED - 26/11/2021 - 1.1.9
#          UPDATED - 24/02/2023 - 1.1.10
#
#############################################################################################################

import logging
import logging.handlers
import sys
import os
import signal
import time
import thread
import subprocess
import glob

import xml.etree.ElementTree as ET
import asterisk.config

# REST API library
from flask import Flask
from flask import jsonify
from flask import request

# Import settings
from settings import totalrecordings

app = Flask(__name__)

# String manipulation
def mid(s, offset, amount):
    return s[offset - 1:offset + amount - 1]

# Prettify pass xml object
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
            
# Global variable declaration
backLogger         = False    # Macro for logger
secureInSecure     = False    # Macro for secure (https) or insecure (http) mode
testxml            = False    # Macro for stored extensions/contact list folder location
xmlTree            = ''       # XML parse from XML file
xmlRoot            = ''       # XML root element from parse XML file
firstDat           = False    # Python dictionary first data initialization
deleteProc         = False    # Delete process flag
recordFile         = []       # Call recording file name buffer
fileNeedToDelete   = []       # File that need to be deleted buffer
totRecordFile      = 0        # Total call recording file 
fileToDeleteCnt    = 0        # Total file to delete counter

# Copy total audio recording files from settings that need to retain inside server
totRetainRecFile   = totalrecordings  

# Check for macro arguments
if (len(sys.argv) > 1):
    for x in sys.argv:
        # Optional macro if we want to enable text file log
        if x == "LOGGER":
            backLogger = True
        # Optional macro if we want to enable https
        elif x == "SECURE":
            secureInSecure = True
        elif x == "XML":
            testxml = True            
        
# Setup log file
if backLogger == True:
    path = os.path.dirname(os.path.abspath(__file__))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logfile = logging.handlers.TimedRotatingFileHandler('/tmp/hangupserver.log', when="midnight", backupCount=3)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    logger.addHandler(logfile)

# Channel CALL status data
hangupData=[
    {
        'id' : '000',
        'callchannel' : '0000',
        'status' : 'TERMINATED'
    }
]

# List UPDATED status data
listUpdtData=[
    {
        'type' : 'Normal',
        'status' : 'SUCCESFULL',
        'ext' : '0000',
        'fullname' : 'NA'
    },
    {
        'type' : 'Webrtc',
        'status' : 'SUCCESFULL',
        'ext' : '0000',
        'fullname' : 'NA'
    },
    {
        'type' : 'Intercomm',
        'status' : 'SUCCESFULL',
        'ext' : '0000',
        'fullname' : 'NA'
    },
    {
        'type' : 'Recording',
        'status' : 'SUCCESFULL',
        'ext' : '0000',
        'fullname' : 'NA'
    }
]

# Error during UPDATE
updateFailed={
    'type' : 'Update',
    'status' : 'FAILED'
}

# Normal contact list data
contactListData=[
    {
        'ext' : '0000',
        'fullname' : 'NA',
        'type' : 'NA',
        'ip' : 'NA'
    }
]

# WebRTC contact list data
webRtcContListData=[
    {
        'ext' : '0000',
        'fullname' : 'NA',
        'pswd' : 'NA',
        'ip' : 'NA',
        'sip' : 'NA',
        'avail' : 'NA'
    }
]

# Intercom contact list data
intercomListData=[
		{
        'ext' : '0000',
        'fullname' : 'NA',
        'type' : 'NA',
        'ip' : 'NA'
    }
]

# Read XML files, and then update python dictionary data
# Normal extensions/contact list
try:
    # Actual stored folder location
    if testxml == True:
        xmlTree = ET.parse("/var/www/html/listContact.xml")
    # Test stored folder location
    else:
        xmlTree = ET.parse("listContact.xml")
        
    xmlRoot = xmlTree.getroot()
    # Start get the data from XML file and arrange it to python dictionary array
    for val in xmlRoot.findall('INFO'):
        ipAddr = val.find('IPADDR').text
        loc = val.find('LOCATION').text
        callId = val.find('CALLID').text
        typ = val.find('TYPE').text

        # First data update
        if firstDat == False:
            extDB = [ extDBB for extDBB in contactListData ]
            extDB[0]['ext'] = callId
            extDB[0]['fullname'] = loc
            extDB[0]['type'] = typ
            extDB[0]['ip'] = ipAddr

            firstDat = True
        # New data update
        else:
            # Construct the new data
            newData = {
                        'ext':callId,
                        'fullname':loc,
                        'type':typ,
                        'ip' : ipAddr
                        }
            # Append a NEW extension to the existing record
            contactListData.append(newData)
except:
    # Write to logger
    if backLogger == True:
        logger.info("DEBUG_LD_XML: Open listContact.xml config file failed!")
    # Print statement
    else:
        print "DEBUG_LD_XML: Open listContact.xml config file failed!"    

# Read XML files, and then update python dictionary data
# SIP WebRTC contact list
try:
    firstDat = False
    
    # Actual stored folder location
    if testxml == True:
        xmlTree = ET.parse("/var/www/html/registrarlist.xml")
    # Test stored folder location
    else:
        xmlTree = ET.parse("registrarlist.xml")
		
    xmlRoot = xmlTree.getroot()
    # Start get the data from XML file and arrange it to python dictionary array
    for val in xmlRoot.findall('SERVER'):
        ipAddr = val.find('IPADDR').text
        loc = val.find('LOCATION').text
        avail = val.find('AVAIL').text
        uname = val.find('USERNAME').text
        sipAddr = val.find('SIPADDR').text
        pswd = val.find('PSWD').text
        
        # First data update
        if firstDat == False:
            extDB = [ extDBB for extDBB in webRtcContListData ]
            extDB[0]['ip'] = ipAddr
            extDB[0]['fullname'] = loc
            extDB[0]['ext'] = uname
            extDB[0]['sip'] = sipAddr
            extDB[0]['pswd'] = pswd
            extDB[0]['avail'] = avail

            firstDat = True
        # New data update
        else:
            # Construct the new data
            newData = {
                        'ext' : uname,
                        'fullname' : loc,
                        'pswd' : pswd,
                        'ip' : ipAddr,
                        'sip' : sipAddr,
                        'avail' : avail
                        }
            # Append a NEW extension to the existing record
            webRtcContListData.append(newData)
except:
    # Write to logger
    if backLogger == True:
        logger.info("DEBUG_LD_XML: Open registrarlist.xml config file failed!")
    # Print statement
    else:
        print "DEBUG_LD_XML: Open registrarlist.xml config file failed!"

# Read XML files, and then update python dictionary data
# Intercom contact list
try:
    firstDat = False

    # Actual stored folder location
    if testxml == True:
        xmlTree = ET.parse("/var/www/html/intercomlist.xml")
    # Test stored folder location
    else:
        xmlTree = ET.parse("intercomlist.xml")

    xmlRoot = xmlTree.getroot()
    # Start get the data from XML file and arrange it to python dictionary array
    for val in xmlRoot.findall('INFO'):
        ipAddr = val.find('IPADDR').text
        loc = val.find('LOCATION').text
        callId = val.find('CALLID').text
        typ = val.find('TYPE').text

        # First data update
        if firstDat == False:
            extDB = [ extDBB for extDBB in intercomListData ]
            extDB[0]['ext'] = callId
            extDB[0]['fullname'] = loc
            extDB[0]['type'] = typ
            extDB[0]['ip'] = ipAddr

            firstDat = True
        # New data update
        else:
            # Construct the new data
            newData = {
                        'ext':callId,
                        'fullname':loc,
                        'type':typ,
                        'ip' : ipAddr
                        }
            # Append a NEW extension to the existing record
            intercomListData.append(newData)
except:
    # Write to logger
    if backLogger == True:
        logger.info("DEBUG_LD_XML: Open intercomlist.xml config file failed!")
    # Print statement
    else:
        print "DEBUG_LD_XML: Open intercomlist.xml config file failed!"

# Retrieve current call recording file from folder
# Then insert the recording file data to XML file
def getRecordFile():
    global recordFile 
    global totRecordFile
    global testxml
    global totRetainRecFile
    global fileNeedToDelete
    global fileToDeleteCnt   
    global deleteProc
    
    retResult = False
    fileName = ''
    fileNameCnt = 0
    tempDateTimeOfCall = ''
    dateTimeOfCall = []
    dashCnt = 0
    tempExtInvol = ''
    extInvol = []
    arrayCnt = 0
    dataSelect = 0
    fileToDelete = ''
    realTotRecFile = 0

    # For testing purposes
    #testxml = False
    
    # Copy curent call recording file name to array
    # recordFile = glob.glob("/var/www/html/recordings/*.ogg")
    # Standard file name: 2021-10-14-0302-6004-6000.ogg
    # XML file will consists of: 01 - Date Of Call
    #                            02 - Time Of Call
    #                            03 - Extensions involved
    # Get the total recording file 
    # Actual stored folder location
    if testxml == True:
        # Get the total record file inside selected folder
        totRecordFile = len(glob.glob("/var/www/html/recordings/*.ogg"))
        # Populate the file name inside selected folder
        recordFile = glob.glob("/var/www/html/recordings/*.ogg")
        # Start sorted recordfile based on the date and time - descending
        recordFile = sorted(recordFile, key=lambda t: -os.stat(t).st_mtime)
        # Get the file name without detail path - only the file name
        recordFile = map(os.path.basename, recordFile)
        
    # For testing purposes
    else:
        # Get the total record file inside selected folder
        totRecordFile = len(glob.glob("/home/bahari/MyWorks/Projects/MasuriPlus-VdgPlus/backup-masuri-plus-ipbx-13102021/monitor/*.ogg"))
        # Populate the file name inside selected folder
        recordFile = glob.glob("/home/bahari/MyWorks/Projects/MasuriPlus-VdgPlus/backup-masuri-plus-ipbx-13102021/monitor/*.ogg")
        # Start sorted record file based on the date and time - descending
        recordFile = sorted(recordFile, key=lambda t: -os.stat(t).st_mtime)
        # Get the file name without detail path - only the file name
        recordFile = map(os.path.basename, recordFile)
    
    # Only execute when delete audio recording file process are not busy
    if deleteProc == False:
        # Go through the record file name inside folder
        if totRecordFile > 0:
            for a in range(totRecordFile):
                fileName = recordFile[a] 
                #fileNameCnt = len(fileName)

                # Audio recording file already exceed the limit
                # Start delete the older recording file 
                if a >= totRetainRecFile and fileName != '':
                    # Set delete process flag
                    deleteProc = True
                    # Copy the audio recording file that need to be deleted to the buffer
                    fileNeedToDelete.append(fileName) 
                    # Increment file that need to be deleted counter
                    fileToDeleteCnt = fileToDeleteCnt + 1

#                    # Copy file detail name to the variable
#                    fileToDelete = '/var/www/html/recordings/' + fileName
#
#                    # Start delete the recording file
#                    tempArgs = 'rm -r ' + fileToDelete 
#                    out = subprocess.Popen([tempArgs], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#                    stdout,stderr = out.communicate()
#                    # NO error after command execution
#                    if stderr == None:
#                        # Write to logger
#                        if backLogger == True:
#                            logger.info("DEBUG_AST_REC_DELETE: Delete File: %s SUCCESFULL" % (fileName))
#                        # Print statement
#                        else:
#                            print "DEBUG_AST_REC_DELETE: Delete File: %s SUCCESFULL" % (fileName)
#
#                    # Error during command execution        
#                    else:
#                        # Write to logger
#                        if backLogger == True:
#                            logger.info("DEBUG_AST_REC_DELETE: Delete File: %s FAILED!" % (fileName))
#                        # Print statement
#                        else:
#                            print "DEBUG_AST_REC_DELETE: Delete File: %s FAILED!" % (fileName)
#
#                    # Wait before execute another command
#                    time.sleep(1)

                # Still within the range 
                else:
                    # Copy current recording index no. 
                    realTotRecFile = a
                    # Increment by 1 to indicate current total audio recording file 
                    realTotRecFile = realTotRecFile + 1

                    fileNameCnt = len(fileName)
                    # Go through each char of file name to retrieved
                    # Date, time and extensions involved
                    for b in range(0, (fileNameCnt + 1)):
                        oneChar = mid(fileName, b, 1)
                        # Get recording date and time 
                        if dataSelect == 0:
                            # To eliminate 'ogg' audio container name
                            if oneChar != 'o' and oneChar != 'g':
                                # Count dash char 
                                if oneChar == '-':
                                    dashCnt += 1
                                    if dashCnt < 4:
                                        tempDateTimeOfCall += oneChar
                                # Append the char for date and time data
                                elif dashCnt < 4:
                                    tempDateTimeOfCall += oneChar 
                                # Finish get the full date and time data 
                                elif dashCnt == 4:
                                    dateTimeOfCall.append(tempDateTimeOfCall)
                                    arrayCnt += 1

                                    tempExtInvol += oneChar
                                    dataSelect = 1
                                    dashCnt = 0

                        # Get the recording call extensions data
                        elif dataSelect == 1:
                            # Append the char for call extensions data
                            if oneChar != '.':
                                tempExtInvol += oneChar
                            # Finish get the full call extensions data
                            elif oneChar == '.':
                                extInvol.append(tempExtInvol)

                                # Re initialize necessary variable
                                dataSelect = 0
                                tempExtInvol = ''
                                tempDateTimeOfCall = ''

        # Start construct recording XML files
        try:
             # Create intercom extension list xml file structure
            firstRecordXml = False
            xmlTree = ''

            xmlRecordRoot = ET.Element('RECORDING')
            xmlRecordItems = ET.SubElement(xmlRecordRoot, 'INFO')

            # Has recording file
            #if totRecordFile > 0:
            if realTotRecFile > 0:
                # Start insert the recording data to the xml file
                #for a in range(totRecordFile):
                for a in range(realTotRecFile):
                    if firstRecordXml == False:
                        ET.SubElement(xmlRecordItems, 'DATETIME').text = dateTimeOfCall[a]
                        ET.SubElement(xmlRecordItems, 'EXTENSIONS').text = extInvol[a]
                        ET.SubElement(xmlRecordItems, 'FILEPATH').text = recordFile[a]

                        firstRecordXml = True

                    else:
                        secXmlRecordItems = ET.SubElement(xmlRecordRoot, 'INFO')

                        ET.SubElement(secXmlRecordItems, 'DATETIME').text = dateTimeOfCall[a]
                        ET.SubElement(secXmlRecordItems, 'EXTENSIONS').text = extInvol[a]
                        ET.SubElement(secXmlRecordItems, 'FILEPATH').text = recordFile[a]

            # NO recording file
            else:
                ET.SubElement(xmlRecordItems, 'DATETIME').text = 'NA'
                ET.SubElement(xmlRecordItems, 'EXTENSIONS').text = 'NA'
                ET.SubElement(xmlRecordItems, 'FILEPATH').text = 'NA'

            # Create the xml file
            # Arrange/prettify the xml structure
            indent(xmlRecordRoot)

            xmlTree = ET.ElementTree(xmlRecordRoot)
            # Actual stored folder location
            if testxml == True:
                xmlTree.write("/var/www/html/recordinglist.xml")
            # Test stored folder location
            else:
                xmlTree.write("recordinglist.xml")

            retResult = True  
        except:        
            # Write to logger
            if backLogger == True:
                logger.info("DEBUG_AST_REC_LIST: Create xml config file failed!")
            # Print statement
            else:
                print "DEBUG_AST_REC_LIST: Create xml config file failed!"
            return retResult
    
    # Delete audio recording file process BUSY
    else:
        # Write to logger
            if backLogger == True:
                logger.info("DEBUG_AST_REC_LIST: Delete process BUSY!")
            # Print statement
            else:
                print "DEBUG_AST_REC_LIST: Delete process BUSY!"
            return retResult
    
    return retResult            
    
# Get and process intercom contact list from asterisk extensions.conf
def getIntercomList(extnNumber, typeUpdt):
    global intercomListData
    global testxml
    
    retResult = False
    firstDatUpdt = False
    intercomData = '' 
    intercomExt = ''
    extType = ''
    extNo = ''
    extFullName = ''
    retExtNo = ''
    retFullNme = ''
    flagCnt = 0

    # Reinitialize back intercom list python dictionary data
    intercomListData=[
        {
            'ext' : '0000',
            'fullname' : 'NA',
            'type' : 'NA',
            'ip' : 'NA'
        }
    ]
		
    try:
        usersCnfg = asterisk.config.Config('/etc/asterisk/extensions.conf')
    except asterisk.config.ParseError as e:
        # Write to logger
        if backLogger == True:
            logger.info("DEBUG_AST_ICOM_CONFIG: Parse Error line: %s: %s" % (e.line, e.strerror))
        # Print statement
        else:
            print "DEBUG_AST_ICOM_CONFIG: Parse Error line: %s: %s" % (e.line, e.strerror)
        return retResult
				
    # Start access asterisk extensions.conf categories
    for category in usersCnfg.categories:
        extType = ''
        extNo = ''
        extFullName = ''
        flagCnt = 0

        # Special intercom extensions for category name  
        #if 'intercomm' in category.name:
        if 'intercomm' in category.name or 'conferences-' in category.name:
            # Copy the category name, to get extensions number, type and location 
            intercomData = category.name
            datLen = len(intercomData)
            # Start extract intercom data
            # Sample data format: intercom-1010-Bilik_SENJATA
            for a in range(0, (datLen + 1)):
                oneChar = mid(intercomData, a, 1)
                # Get extension type
                if flagCnt == 0:
                    if oneChar != '-':
                        extType += oneChar
                    elif oneChar == '-':
                        flagCnt = 1
                # Get intercom extension no.
                elif flagCnt == 1:
                    if oneChar != '-':
                        extNo += oneChar
                    elif oneChar == '-':
                        flagCnt = 2
                # Get intercome full name or location
                elif flagCnt == 2:
                    extFullName += oneChar
                                
            # Start updating process for python data dictionary
            try:
                # Update first data from existing dummy python data dictionary 
                if firstDatUpdt == False:
                    extDB = [ extDBB for extDBB in intercomListData ]
                    extDB[0]['ext'] = extNo

                    # Look location/full name info for this extension no.
                    if extnNumber == extNo:
                        # Only take changes
                        if extDB[0]['fullname'] != extFullName:
                            # Return value
                            retExtNo = extNo
                            retFullNme = extFullName
                                                    
                    extDB[0]['fullname'] = extFullName
                    extDB[0]['type'] = extType

                    firstDatUpdt = True
                else:
                    # Check the extensions whether its already exist or not
                    extDB = [ extDBB for extDBB in intercomListData if (extDBB['ext'] == extNo) ]
                    # Update the existing data, throw error if record is not exist, consider its a new data
                    # Look location/full name info for this extension no.
                    if extnNumber == extNo:
                        # Only take changes
                        if extDB[0]['fullname'] != extFullName:
                            # Return value
                            retExtNo = extNo
                            retFullNme = extFullName
                                                    
                    extDB[0]['fullname'] = extFullName
                    extDB[0]['type'] = extType
												
            # NEW intercom list
            except:
                # Construct the new data
                newData = {
                            'ext':extNo,
                            'fullname':extFullName,
                            'type':extType,
                            'ip':'NA'
                            }
                
                # Append a NEW intercom extension to the existing record
                intercomListData.append(newData)
		
    try:
        # Create intercom extension list xml file structure
        firstContactXml = False
        xmlTree = ''
				
        xmlContactRoot = ET.Element('CONTACT')
        xmlContactItems = ET.SubElement(xmlContactRoot, 'INFO')

        # Start insert the python data dictionary to the xml file
        for extData in intercomListData:
            if firstContactXml == False:
                # Only update IP address to a new value, if previously the setting already take place
                if extData['ip'] != 'NA':
                    ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                else:
                    ET.SubElement(xmlContactItems, 'IPADDR').text = 'NA'
                                
                ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']
                ET.SubElement(xmlContactItems, 'CALLID').text = extData['ext']
                ET.SubElement(xmlContactItems, 'SERVERID').text = 'NA'
                ET.SubElement(xmlContactItems, 'TYPE').text = extData['type']
                
                firstContactXml = True
            else:
                secXmlContactItems = ET.SubElement(xmlContactRoot, 'INFO')

                # Only update IP address to a new value, if previously the setting already take place
                if extData['ip'] != 'NA':
                    ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                else:
                    ET.SubElement(secXmlContactItems, 'IPADDR').text = 'NA'
                                
                ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']
                ET.SubElement(secXmlContactItems, 'CALLID').text = extData['ext']
                ET.SubElement(secXmlContactItems, 'SERVERID').text = 'NA'
                ET.SubElement(secXmlContactItems, 'TYPE').text = extData['type']
								
        # Create the xml file
        # Arrange/prettify the xml structure
        indent(xmlContactRoot)
                                        
        xmlTree = ET.ElementTree(xmlContactRoot)
        # Actual stored folder location
        if testxml == True:
            xmlTree.write("/var/www/html/intercomlist.xml")
        # Test stored folder location
        else:
            xmlTree.write("intercomlist.xml")

        retResult = True
    except:
        # Write to logger
        if backLogger == True:
            logger.info("DEBUG_AST_ICOM_CONFIG: Create xml config file failed!")
        # Print statement
        else:
            print "DEBUG_AST_ICOM_CONFIG: Create xml config file failed!"
        return retResult
				
    return retResult, retExtNo, retFullNme

def getContactListFromSip(typeUpdt,frstNormTypData):
    global contactListData
    
    extName = ''
    extNumber = ''
    
    # load and parse the config file
    try:
        sipCnfg = asterisk.config.Config('/etc/asterisk/sip.conf')
    except asterisk.config.ParseError as e:
        print ("Parse Error line: %s: %s") % (e.line, e.strerror)
        sys.exit(1)
    except IOError as e:
        print ("Error opening file: %s") % e.strerror
        sys.exit(1)
        
    for category in sipCnfg.categories:    
        if category.name != 'general' and category.name != 'tgprovider':
            extType = ''
            extNumber = category.name
            
            for item in category.items:
                if item.name == 'callerid':
                    #Since sip.conf does not have fullname, we use the item callerid to get its extension type and extension name
                    #However, because of its format, there will be '<extNumber>' at the end, so we will filter that out from the string
                    extName = item.value.replace("<"+extNumber+">",'')
                    extName = extName.replace('"','')
                    extNLen = extName.find(':') #this function returns the length until it meets ':'
                    # Get the extension type from the extension full name
                    for a in range(extNLen):
                        extType += extName[a]
                    break # since callerid is in the middle row, and other items on row below is not used, then we break here
                    
            # Normal extension       
            if extType != 'FXO' and typeUpdt == 'Normal':
                try:
                    if not frstNormTypData:
                        contactListData[0]['ext'] = extNumber
                        contactListData[0]['fullname'] = extName
                        contactListData[0]['type'] = extType
                        frstNormTypData = True
                    else:
                    # Construct the new data
                        newData = {
                                    'ext':extNumber,
                                    'fullname':extName,
                                    'type':extType,
                                    'ip':'NA'
                                    }
                        # Append a NEW extension to the existing record
                        contactListData.append(newData)       
                except Exception as e :
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print(exc_type, fname, exc_tb.tb_lineno)
    print contactListData

# Get and process contact list from asterisk users.conf
def getContactList(extnNumber, typeUpdt):
    global testxml
    global backLogger
    global webRtcContListData
    global contactListData
            
    retResult = False
    frstNormTypData = False
    frstWRtcTypData = False
    extTypeStrt = False
    extNumber = ''
    extName = ''
    extType = ''    
    extSecret = ''
    retExtNo = ''
    retFullNme = ''
    
    extNLen = 0

    # Reinitialize back extensions list python dictionary data
    if typeUpdt == 'Normal':
        contactListData=[
            {
                'ext' : '0000',
                'fullname' : 'NA',
                'type' : 'NA',
                'ip' : 'NA'
            }
        ]
    # Reinitialize back SIP WebRTC list python dictionary data
#    else:
#        webRtcContListData=[
#            {
#                'ext' : '0000',
#                'fullname' : 'NA',
#                'pswd' : 'NA',
#                'ip' : 'NA',
#                'sip' : 'NA',
#                'avail' : 'NA'
#            }
#        ]
    
    try:
        usersCnfg = asterisk.config.Config('/etc/asterisk/users.conf')
    except asterisk.config.ParseError as e:
        # Write to logger
        if backLogger == True:
            logger.info("DEBUG_AST_CONFIG: Parse Error line: %s: %s" % (e.line, e.strerror))
        # Print statement
        else:
            print "DEBUG_AST_CONFIG: Parse Error line: %s: %s" % (e.line, e.strerror)
        return retResult

    # Start access asterisk users.conf categories
    for category in usersCnfg.categories:
        if category.name != 'general':
            extType = ''
            extTypeStrt = False
            
            # Get the extension number
            extNumber = category.name
            # Start access asterisk users.conf item
            for item in category.items:
                # Get the extension full name
                if item.name == 'fullname':
                    extName = item.value
                    extNLen = len(extName)
                    # Get the extension type from the extension full name
                    for a in range(0, extNLen + 1):
                        oneChar = mid(extName, a, 1)
                        if oneChar == ' ' and extTypeStrt == False:
                            extTypeStrt = True
                        elif oneChar != ':' and extTypeStrt == True:
                            extType += oneChar
                        elif oneChar == ':' and extTypeStrt == True:
                            break
                # Exit loop, other than sip webrtc, no need to check others items
                elif extType != 'SIP WEBRTC':
                    break
                # Get extension secret or sip password                    
                elif item.name == 'secret':
                    extSecret = item.value
                    break
            # SIP WEBRTC extension 
            if extType == 'SIP WEBRTC' and typeUpdt == 'Webrtc':
                try:
                    # Update first data from existing python dictionary dummy data
                    if frstWRtcTypData == False:
                        extDB = [ extDBB for extDBB in webRtcContListData ]
                        extDB[0]['ext'] = extNumber

                        # Look location/full name info for this extension no.
                        if extnNumber == extNumber:
                            # Only take changes
                            if extDB[0]['fullname'] != extName:
                                # Return value
                                retExtNo = extNumber
                                retFullNme = extName
                        
                        extDB[0]['fullname'] = extName
                        extDB[0]['pswd'] = extSecret
                        
                        frstWRtcTypData = True
                    else:
                        # Check the extensions whether its already exist or not
                        extDB = [ extDBB for extDBB in webRtcContListData if (extDBB['ext'] == extNumber) ]
                        # Update the existing data, throw error if record is not exist, consider its a new data
                        # Look location/full name info for this extension no.
                        if extnNumber == extNumber:
                            # Only take changes
                            if extDB[0]['fullname'] != extName:
                                # Return value
                                retExtNo = extNumber
                                retFullNme = extName
                            
                        extDB[0]['fullname'] = extName
                        extDB[0]['pswd'] = extSecret
                                      
                # NEW contact list
                except:
                    # Construct the new data
                    newData = {
                                'ext':extNumber,
                                'fullname':extName,
                                'pswd':extSecret,
                                'ip':'NA',
                                'sip':'NA',
                                'avail' : 'NA'
                                }
                                          
                    # Append a NEW extension to the existing record
                    webRtcContListData.append(newData)    
            # Normal extension
            elif extType != 'FXO' and typeUpdt == 'Normal':
                # Update python contact list data
                try:
                    # Update first data from existing python dictionary dummy data
                    if frstNormTypData == False:
                        extDB = [ extDBB for extDBB in contactListData ]
                        extDB[0]['ext'] = extNumber

                        # Look location/full name info for this extension no.
                        if extnNumber == extNumber:
                            # Only take changes
                            if extDB[0]['fullname'] != extName:
                                # Return value
                                retExtNo = extNumber
                                retFullNme = extName
                                
                        extDB[0]['fullname'] = extName
                        extDB[0]['type'] = extType

                        frstNormTypData = True
                    else:
                        # Check the extensions whether its already exist or not
                        extDB = [ extDBB for extDBB in contactListData if (extDBB['ext'] == extNumber) ]
                        # Update the existing data, throw error if record is not exist, consider its a new data
                        # Look location/full name info for this extension no.
                        if extnNumber == extNumber:
                            # Only take changes
                            if extDB[0]['fullname'] != extName:
                                # Return value
                                retExtNo = extNumber
                                retFullNme = extName
                                
                        extDB[0]['fullname'] = extName
                        extDB[0]['type'] = extType
                
                # NEW contact list
                except:
                    # Construct the new data
                    newData = {
                                'ext':extNumber,
                                'fullname':extName,
                                'type':extType,
                                'ip':'NA'
                                }
                    
                    # Append a NEW extension to the existing record
                    contactListData.append(newData)
    getContactListFromSip(typeUpdt,frstNormTypData)
    try:
        # Create extension list xml file structure
        firstContactXml = False
        xmlTree = ''

        # Update XML file for normal extensions list
        if typeUpdt == 'Normal':
            xmlContactRoot = ET.Element('CONTACT')
            xmlContactItems = ET.SubElement(xmlContactRoot, 'INFO')

            # Start insert the python dictionary data to the xml file
            for extData in contactListData:
                if firstContactXml == False:
                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(xmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']
                    ET.SubElement(xmlContactItems, 'CALLID').text = extData['ext']
                    ET.SubElement(xmlContactItems, 'SERVERID').text = 'NA'
                    ET.SubElement(xmlContactItems, 'TYPE').text = extData['type']
                    
                    firstContactXml = True
                else:
                    secXmlContactItems = ET.SubElement(xmlContactRoot, 'INFO')

                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']
                    ET.SubElement(secXmlContactItems, 'CALLID').text = extData['ext']
                    ET.SubElement(secXmlContactItems, 'SERVERID').text = 'NA'
                    ET.SubElement(secXmlContactItems, 'TYPE').text = extData['type']
                    
            # Create the xml file
            # Arrange/prettify the xml structure
            indent(xmlContactRoot)
                    
            xmlTree = ET.ElementTree(xmlContactRoot)
            # Actual stored folder location
            if testxml == True:
                xmlTree.write("/var/www/html/listContact.xml")
            # Test stored folder location
            else:
                xmlTree.write("listContact.xml")

            retResult = True
        
        # Update XML file for SIP WebRTC extensions list
        else:
            xmlContactRoot = ET.Element('REGISTRAR')
            xmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')
            
            # Start insert the python dictionary data to the xml file
            for extData in webRtcContListData:
                if firstContactXml == False:
                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(xmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']

                    # Only update SIP WebRTC availability list to a new value, if previously the setting already take place
                    if extData['avail'] != 'NA':
                        ET.SubElement(xmlContactItems, 'AVAIL').text = extData['avail']
                    else:
                        ET.SubElement(xmlContactItems, 'AVAIL').text = 'NA'
                        
                    ET.SubElement(xmlContactItems, 'USERNAME').text = extData['ext']

                    # Only update SIP address to a new value, if previously the setting already take place
                    if extData['sip'] != 'NA':
                        ET.SubElement(xmlContactItems, 'SIPADDR').text = extData['sip']
                    else:
                        ET.SubElement(xmlContactItems, 'SIPADDR').text = 'NA'

                    ET.SubElement(xmlContactItems, 'PSWD').text = extData['pswd']
                    
                    firstContactXml = True
                else:
                    secXmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')

                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']

                    # Only update SIP WebRTC availability list to a new value, if previously the setting already take place
                    if extData['avail'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'AVAIL').text = extData['avail']
                    else:
                        ET.SubElement(secXmlContactItems, 'AVAIL').text = 'NA'
                    
                    ET.SubElement(secXmlContactItems, 'USERNAME').text = extData['ext']

                    # Only update SIP address to a new value, if previously the setting already take place
                    if extData['sip'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'SIPADDR').text = extData['sip']
                    else:
                        ET.SubElement(secXmlContactItems, 'SIPADDR').text = 'NA'
                        
                    ET.SubElement(secXmlContactItems, 'PSWD').text = extData['pswd']
                    
            # Create the xml file
            # Arrange/prettify the xml structure
            indent(xmlContactRoot)
            
            xmlTree = ET.ElementTree(xmlContactRoot)
            # Actual stored folder location
            if testxml == True:
                xmlTree.write("/var/www/html/registrarlist.xml")
            # Test stored folder location
            else:
                xmlTree.write("registrarlist.xml")
            retResult = True
    except:
        # Write to logger
        if backLogger == True:
            logger.info("DEBUG_AST_CONFIG: Create xml config file failed!")
        # Print statement
        else:
            print "DEBUG_AST_CONFIG: Create xml config file failed!"
        return retResult

    return retResult, retExtNo, retFullNme
    
# Handle Cross-Origin (CORS) problem upon client request
@app.after_request
def add_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')

    return response

# Delete recording file based on given file name
# To delete and refresh recording xml file:
# http://192.168.1.1:8000/deleterecords/Recording/2021-11-05-1143-6013-6000.ogg
@app.route('/deleterecords/<statustype>/<filedetail>', methods=['GET'])
def deleteRecData(statustype, filedetail):
    retResult = False
    fileToDelete = ''
    tempArgs = ''
    updtType = ''
    
    try:
        updtLst = [ updtLstT for updtLstT in listUpdtData if (updtLstT['type'] == statustype) ]
        updtType = updtLst[0]['type']
        if updtType == 'Recording':
            # Copy file detail name to the variable
            fileToDelete = '/var/www/html/recordings/' + filedetail

            # Start delete the recording file
            tempArgs = 'rm -r ' + fileToDelete 
            out = subprocess.Popen([tempArgs], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout,stderr = out.communicate()
            # NO error after command execution
            if stderr == None:
                # Write to logger
                if backLogger == True:
                    logger.info("DEBUG_DELETE_RECORD: Delete File: %s SUCCESFULL" % (filedetail))
                # Print statement
                else:
                    print "DEBUG_DELETE_RECORD: Delete File: %s SUCCESFULL" % (filedetail)

                # Update back XML file with the new recording file contents
                getRecordFile()
                # Update return status sucessfull
                updtLst[0]['status'] = 'SUCCESFULL'
            else: 
                # Write to logger
                if backLogger == True:
                    logger.info("DEBUG_DELETE_RECORD: Delete File: %s FAILED!" % (filedetail))
                # Print statement
                else:
                    print "DEBUG_DELETE_RECORD: Delete File: %s FAILED!" % (filedetail)
                    
                # Update return status failed!
                updtLst[0]['status'] = 'FAILED'
    except:
        return jsonify({'UpdatedStatusInfo' : updateFailed})
    return jsonify({'UpdatedStatusInfo' : updtLst})
    
# Get updated recording file list after request process
# Example command to send:
# To update and refresh intercom xml file:
# http://192.168.1.1:8000/updatedrecordlist/Recording
# extNo - Always be dummy
@app.route('/updatedrecordlist/<statustype>', methods=['GET'])
def updatedRecList(statustype):
    retResult = False
    updtType = ''
    
    try:
        updtLst = [ updtLstT for updtLstT in listUpdtData if (updtLstT['type'] == statustype) ]
        updtType = updtLst[0]['type']
        if updtType == 'Recording':
            # Get current list of the call audio file 
            retResult = getRecordFile()
            if retResult == True:
                # Update return status sucessfull
                updtLst[0]['status'] = 'SUCCESFULL'
            else:
                # Update return status failed!
                updtLst[0]['status'] = 'FAILED'
    except:
        return jsonify({'UpdatedStatusInfo' : updateFailed})
    return jsonify({'UpdatedStatusInfo' : updtLst})
    
# Get intercom updated list status after request
# Example command to send:
# To update and refresh intercom xml file:
# http://192.168.1.1:8000/updatedicomlist/Intercomm/dummy
# extNo - Always be dummy
@app.route('/updatedicomlist/<statustype>/<extNo>', methods=['GET'])
def updatedIComList(statustype, extNo):
    retResult = False
    updtType = ''
    retExtNo = ''
    retFullNme = ''
		
    try:
        updtLst = [ updtLstT for updtLstT in listUpdtData if (updtLstT['type'] == statustype) ]
        updtType = updtLst[0]['type']
        if updtType == 'Intercomm':
            # Get updated intercomm list
            retResult, retExtNo, retFullNme = getIntercomList(extNo, updtType)
            # Update successful
            if retResult == True:
                # Update return status succesfull
                if retExtNo != '':
                    updtLst[0]['ext'] = retExtNo
                else:
                    updtLst[0]['ext'] = 'NA'

                if retFullNme != '':
                    updtLst[0]['fullname'] = retFullNme
                else:
                    updtLst[0]['fullname'] = 'NA'
                
                # Update return status sucessfull
                updtLst[0]['status'] = 'SUCCESFULL'
            else:
                # Update return status failed!
                updtLst[0]['status'] = 'FAILED'
    except:
        return jsonify({'UpdatedStatusInfo' : updateFailed})
    return jsonify({'UpdatedStatusInfo' : updtLst})
		
# Get updated list (contact or registrar list) status after request
# Example command to send:
# http://192.168.1.1:8000/updatedlist/Normal
# To update and refresh contact list xml file:
# http://192.168.1.1:8000/updatedlist/Normal/dummy
@app.route('/updatedlist/<statustype>/<extNo>', methods=['GET'])
def updatedList(statustype, extNo):
    retResult = False
    updtType = ''
    retExtNo = ''
    retFullNme = ''
    
    try:
        updtLst = [ updtLstT for updtLstT in listUpdtData if (updtLstT['type'] == statustype) ]
        updtType = updtLst[0]['type']
        if updtType == 'Normal' or updtType == 'Webrtc': 
            # Update contacts/extensions list
            retResult, retExtNo, retFullNme = getContactList(extNo, updtType)
            # Update successful
            if retResult == True:
                # Update return status succesfull
                if retExtNo != '':
                    updtLst[0]['ext'] = retExtNo
                else:
                    updtLst[0]['ext'] = 'NA'

                if retFullNme != '':
                    updtLst[0]['fullname'] = retFullNme
                else:
                    updtLst[0]['fullname'] = 'NA'

                updtLst[0]['status'] = 'SUCCESFULL'
            else:
                # Update return status succesfull
                updtLst[0]['status'] = 'FAILED'
    except:
        return jsonify({'UpdatedStatusInfo' : updateFailed})
    return jsonify({'UpdatedStatusInfo' : updtLst})

# Update normal extensions/contacts list
# Example command to send:
# curl -i -H "Content-type: application/json" -X PUT -d "{\"ip\":\"192.168.1.1\"}" http://192.168.1.1:8000/ext/6004
@app.route('/ext/<extNo>', methods=['PUT'])
def updateExtData(extNo):
    try:
        # Initialize data dictionary
        extNum = [ extNumM for extNumM in contactListData if (extNumM['ext'] == extNo) ]
        # Update extensons IP address
        if 'ip' in request.json:
            extNum[0]['ip'] = request.json['ip']

            # Create normal extension list xml file structure - listContact.xml
            firstContactXml = False
            xmlTree = ''
            
            xmlContactRoot = ET.Element('CONTACT')
            xmlContactItems = ET.SubElement(xmlContactRoot, 'INFO')

            # Start insert the python dictionary data to the xml file
            for extData in contactListData:
                if firstContactXml == False:
                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(xmlContactItems, 'IPADDR').text = 'NA'

                    ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']
                    ET.SubElement(xmlContactItems, 'CALLID').text = extData['ext']
                    ET.SubElement(xmlContactItems, 'SERVERID').text = 'NA'
                    ET.SubElement(xmlContactItems, 'TYPE').text = extData['type']
                    
                    firstContactXml = True
                else:
                    secXmlContactItems = ET.SubElement(xmlContactRoot, 'INFO')

                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']
                    ET.SubElement(secXmlContactItems, 'CALLID').text = extData['ext']
                    ET.SubElement(secXmlContactItems, 'SERVERID').text = 'NA'
                    ET.SubElement(secXmlContactItems, 'TYPE').text = extData['type']    

                # Create the xml file
                # Arrange/prettify the xml structure
                indent(xmlContactRoot)
                
                xmlTree = ET.ElementTree(xmlContactRoot)
                # Actual stored folder location
                if testxml == True:
                    xmlTree.write("/var/www/html/listContact.xml")
                # Test stored folder location
                else:
                    xmlTree.write("listContact.xml")
                    
        return jsonify({'UpdatedExtInfo' : extNum})        
    except:
        return jsonify({'UpdatedStatusInfo' : updateFailed})
    
# Update webrtc extensions/contacts list - IP address and SIP WebRTC availability list
# Example command to send:
# curl -i -H "Content-type: application/json" -X PUT -d "{\"ip\":\"192.168.1.1\"}" http://192.168.1.1:8000/webrtc/6004
# curl -i -H "Content-type: application/json" -X PUT -d "{\"avail\":\"OCCUPIED\"}" http://192.168.1.1:8000/webrtc/6004
# curl -i -H "Content-type: application/json" -X PUT -d "{\"avail\":\"DUMMY\"}" http://192.168.1.1:8000/webrtc/6004
@app.route('/webrtc/<extNo>', methods=['PUT'])
def updateWebRtcData(extNo):
    try:
        # Initialize data dictionary
        webRtc = [ webRtcC for webRtcC in webRtcContListData if (webRtcC['ext'] == extNo) ]
        # Update webrtc ip address
        if 'ip' in request.json:
            webRtc[0]['ip'] = request.json['ip']
            webRtc[0]['sip'] = 'sip:' + webRtc[0]['ext'] + '@' + request.json['ip']

            # Create webrtc extension list xml file structure - registrarlist.xml
            firstContactXml = False
            xmlTree = ''
            
            xmlContactRoot = ET.Element('REGISTRAR')
            xmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')
            
            # Start insert the python dictionary data to the xml file
            for extData in webRtcContListData:
                if firstContactXml == False:
                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(xmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']
                    ET.SubElement(xmlContactItems, 'AVAIL').text = extData['avail']
                    ET.SubElement(xmlContactItems, 'USERNAME').text = extData['ext']

                    # Only update SIP address to a new value, if previously the setting already take place
                    if extData['sip'] != 'NA':
                        ET.SubElement(xmlContactItems, 'SIPADDR').text = extData['sip']
                    else:
                        ET.SubElement(xmlContactItems, 'SIPADDR').text = 'NA'
                        
                    ET.SubElement(xmlContactItems, 'PSWD').text = extData['pswd']
                    
                    firstContactXml = True
                else:
                    secXmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')

                    # Only update IP address to a new value, if previously the setting already take place
                    if extData['ip'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                    else:
                        ET.SubElement(secXmlContactItems, 'IPADDR').text = 'NA'
                        
                    ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']
                    ET.SubElement(secXmlContactItems, 'AVAIL').text = extData['avail']
                    ET.SubElement(secXmlContactItems, 'USERNAME').text = extData['ext']

                    # Only update SIP address to a new value, if previously the setting already take place
                    if extData['sip'] != 'NA':
                        ET.SubElement(secXmlContactItems, 'SIPADDR').text = extData['sip']
                    else:
                        ET.SubElement(secXmlContactItems, 'SIPADDR').text = 'NA'
                        
                    ET.SubElement(secXmlContactItems, 'PSWD').text = extData['pswd']

            # Create the xml file
            # Arrange/prettify the xml structure
            indent(xmlContactRoot)
            
            xmlTree = ET.ElementTree(xmlContactRoot)
            # Actual stored folder location
            if testxml == True:
                xmlTree.write("/var/www/html/registrarlist.xml")
            # Test stored folder location
            else:
                xmlTree.write("registrarlist.xml")

        # Update SIP WebRTC availability list
        elif 'avail' in request.json:
            checkTyp = request.json['avail']

            # Normal SIP WebRTC account availability update 
            if checkTyp != "DUMMY":
                # Update for availability: AVAILABLE or OCCUPIED
                webRtc[0]['avail'] = request.json['avail']
                
                # Create webrtc extension list xml file structure - registrarlist.xml
                firstContactXml = False
                xmlTree = ''
                
                xmlContactRoot = ET.Element('REGISTRAR')
                xmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')

                # Start insert the python dictionary data to the xml file
                for extData in webRtcContListData:
                    if firstContactXml == False:
                        ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                        ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']

                        # Only update SIP WebRTC list to a new value, if previously the setting already take place
                        if extData['avail'] != 'NA':
                            ET.SubElement(xmlContactItems, 'AVAIL').text = extData['avail']
                        else:
                            ET.SubElement(xmlContactItems, 'AVAIL').text = 'NA'
                        
                        ET.SubElement(xmlContactItems, 'USERNAME').text = extData['ext']
                        ET.SubElement(xmlContactItems, 'SIPADDR').text = extData['sip']
                        ET.SubElement(xmlContactItems, 'PSWD').text = extData['pswd']
                        
                        firstContactXml = True
                    else:
                        secXmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')

                        ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                        ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']

                        # Only update SIP WebRTC list to a new value, if previously the setting already take place
                        if extData['avail'] != 'NA':
                            ET.SubElement(secXmlContactItems, 'AVAIL').text = extData['avail']
                        else:
                            ET.SubElement(secXmlContactItems, 'AVAIL').text = 'NA'
                        
                        ET.SubElement(secXmlContactItems, 'USERNAME').text = extData['ext']
                        ET.SubElement(secXmlContactItems, 'SIPADDR').text = extData['sip']
                        ET.SubElement(secXmlContactItems, 'PSWD').text = extData['pswd']
                        
                # Create the xml file
                # Arrange/prettify the xml structure
                indent(xmlContactRoot)
                
                xmlTree = ET.ElementTree(xmlContactRoot)
                
                # Actual stored folder location
                if testxml == True:
                    xmlTree.write("/var/www/html/registrarlist.xml")
                # Test stored folder location
                else:
                    xmlTree.write("registrarlist.xml")

            # Reset previous SIP WebRTC account availability 
            else:
                # Reset all necessary parameter
                webRtc[0]['avail'] = 'NA'
                webRtc[0]['ip'] = 'NA'
                webRtc[0]['sip'] = 'NA'

                # Create webrtc extension list xml file structure - registrarlist.xml
                firstContactXml = False
                xmlTree = ''
                
                xmlContactRoot = ET.Element('REGISTRAR')
                xmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')

                # Start insert the python dictionary data to the xml file
                for extData in webRtcContListData:
                    if firstContactXml == False:
                        ET.SubElement(xmlContactItems, 'IPADDR').text = extData['ip']
                        ET.SubElement(xmlContactItems, 'LOCATION').text = extData['fullname']
                        ET.SubElement(xmlContactItems, 'AVAIL').text = extData['avail']
                        ET.SubElement(xmlContactItems, 'USERNAME').text = extData['ext']
                        ET.SubElement(xmlContactItems, 'SIPADDR').text = extData['sip']
                        ET.SubElement(xmlContactItems, 'PSWD').text = extData['pswd']
                        
                        firstContactXml = True
                    else:
                        secXmlContactItems = ET.SubElement(xmlContactRoot, 'SERVER')

                        ET.SubElement(secXmlContactItems, 'IPADDR').text = extData['ip']
                        ET.SubElement(secXmlContactItems, 'LOCATION').text = extData['fullname']
                        ET.SubElement(secXmlContactItems, 'AVAIL').text = extData['avail']
                        ET.SubElement(secXmlContactItems, 'USERNAME').text = extData['ext']
                        ET.SubElement(secXmlContactItems, 'SIPADDR').text = extData['sip']
                        ET.SubElement(secXmlContactItems, 'PSWD').text = extData['pswd']
                        
                # Create the xml file
                # Arrange/prettify the xml structure
                indent(xmlContactRoot)
                
                xmlTree = ET.ElementTree(xmlContactRoot)
                
                # Actual stored folder location
                if testxml == True:
                    xmlTree.write("/var/www/html/registrarlist.xml")
                # Test stored folder location
                else:
                    xmlTree.write("registrarlist.xml")

    except:
        return jsonify({'UpdatedStatusInfo' : updateFailed})    
    return jsonify({'UpdatedWebRtcInfo' : webRtc})

# Get current CALL status after termination
# Example command to send:
# http://192.168.1.1:8000/channelinfo
@app.route('/callinfo', methods=['GET'])
def getCallInfoDb():
    return jsonify({'CallStatusInfo' : hangupData})

# Terminate a dispatch call based on the given channel
# Example command to send:
# curl -i -H "Content-type: application/json" -X PUT -d "{\"callchannel\":\"1001\"}" http://192.168.1.1:8000/terminatecall/000
@app.route('/terminatecall/<hgUpId>', methods=['PUT'])
def terminateGivenCall(hgUpId):
    # Initialize data dictionary
    hgup = [ hgupP for hgupP in hangupData if (hgupP['id'] == hgUpId) ]
    
    # Terminate the given call dispatch channel
    if 'callchannel' in request.json:
        # Update call channel data
        hgup[0]['callchannel'] = request.json['callchannel']
        # Retrieve call channel to terminate
        terminateChan = hgup[0]['callchannel']

        # Write to logger
        if backLogger == True:
            logger.info("DEBUG_TERMINATE_STATUS: Request Channel: %s" % (terminateChan))
        # Print statement
        else:
            print "DEBUG_TERMINATE_STATUS: Request Channel: %s" % (terminateChan)
        
        # Execute asterisk command via linux terminal
        # Sample reply:
        # SIP/1002-0000007b!myphones!!1!Up!AppDial!(Outgoing Line)!1002!!!3!196!0377ef02-fcb0-490a-8231-53ed81fa9d4a!1580297330.202
        # SIP/1001-0000007a!myphones!1002!1!Up!Dial!SIP/1002!1003!!!3!196!0377ef02-fcb0-490a-8231-53ed81fa9d4a!1580297330.200
        # Message/ast_msg_queue!mychatmessages!1000!9!Up!Hangup!!!!!3!33754!!1580263771.180
        out = subprocess.Popen(['asterisk', '-rx', 'core show channels concise'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()

        # Write to logger
        if backLogger == True:
            logger.info("DEBUG_TERMINATE_STATUS: Connected Channel List: %s" % (stdout))
        # Print statement
        else:
            print "DEBUG_TERMINATE_STATUS: Connected Channel List: %s" % (stdout)
                    
        # NO error during asterisk command execution
        if stderr == None:
            getChan = False
            fullChan = ''
            chan = stdout
            # Check request call channel for termination existence
            terminateChan = 'SIP/' + terminateChan 
            # Dispatch call channel exist
            if terminateChan in chan:
                # Write to logger
                if backLogger == True:
                    logger.info("DEBUG_TERMINATE_STATUS: Call Channel [%s] exist" % (terminateChan))
                 # Print statement
                else:   
                    print "DEBUG_TERMINATE_STATUS: Call Channel [%s] exist" % (terminateChan)
                    
                # Get FULL dispatch channel info to be terminated
                chanIdLen = len(chan)
                for b in range(0, chanIdLen + 1):
                    oneChar = mid(chan, b, 1)
                    # Indicate there is a dispatch call channel connected
                    if oneChar == '/' and getChan == False:
                        getChan = True
                    # Retrieve full channel name
                    elif getChan == True and oneChar != '!':
                        fullChan += oneChar
                    # End of full channel name
                    elif getChan == True and oneChar == '!':
                        # Check call channel format, MUST has '-' sign
                        if '-' in fullChan:
                            fullChan = 'SIP/' + fullChan

                            # Write to logger
                            if backLogger == True:
                                logger.info("DEBUG_TERMINATE_STATUS: Full Call Channel Name: %s" % (fullChan))
                            # Print statement
                            else:       
                                print "DEBUG_TERMINATE_STATUS: Full Call Channel Name: %s" % (fullChan)
                                
                            # Check against request channel name
                            if terminateChan in fullChan:
                                fullChan = 'channel request hangup ' + fullChan
                                out = subprocess.Popen(['asterisk', '-rx', fullChan], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                                stdout,stderr = out.communicate()

                                # Write to logger
                                if backLogger == True:
                                    logger.info("DEBUG_TERMINATE_STATUS: Terminated Channel Message: %s" % (stdout))
                                # Print statement
                                else:
                                    print "DEBUG_TERMINATE_STATUS: Terminated Channel Message: %s" % (stdout)
                                    
                                if stderr == None:
                                    # Write to logger
                                    if backLogger == True:
                                        logger.info("DEBUG_TERMINATE_STATUS: Terminate Dispatch Call Channel Successful")
                                    # Print statement
                                    else:
                                        print "DEBUG_TERMINATE_STATUS: Terminate Dispatch Call Channel Successful"
                                        
                                    # Update call channel data
                                    hgup[0]['status'] = 'TERMINATED' 
                                    break
                                else:
                                    # Write to logger
                                    if backLogger == True:
                                        logger.info("DEBUG_TERMINATE_STATUS: Terminate Dispatch Call Channel Failed!")
                                    # Print statement
                                    else:
                                        print "DEBUG_TERMINATE_STATUS: Terminate Dispatch Call Channel Failed!"

                                    # Update call channel data
                                    hgup[0]['status'] = 'ERROR' 
                                    break
                            else:
                                fullChan = ''
                        getChan = False
            # Dispatch call channel NOT exist    
            else:
                # Write to logger
                if backLogger == True:
                    logger.info("DEBUG_TERMINATE_STATUS: Dispatch Call Channel NOT Exist!")
                # Print statement
                else:
                    print "DEBUG_TERMINATE_STATUS: Dispatch Call Channel NOT Exist!"
                    
                # Update call channel data
                hgup[0]['status'] = 'ERROR'
        # Error during asterisk command execution 
        else:
            # Write to logger
            if backLogger == True:
                logger.info("DEBUG_TERMINATE_STATUS: Error: %s" % (stderr))
                logger.info("DEBUG_TERMINATE_STATUS: Error during asterisk command execution")    
            # Print statement
            else:
                print "DEBUG_TERMINATE_STATUS: Error: %s" % (stderr)
                print "DEBUG_TERMINATE_STATUS: Error during asterisk command execution"
                     
            # Update call channel data
            hgup[0]['status'] = 'ERROR'
            
    return jsonify({'CallStatusInfo': hgup}) 

#Thread to delete audio recording file
def deleteRecordingFile (threadname, delay):
    global fileNeedToDelete
    global fileToDeleteCnt   
    global deleteProc
    
    fileToDelete = ''
    
    # Forever loop
    while True:
        # Loop every 0.5s
        time.sleep(delay)
        
        # Previously there is a request to delete maximum audio recording file
        if deleteProc == True:
            # Loop through the audio recording file delete buffer
            for a in range(fileToDeleteCnt):
                # Copy file detail name to the variable
                fileToDelete = '/var/www/html/recordings/' + fileNeedToDelete[a]

                # Start delete the recording file
                tempArgs = 'rm -r ' + fileToDelete 
                out = subprocess.Popen([tempArgs], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stdout,stderr = out.communicate()
                # NO error after command execution
                if stderr == None:
                    # Write to logger
                    if backLogger == True:
                        logger.info("DEBUG_THD_REC_DELETE: Delete File: %s SUCCESFUL" % (fileNeedToDelete[a]))
                    # Print statement
                    else:
                        print "DEBUG_THD_REC_DELETE: Delete File: %s SUCCESFUL" % (fileNeedToDelete[a])

                # Error during command execution        
                else:
                    # Write to logger
                    if backLogger == True:
                        logger.info("DEBUG_THD_REC_DELETE: Delete File: %s FAILED!" % (fileNeedToDelete[a]))
                    # Print statement
                    else:
                        print "DEBUG_THD_REC_DELETE: Delete File: %s FAILED!" % (fileNeedToDelete[a])
                        
            # Empty delete buffer
            fileNeedToDelete = []
            # Reset buffer index counter
            fileToDeleteCnt = 0
            # Reset back recording flag
            deleteProc = False
            
            # Write to logger
            if backLogger == True:
                logger.info("DEBUG_THD_REC_DELETE: Delete File: FINISHED")
            # Print statement
            else:
                print "DEBUG_THD_REC_DELETE: Delete File: FINISHED" 
            
# Main daemon entry point             
def main():
    # Create thread to check PING signal from server
    try:
        thread.start_new_thread(deleteRecordingFile, ("Create delete recording file thread", 5, ))
    except:
        # Write to logger
        if backLogger == True:
            # log events, when daemon run in background
            logger.info("DEBUG_THD_REC_DELETE: Error: unable to start delete recording file thread")
        # Print statement
        else:
            print "DEBUG_THD_REC_DELETE: Error: unable to start delete recording file thread"
            
    # Get current and latest call audio file 
    getRecordFile()
    
    # Write to logger
    if backLogger == True:
        logger.info("DEBUG_REST_API: RestFul API web server STARTED")
    # Print statement
    else:
        print "DEBUG_REST_API: RestFul API web server STARTED"
    if __name__ == "__main__":
        if secureInSecure == True:
            # RUN RestFul API web server
            # Add a certificate to make sure REST web API can support HTTPS request
            # Generate first cert.pem (new certificate) and key.pem (new key) by initiate below command:
            # openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
            #app.run(host='0.0.0.0', port=8000, ssl_context=('cert.pem', 'key.pem'))
            #app.run(host='0.0.0.0', port=8000, ssl_context=('asterisk.pem', 'ca.key'))
            app.run(host='masuri.scs.my', port=8000, ssl_context=('fullchain.pem', 'ca.key'))
            #app.run(host='mabvoip.scs.my', port=8000, ssl_context=('asterisk.pem', 'key.pem'))
        # Insecure web server (HTTP) - Default port 5000
        else:
            app.run(host='0.0.0.0', port=8000)
main()
