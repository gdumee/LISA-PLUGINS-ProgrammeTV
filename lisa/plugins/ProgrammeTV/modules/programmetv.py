# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa plugins
# module      : ProgrammeTV
# file        : programmetv.py
# description : Give tu programming
# author      : G AUDET
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------

# TODO :



#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
#mandatory
from lisa.server.plugins.IPlugin import IPlugin
import gettext
import inspect
import os, sys

#optionnal
import urllib
import xml.etree.ElementTree as ET
#import datetime
from datetime import datetime
from datetime import time
from datetime import date

from lisa.Neotique.NeoTrans import NeoTrans
from lisa.Neotique.NeoConv import NeoConv

#-----------------------------------------------------------------------------
# Plugin Meteo class
#-----------------------------------------------------------------------------
class ProgrammeTV(IPlugin):
    """
    Plugin main class
    """
    def __init__(self):
        super(ProgrammeTV, self).__init__()
        self.configuration_plugin = self.mongo.lisa.plugins.find_one({"name": "ProgrammeTV"})
        self.path = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile(inspect.currentframe()))[0],os.path.normpath("../lang/"))))
        self._ = NeoTrans(domain='programmetv',localedir=self.path,fallback=True,languages=[self.configuration_lisa['lang']], test = __name__).Trans
        
        self.WITDate = NeoConv(self._, test = __name__).WITDate
        self.time2str = NeoConv(self._, test = __name__).time2str
    
    
    #-----------------------------------------------------------------------------
    #              Publics  Fonctions
    #-----------------------------------------------------------------------------   
    def getProgrammeTV(self, jsonInput):
        
        #print 'json                     ',jsonInput
        
        #init
        rep = os.path.dirname(os.path.abspath(__file__)) + '/tmp/'+str(date.today())+'_programmetv.xml'
        #print rep
        self.downloadProgrammeTV(rep)
        if __name__ == "__main__" :print 'debut lecture xml ',datetime.now().time()
        #programmetv = ET.parse('tmp/'+str(date.today())+'_programmetv.xml').getroot()
        programmetv = ET.parse(rep).getroot()
        if __name__ == "__main__" : print 'fin lecture',datetime.now().time()
        
        
        #config date
        #dDate = {'end': datetime.time(20,50), 'begin': datetime.time(12,00), 'date': datetime.date(2014, 7, 18), 'part': 'afternoon', 'delta': 1, 'day' : 'Mon', 'Month':'July'}
        dDate = self.WITDate(jsonInput)
        if dDate['delta'] > 7 :
            return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": self._("not yet")}                         #fatal
        #special case for evening
        if dDate['part'] == 'alltheday' or \
            (dDate['begin'] == time(18,00) and  dDate['end'] == time(00,00)):  
            #by default, get TV for the evening
            dDate['begin'] = time(21,00)
            dDate['end'] = time(21,10)
            dDate['part'] = 'evening'
        #special case for other part of the day
        
        #if __name__ == "__main__" : print dDate

        
        #config channel
        #list all channel in programmetv
        channelDict = {}
        for child in programmetv:
            if child.tag == "channel":
                channelDict[child.attrib['id']] = child.find('display-name').text.lower()
            if child.tag == "programme":
                break
        #check if requested channel exist
        namchannel='all' #by default get tv for all channel
        if jsonInput['outcome']['entities'].has_key('location') == True:
            for channel in channelDict :
                print channelDict[channel]
                if ((jsonInput['outcome']['entities']['location']['value']).lower()) == channelDict[channel]:
                    namchannel = channelDict[channel]  #requested channel is in the xml
                    break
            #not found requested channel
            if namchannel == 'all' : 
                return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": self._("dont know this channel")}          #fatal
            
        
        #look for request date/channel
        programmetv_str = ""
        actualchannel = ""
        firstchannel = True
        future=''
        if dDate['delta'] > 0 : future = '-future' #speak with verb on future
        for child in programmetv.findall('programme'):    
            if (channelDict[child.attrib['channel']] == namchannel) or (namchannel == 'all') :  #check for request channel or all channel                    
                if child.attrib['start'][:8] == dDate['date'].strftime("%Y%m%d")  : #check for request date
                    if (child.attrib['start'][8:12] >= dDate['begin'].strftime("%H%M") and child.attrib['start'][8:12] <= dDate['end'].strftime("%H%M")) or \
                        (child.attrib['start'][8:12] < dDate['begin'].strftime("%H%M") and child.attrib['stop'][8:12] > dDate['begin'].strftime("%H%M")):#check for request time
                        #build return message
                        try :
                            title = child.find('title').text  #.encode('utf8')
                        except:
                            print 'Erreur de decodage        ',child.find('title').text
                        tim = self.time2str(child.attrib['start'][8:10]+':'+child.attrib['start'][10:12],pMinutes=0)
                        if channelDict[child.attrib['channel']] <> actualchannel :  #new channel in the list
                            if firstchannel == True :   #add . at the end of channel list. Except for the first channel
                                firstchannel = False
                            else :
                                programmetv_str += '. '
                            actualchannel = channelDict[child.attrib['channel']]
                            programmetv_str += self._('prog1{0}'.format(future)).format(channel = channelDict[child.attrib['channel']],time =tim, title =title)
                        else : #actual channel
                            programmetv_str += self._('prog2{0}'.format(future)).format(time =tim, title = title)

        
        
        #build return message
        if dDate['delta'] == 0 :
            message = self._('today-msg').format (part=self._(dDate['part']))
        elif dDate['delta'] == 1 :
            message = self._('tomorrow-msg').format(day = self._('tomorrow'), part= self._(dDate['part']).encode('utf_'))
        elif dDate['delta'] == 2 :
            message = self._('after tomorrow-msg').format(day = self._('after tomorrow'), part= self._(dDate['part']).encode('utf_'))
        elif dDate['delta'] >2 :
            d =dDate['date'].strftime('%d')
            if d[0:1] == "0":
                d=d[1:2]
            message = self._("further day-msg").format(date = d, month=self._(dDate['month']),day=self._(dDate['day']),part=self._(dDate['part']))
        
        message += programmetv_str +'.'
        
        return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": message}

    #-----------------------------------------------------------------------------
    def downloadProgrammeTV(self,rep):
        
        url = "http://www.kazer.org/tvguide.xml?u=" + self.configuration_plugin['configuration']['user_id']
        if not os.path.isfile(rep) :
            print self._("Downloading tv program")
            if __name__ == "__main__" :print 'debut telechargement',datetime.now().time()
            urllib.urlretrieve(url,rep)         #write file
            if __name__ == "__main__" :print 'debut telechargement',datetime.now().time()
            self.extractProgrammeTV(rep)

        
        return "SUCCESS"
        """
        url = "http://www.kazer.org/tvguide.xml?u=" + self.configuration_plugin['configuration']['user_id']
        if not os.path.exists('tmp/'+str(date.today())+'_programmetv.xml'):
            print self._("Downloading the tv program")
            import glob
            files=glob.glob('tmp/*_programmetv.xml')
            print 'files                         ',files
            for filename in files:
                print 'filename                         ',filename
                os.unlink(filename)
            urllib.urlretrieve(url,'tmp/'+str(date.today())+'_programmetv.xml')
        
        return "SUCCESS"
        """ 
    #-----------------------------------------------------------------------------    
    def extractProgrammeTV(self,rep) :
        """
        extrait les info utile de l xml et le reengisgre
        """
        print self._("creating tv program")
        if __name__ == "__main__" :print 'debut creation prog TV' ,datetime.now().time()
        programmetv_tree = ET.parse(rep)
        programmetv_root = programmetv_tree.getroot()
        for el in ['sub-title','episode-num','desc','credits','date','category','length','video','audio','star-rating'] :
            for el2 in programmetv_root.findall('programme'):
                try :
                    el3 = el2.find(el)
                    el2.remove(el3)
                except :
                    pass
        programmetv_tree.write(rep)   
        #programmetv_tree.write('tmp/'+str(date.today())+'_programmetv.xml')   
        if __name__ == "__main__" :print 'fin creation prog TV' ,datetime.now().time()    
        return "SUCCESS"
        """
        for dat in range (0,4) :
            print 'generation du xml pour la date du',(dDate['date']+timedelta(days=dat)).strftime("%Y%m%d")
            programmetv_tree = ET.parse('tmp/'+str(date.today())+'_programmetv.xml')
            programmetv_root = programmetv_tree.getroot()
            for child in programmetv_root.findall('programme'):
                if child.attrib['start'][:8] == ((dDate['date']+timedelta(days=dat)).strftime("%Y%m%d"))  : #check for date
                    #print child.attrib['start'][:8]
                    for el in ['sub-title','episode-num','desc','credits','date','category','length','video','audio','star-rating'] :
                        #print child.find('title').text
                        try :
                            el2 = child.find(el)
                            child.remove(el2)
                        except :
                            pass
                else :
                    programmetv_root.remove(child)
                
            programmetv_tree.write('tmp/output'+str((dDate['date']+timedelta(days=dat)).strftime("%Y-%m-%d"))+'.xml')
        """     
        

        

