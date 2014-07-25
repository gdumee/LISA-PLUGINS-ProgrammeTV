# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa plugins
# module      : ProgrammeTV
# file        : programmetv.py
# description : Give TV programming with http://www.kazer.org/
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
from lisa.Neotique.NeoTrans import NeoTrans

#optionnal
import urllib
import xml.etree.ElementTree as ET
#import datetime
from datetime import datetime
from datetime import time
from datetime import date
from datetime import timedelta


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
        """
        get TV show on a specific/all channel
        """
        #print 'json                     ',jsonInput
        
        #init
        rep = os.path.dirname(os.path.abspath(__file__)) + '/tmp/'+str(date.today())+'_programmetv.xml'
        self._downloadProgrammeTV(rep)
        if __name__ == "__main__" : print "début lecture fichier xml"; t1= datetime.now()
        programmetv = ET.parse(rep).getroot()
        if __name__ == "__main__" : print '         durée lecture fichier xml',(datetime.now()-t1)
        
        #config date
        #dDate = {'end': datetime.time(20,50), 'begin': datetime.time(12,00), 'date': datetime.date(2014, 7, 18), 'part': 'afternoon', 'delta': 1, 'day' : 'Mon', 'Month':'July'}
        dDate = self.WITDate(jsonInput)
        #exceptions
        if dDate['delta'] > 7 :
            return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": self._("not yet")}                         #fatal
        if dDate['delta'] < 0 :
            return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": self._("too late")}                         #fatal
        #special case for evening
        if (dDate['part'] == u'alltheday') or  (dDate['begin'] == time(18,00) and  dDate['end'] == time(00,00)):  
            #by default, get TV for the evening
            dDate['begin'] = time(21,05)
            dDate['end'] = time(21,10)
            dDate['part'] = u'evening'
        #special case for other part of the day
        #...TODO if needed
        #for debug
        #print 'ma date       ', dDate

        
        #list all channel in programtv
        channelDict = {}
        for child in programmetv:
            if child.tag == u"channel":
                channelDict[child.attrib['id']] = child.find('display-name').text.upper()
            if child.tag == u"programme":
                break
        channelDict = self._channelCorrection(channelDict,self.configuration_lisa['lang'])
        #print channelDict
        
        
        #check if requested channel exist
        namchannel=u'all' #by default get tv for all channel
        if 'location' in jsonInput['outcome']['entities'] :
            for channel in channelDict :
                if ((jsonInput['outcome']['entities']['location']['value']).upper()) == channelDict[channel]:
                    namchannel = channelDict[channel]  #requested channel is in the xml
                    break
            if namchannel == 'all' : #if not found requested channel 
                return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": self._("dont know this channel")}          #fatal
        
        
        #check if not to much
        #I seleted 3h as maximun duration
        #if all channel and start time to end time > xh and not end time - actual time >xh, we say 'too much'
        #it will last many minutes to say all shows..
        if namchannel==u'all' and \
         (int(dDate['end'].strftime("%H"))-int(dDate['begin'].strftime("%H")))>=3 and \
         (int(dDate['end'].strftime("%H"))-int(datetime.now().time().strftime("%H")))>=3 :
            return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": self._("too much")}          #fatal
            

        #look for request date/channel
        progDict={} #contains tv programming, to re-order because xml file is not in time order !
        for child in programmetv.findall('programme'):    
            if (channelDict[child.attrib['channel']] == namchannel) or (namchannel == u'all') :  #check for request channel or all channel                    
                if child.attrib['start'][:8] == dDate['date'].strftime("%Y%m%d")  : #check for request date
                    if child.attrib['stop'][8:12] >= datetime.now().time().strftime("%H%M") : #dont care about already finish show 
                        if (child.attrib['start'][8:12] >= dDate['begin'].strftime("%H%M") and child.attrib['start'][8:12] <= dDate['end'].strftime("%H%M")) or \
                            (child.attrib['start'][8:12] < dDate['begin'].strftime("%H%M") and child.attrib['stop'][8:12] > dDate['begin'].strftime("%H%M")):#check for request time
                            #build return dict
                            tim = child.attrib['start'][8:12]
                            title = child.find('title').text
                            progDict[(child.attrib['channel'],tim)] = title
        #for debug
        #for t,s in sorted(progDict.iteritems()): print t,s
        
        #search for following episodes of same series
        episodedict={} 
        previousshow=u''  #what are you watching ?
        fistshow=u''  #
        for t,s in sorted(progDict.iteritems()): # sorted by channel and time
            #print t,s
            if s == previousshow :  #new episode of current show
                episodelist =  episodedict[firstshow]
                episodelist.append(t) #store times of episode
                episodedict[firstshow]=episodelist
            else :#new show
                firstshow = t
                previousshow=s
                episodedict[firstshow]=[] 
        
        #delete episodes on progDict 
        #and replace <episode name> by 'x episodes of <episode name>'
        for t,e in sorted(episodedict.iteritems()):
            #print t,s
            if e :
                nbepisode =1
                for i in e :
                    nbepisode+=1
                    del progDict[i]  #delete episode
                progDict[t]= self._('episodes').format(nbepisode=nbepisode,title = progDict[t])  #replace name
        #for debug
        #for t,s in sorted(progDict.iteritems()): print t,s
        

        #build return TV message
        programmetv_str = u""
        actualchannel = u""
        firstchannel = True
        previoustime = 0000  #heure-minutes
        future = dDate['delta'] > 0 and  u'-future' or u'' #speak with verb on future
        for t,p in sorted(progDict.iteritems()) : #sorted by channel and time
            #print t,p
            #time
            if t[1] < datetime.now().time().strftime("%H%M") :  #if TV show runs actually
                tim=self._('now')  
            elif (eval(t[1])-previoustime) > 8 :
                previoustime = eval(t[1])
                tim = self._('at') + self.time2str((t[1][:2]+':'+t[1][2:4]),pMinutes=0)
            elif (eval(t[1])-previoustime) < 8 :  #delete time if show lasts <8 minutes
                tim = ''
            #prog
            if t[0] <> actualchannel :  #new channel in the list
                if firstchannel == True :   #add . at the end of channel list. Except for the first channel.    ??? should be deleted
                    firstchannel = False
                else :
                    programmetv_str += '. '
                actualchannel = t[0]
                previoustime=00
                programmetv_str += self._('prog1{0}'.format(future)).format(channel = channelDict[t[0]],time =tim, title =p)
            else : #actual channel
                    programmetv_str += self._('prog2').format(time =tim, title = p)
        
    
        #build return start message
        if dDate['delta'] == 0 :
            message = self._('today-msg').format (part=self._(dDate['part']))
        elif dDate['delta'] == 1 :
            message = self._('tomorrow-msg').format(day = self._('tomorrow'), part=self._(dDate['part']))
        elif dDate['delta'] == 2 :
            message = self._('after-tomorrow-msg').format(day = self._('after tomorrow'), part=self._(dDate['part']))
        elif dDate['delta'] >2 :
            d =dDate['date'].strftime('%d')
            if d[0:1] == "0":
                d=d[1:2]
            message = self._("further day-msg").format(date = d, month=self._(dDate['month']),day=self._(dDate['day']),part=self._(dDate['part']))
        
        #final message
        message += programmetv_str +'.'
        
        return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": message}



    #-----------------------------------------------------------------------------    
    def getNextShow(self,jsonInput) :
        """
        look for the next time of requested show
        """
        #print 'json                     ',jsonInput
        #init
        rep = os.path.dirname(os.path.abspath(__file__)) + '/tmp/'+str(date.today())+'_programmetv.xml'
        self._downloadProgrammeTV(rep)
        programmetv = ET.parse(rep).getroot()

    
        #config show
        if 'message_body' in jsonInput['outcome']['entities'] :
            namshow = jsonInput['outcome']['entities']['message_body']['value']
            namshow = namshow.lower().strip()
        else :
            message = self._('no show')
            return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": message}          #fatal
        
        
        #look for show
        showList=[]
        for child in programmetv.findall('programme'):    
            if child.attrib['stop'][8:12] >= datetime.now().time().strftime("%H%M") : #dont care about already finish show
                if namshow in child.find('title').text.lower():
                    showList.append(child.attrib['start'][0:12])
                    namshow = child.find('title').text
        if not showList :
            message = self._('no show')
            return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": message}           #fatal
        #print showList
        
        #return message
        previousdelta=-1
        message = self._('next show').format(title=namshow)
        for el in showList :
            delta = (datetime.strptime(el,'%Y%m%d%H%M').date()-datetime.today().date()).days
            #build return start message
            if delta <> previousdelta :
                if delta == 0 :
                    message += self._('today')
                elif delta == 1 :
                    message += self._('tomorrow')
                elif delta== 2 :
                    message += self._('after tomorrow')
                elif delta >2 :
                    d =datetime.strptime(el,'%Y%m%d%H%M').strftime('%d')
                    if d[0:1] == "0":
                        d=d[1:2]
                    month = datetime.strptime(el,'%Y%m%d%H%M').strftime('%B')
                    day = datetime.strptime(el,'%Y%m%d%H%M').strftime('%c')[:3]
                    message += self._("further day-msg").format(date = d, month='',day=self._(day),part='')
                previousdelta = delta
        
            tim = self._('at') + self.time2str((el[8:10]+':'+el[10:12]),pMinutes=0) +', '
            message+= tim

        
        return {"plugin": __name__.split('.')[-1], "method": sys._getframe().f_code.co_name, "body": message}
        
    #-----------------------------------------------------------------------------
    #              Private  Fonctions
    #-----------------------------------------------------------------------------  
    def _downloadProgrammeTV(self,rep):
        
        url = "http://www.kazer.org/tvguide.xml?u=" + self.configuration_plugin['configuration']['user_id']
        
        if not os.path.exists(os.path.dirname(rep)) :
            os.mkdir(os.path.dirname(rep))
        
        if not os.path.isfile(rep) :
            #delete all old exisitng files
            fichier= os.listdir(os.path.dirname(rep))
            for f in fichier :
                os.remove(os.path.dirname(rep)+'/'+f)
            #download
            print self._("Downloading tv program")
            if __name__ == "__main__" : print '         debut telechargement';t1= datetime.now()
            urllib.urlretrieve(url,rep)         #write file
            if __name__ == "__main__" :print '         durée telechargement',datetime.now()-t1
            self._extractProgrammeTV(rep)
           
        return "SUCCESS"

    #-----------------------------------------------------------------------------    
    def _extractProgrammeTV(self,rep) :
        """
        supprime toutes les infos inutules de l xml et le ré-engregistre
        """
        print self._("creating tv program")
        if __name__ == "__main__" : print '         debut creation prog TV'; t1= datetime.now()
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
        if __name__ == "__main__" :print '         duree creation prog TV' ,datetime.now()-t1 
        return "SUCCESS"
  
        
    #-----------------------------------------------------------------------------    
    def _channelCorrection(self,channelDict,lang) :
        """
        corrige le nom des chaines pour les rendre plus naturel
        """
        if lang == 'fr' :
            for channel in channelDict :
                if channelDict[channel] == 'RMC DECOUVERTE' : channelDict[channel] = u'RMC' 
                if channelDict[channel] == 'I>TELE' : channelDict[channel] = u'I télé'
                if channelDict[channel] == 'BFM TV' : channelDict[channel] = u'BFM télé'
                if channelDict[channel] == 'PLANETE' : channelDict[channel] = u'planète'
                if channelDict[channel] == 'PARIS PREMIERE' : channelDict[channel] = u'paris première'
                if channelDict[channel] == 'NUMERO 23' : channelDict[channel] = u'numéro 23'
                if channelDict[channel] == 'L EQUIPE 21' : channelDict[channel] = u"l'équipe 21"
                if channelDict[channel] == 'ARTE' : channelDict[channel] = u"arté"
                if channelDict[channel] == '13EME RUE' : channelDict[channel] = u"13éme rue"
                if channelDict[channel] == '6 TER' : channelDict[channel] = u"6 ter"

        return channelDict
        
    #-----------------------------------------------------------------------------    
    

        
