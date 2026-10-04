"""Set document properties before the package is validated."""
from pathlib import Path
from zipfile import ZipFile
import sys
import xml.etree.ElementTree as ET

path = Path(sys.argv[1])
dc = 'http://purl.org/dc/elements/1.1/'
cp = 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
ET.register_namespace('dc', dc)
ET.register_namespace('cp', cp)
ET.register_namespace('dcterms', 'http://purl.org/dc/terms/')
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
with ZipFile(path) as source:
    members = [(item, source.read(item.filename)) for item in source.infolist()]
temporary = path.with_suffix('.metadata.pptx')
with ZipFile(temporary, 'w') as output:
    for item, data in members:
        if item.filename == 'docProps/core.xml':
            root = ET.fromstring(data)
            for name, value in [(f'{{{dc}}}creator', 'Loukas Louka'), (f'{{{cp}}}lastModifiedBy', 'Loukas Louka'), (f'{{{dc}}}title', 'Aktina | Pafos 2026')]:
                element = root.find(name)
                if element is None:
                    element = ET.SubElement(root, name)
                element.text = value
            data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        output.writestr(item, data)
temporary.replace(path)