#-----------------------------------------------------------------------------
# Tests
#-----------------------------------------------------------------------------
if __name__ == "__main__" :
    jsonInput = {'from': u'Lisa-Web', 'zone': u'WebSocket', u'msg_id': u'2dba9333-a9f3-435c-bdca-c3beba73a633', 
    'lisaprotocol': '<lisa.server.libs.server.Lisa instance at 0x7f55f01dc128>', 
    u'msg_body': u'quel est le programme TV demain \xe0 21 heure sur France 4', 
    u'outcome': {
        u'entities': {
        u'datetime': {u'body': u'demain \xe0 21 heure', u'start': 25, u'end': 42, u'value': {u'to': u'2014-07-20T00:00:00.000+02:00', u'from': u'2014-07-19T18:00:00.000+02:00'}} 

        }, 
        u'confidence': 0.987, 
        u'intent': u'programmetv_getprogrammetv'
    }, 
    'type': u'chat'}
    #u'location': {u'body': u'France 4', u'start': 47, u'end': 55, u'suggested': True, u'value': u'France 4'},
    #u'datetime': {u'body': u'demain \xe0 21 heure', u'start': 25, u'end': 42, u'value': {u'to': u'2014-07-17T22:00:00.000+02:00', u'from': u'2014-07-17T21:00:00.000+02:00'}} 
    essai = ProgrammeTV()
    retourn = essai.getProgrammeTV(jsonInput)
    print (retourn['body'])
