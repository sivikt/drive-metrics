
class Prefix:
    def __init__(self, abbr: str, uri: str):
        self._abbr = abbr
        self._uri = uri
        self._declaration = f"PREFIX {abbr}: <{uri}#>"

    def __str__(self):
        return self._declaration

    @property
    def declaration(self):
        return self._declaration

    @property
    def abbr(self):
        return self._abbr

    @property
    def uri(self):
        return self._uri


TRIP = Prefix('trip', 'http://www.semanticweb.org/dmonto/autology/trip')
TRIPUI = Prefix('tripui', 'http://www.semanticweb.org/dmonto/autology/tripui')
TRIPQA = Prefix('qa', 'http://www.semanticweb.org/dmonto/autology/qa-statistics')
OWL = Prefix('owl', 'http://www.w3.org/2002/07/owl')
XSD = Prefix('xsd', 'http://www.w3.org/2001/XMLSchema')
RDF = Prefix('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns')
RDFS = Prefix('rdfs', 'http://www.w3.org/2000/01/rdf-schema')
TIME = Prefix('time', 'http://www.w3.org/2006/time')
GEOSPARQL = Prefix('geosparql', 'http://www.opengis.net/ont/geosparql')


def declare_prefixes(*prefixes):
    return ' '.join(p.declaration for p in prefixes)