#-----------------------------------------------------------------------------
# Tests
#-----------------------------------------------------------------------------
if __name__ == "__main__" :
    jsonInput = {'from': u'Lisa-Web', 'zone': u'WebSocket', u'msg_id': u'2dba9333-a9f3-435c-bdca-c3beba73a633', 
    'lisaprotocol': '<lisa.server.libs.server.Lisa instance at 0x7f55f01dc128>', 
    u'msg_body': u'quel est le programme TV demain \xe0 21 heure sur France 4', 
    u'outcome': {
        u'entities': {
            u'message_body': {u'body': u'hercules poirot', u'start': 22, u'end': 37, u'suggested': True, u'value': u'hercule poirot'},
            
            u'datetime': {u'body': u'demain \xe0 21 heure', u'start': 25, u'end': 42, u'value': {u'to': u'2014-07-24T12:00:00.000+02:00', u'from': u'2014-07-23T08:00:00.000+02:00'}} 
        }, 
        u'confidence': 0.987, 
        u'intent': u'programmetv_getprogrammetv'
    }, 
    'type': u'chat'}
    #u'location': {u'body': u'France 4', u'start': 47, u'end': 55, u'suggested': True, u'value': u'tmc'},
    
    #print dir(ProgrammeTV)
    #print help(ProgrammeTV)
    
    
    essai = ProgrammeTV()
    retourn = essai.getProgrammeTV(jsonInput)
    #retourn = essai.getNextShow(jsonInput)
    print (retourn['body'])
