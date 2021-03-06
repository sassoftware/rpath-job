#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from lxml import etree
import StringIO
import sys
from xml.dom import minidom

from rpath_xmllib import api1 as _xmllib
InvalidXML = _xmllib.InvalidXML

class Base(object):
    xmlSchemaNamespace = "http://www.w3.org/2001/XMLSchema-instance"
    InvalidXML = InvalidXML

    def serialize(self, stream, validate = True):
        attrs = [
            ('xmlns', self.defaultNamespace),
            ('xmlns:xsi', self.xmlSchemaNamespace),
            ('xsi:schemaLocation', self.xmlSchemaLocation),
        ]
        self._writeToStream(stream, attrs)

    def parseStream(self, fromStream):
        if isinstance(fromStream, (str, unicode)):
            func = minidom.parseString
        else:
            func = minidom.parse
        try:
            doc = func(fromStream)
        except Exception, e:
            raise self.InvalidXML(e), None, sys.exc_info()[2]
        rootNode = doc.documentElement
        self.__init__()
        self.build(rootNode)

    def getElementTree(self, attrs = None):
        if attrs:
            namespacedef = ' '.join('%s="%s"' % a for a in attrs)
        else:
            namespacedef = None

        sio = StringIO.StringIO()
        self.export(sio, 0, namespace_ = '', name_ = self.RootNode,
            namespacedef_ = namespacedef)
        sio.seek(0)
        tree = etree.parse(sio)
        return tree

    def _writeToStream(self, stream, attrs):
        tree = self.getElementTree(attrs)
        tree.write(stream, encoding = 'UTF-8', pretty_print = True,
            xml_declaration = True)
        return tree
