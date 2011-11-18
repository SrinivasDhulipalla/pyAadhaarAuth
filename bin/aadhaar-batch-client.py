#!/usr/bin/python
#
#Copyright (C) 2011 by Venkata Pingali (pingali@gmail.com) & TCS 
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import os, os.path, sys

# For dumper library 
import AadhaarAuth
auth_path = os.path.dirname(os.path.realpath(AadhaarAuth.__file__))
sys.path.append(auth_path + "/lib") 

import copy 
import logging
from lxml import etree, objectify 
import tempfile 
import dumper 
import hashlib, hmac, base64, random 
from config import Config 
import traceback 
from datetime import datetime
from M2Crypto import Rand 
import json
from pprint import pprint

from AadhaarAuth.request import AuthRequest
from AadhaarAuth.data import AuthData
from AadhaarAuth.command import AuthConfig

log = logging.getLogger("AuthBatchRequest")

__author__ = "Venkata Pingali"
__copyright__ = "Copyright 2011,Venkata Pingali and TCS" 
__credits__ = ["UIDAI", "MindTree", "GeoDesic", "Viral Shah"] 
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Venkata Pingali"
__email__ = "pingali@gmail.com"
__status__ = "Pre-release"


"""
Issue batch requests to the server
"""
class AuthBatchRequest():
    """
    Issue batch requests to the server 
    """
    
    data_xmlns = "http://www.uidai.gov.in/authentication/uid-auth-request-data/1.0"
    
    def __init__(self, cfg): 
        self._cfg = cfg 
        self._json_file = cfg.batch.json
        self._data = None 
        self._xml_hash = {} 
        self._processing_functions = {} 

    def name_exact(self, root, person): 

        uses = root.find('Uses')
        uses.set("pi","y")
        pid = root.find('Pid')
        demo = etree.SubElement(pid, "Demo")
        pi=etree.SubElement(demo, "Pi", ms="E", name=person['name'])

    def name_partial(self, root, person): 

        uses = root.find('Uses')
        uses.set("pi","y")
        pid = root.find('Pid')
        demo = etree.SubElement(pid, "Demo")
        pi=etree.SubElement(demo, "Pi", ms="P", mv="70", 
                            name=person['name'])

    def address_exact(self, root, person):

        uses = root.find('Uses')
        uses.set("pa","y")
        pid = root.find('Pid')
        demo = etree.SubElement(pid, "Demo")
        pi=etree.SubElement(demo, "Pa", 
                            ms="E", 
                            street=person['street'],
                            vtc=person['vtc'],
                            subdist=person['subdist'],
                            district=person['district'],
                            state=person['state'],
                            pincode=person['pincode'])
    
    def email_exact(self, root, person): 

        uses = root.find('Uses')
        uses.set("pi","y")
        pid = root.find('Pid')
        demo = etree.SubElement(pid, "Demo")
        pi=etree.SubElement(demo, "Pi", ms="E",
                            email=person['email'])

    def phone_exact(self, root, person): 

        uses = root.find('Uses')
        uses.set("pi","y")
        pid = root.find('Pid')
        demo = etree.SubElement(pid, "Demo")
        pi=etree.SubElement(demo, "Pi", ms="E",
                            email=person['phone'])

    #def pin_otp(self, root, person):  
    #
    #    uses = root.find('Uses')
    #    uses.set("pi","y")
    #    pid = root.find('Pid')
    #    demo = etree.SubElement(pid, "Demo")
    #    pi=etree.SubElement(demo, "Pv", 
    #                        pin=person['pin'],
    #                        otp=person['otp'])

    def bio_fmr(self, root, person): 

        uses = root.find('Uses')
        uses.set("bio","y")
        uses.set("bt","FMR")
        pid = root.find('Pid')
        bios = etree.SubElement(pid, "Bios")
        bio = etree.SubElement(bios, "Bio", 
                               type="FMR")
        bio.text = person['bio']
    
    def register_processing_functions(self): 
        
        self._processing_functions = { 
            'name_exact': ["Exact name", self.name_exact],
            'name_partial': ["Partial name", self.name_partial],
            'address_exact': ["Exact address", self.address_exact],
            'email_exact': ["Exact Email", self.email_exact],
            'phone_exact': ["Exact phone", self.phone_exact],
            'bio_only': ["Bio FMR", self.bio_fmr],
            }
    
    def load_data(self): 
        """
        Load json data
        """
        fp=open(self._json_file)
        self._data = json.load(fp)
        fp.close()

    def generate_xml(self): 
        
        if (self._data == None): 
            self.load_data() 

        # Generate the xml 
        ts = datetime.now()
        root = etree.Element('Auth', 
                             xmlns=self._cfg.common.request_xmlns,
                             ver=self._cfg.common.ver,
                             tid=self._cfg.common.tid,
                             ac=self._cfg.common.ac, 
                             sa=self._cfg.common.sa,
                             txn = "",
                             uid = "",
                             lk=self._cfg.common.license_key,
                             )
        uses = etree.SubElement(root, "Uses", 
                                otp="n", 
                                pin="n",
                                bio="n",
                                pfa="n",
                                pi="n",
                                pa="n")
        pid = etree.SubElement(root, 'Pid', 
                             xmlns=self.data_xmlns, 
                             ts=ts.strftime("%Y-%m-%dT%H:%M:%S"),
                             ver="1.0")
            
        for person in self._data:            
            #print person 
            for func_name,func_details in self._processing_functions.items():
                func = func_details[1] 
                
                # Fix some details of the root
                new_root = copy.deepcopy(root)
                new_root.set('uid', person['uid'])
                new_root.set('txn', "batch:"+random.randint(2**20, 2**30-1).__str__())
                
                # Now insert the demo/bio element 
                func(new_root, person) 
                
                # output the tree 
                print "------"
                print "UID,Test Name"
                print "%s,%s" %(person['uid'], func_details[0])
                print etree.tostring(new_root, pretty_print=True)
                
    def authenticate_basic(self): 
        
        log.debug("Authenticating") 

        for person in self._data: 
            cfg= self._cfg 
            cfg.request.uid = person['uid'] 
            cfg.request.demographics = ["Pi"]
            cfg.request.biometrics = ["FMR"]
            cfg.request['Pi'] = {
                'ms': "E",
                'name': person['name']
                }
            cfg.request["FMR"] = { 
                'bio': person['bio']
                }

            # => Gather the data from the (simulated) client
            data = AuthData(cfg=cfg) 
            data.generate_client_xml() 
            exported_data = data.export_request_data() 
            
            # Create the request object and execute 
            req = AuthRequest(cfg)
            req.import_request_data(exported_data)
            req.execute()
            

if __name__ == '__main__':
       
    logging.basicConfig() 

    cmd = AuthConfig('batch', "Batch processing") 
    cfg = cmd.update_config() 

    #=> Setup logging 
    logging.getLogger().setLevel(logging.WARN) #cfg.common.loglevel )
    logging.basicConfig(
	filename='execution.log',
	format='%(asctime)-6s: %(name)s - %(levelname)s - %(message)s') 

    log.info("Starting my Batch AuthClient")

    batch = AuthBatchRequest(cfg=cfg)
    batch.load_data() 
    batch.authenticate_basic() 
    #batch.register_processing_functions() 
    #batch.generate_xml()
