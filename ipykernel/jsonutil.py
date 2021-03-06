"""Utilities to manipulate JSON objects."""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

import math
import re
import types
from datetime import datetime
import numbers

try:
    # base64.encodestring is deprecated in Python 3.x
    from base64 import encodebytes
except ImportError:
    # Python 2.x
    from base64 import encodestring as encodebytes

from ipython_genutils import py3compat
from ipython_genutils.py3compat import unicode_type, iteritems
from ipython_genutils.encoding import DEFAULT_ENCODING
next_attr_name = '__next__' if py3compat.PY3 else 'next'

#-----------------------------------------------------------------------------
# Globals and constants
#-----------------------------------------------------------------------------

# timestamp formats
ISO8601 = "%Y-%m-%dT%H:%M:%S.%f"
ISO8601_PAT=re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d{1,6})?Z?([\+\-]\d{2}:?\d{2})?$")

# holy crap, strptime is not threadsafe.
# Calling it once at import seems to help.
datetime.strptime("1", "%d")

#-----------------------------------------------------------------------------
# Classes and functions
#-----------------------------------------------------------------------------


# constants for identifying png/jpeg data
PNG = b'\x89PNG\r\n\x1a\n'
# front of PNG base64-encoded
PNG64 = b'iVBORw0KG'
JPEG = b'\xff\xd8'
# front of JPEG base64-encoded
JPEG64 = b'/9'
# front of PDF base64-encoded
PDF64 = b'JVBER'

def encode_images(format_dict):
    """b64-encodes images in a displaypub format dict

    Perhaps this should be handled in json_clean itself?

    Parameters
    ----------

    format_dict : dict
        A dictionary of display data keyed by mime-type

    Returns
    -------

    format_dict : dict
        A copy of the same dictionary,
        but binary image data ('image/png', 'image/jpeg' or 'application/pdf')
        is base64-encoded.

    """
    encoded = format_dict.copy()

    pngdata = format_dict.get('image/png')
    if isinstance(pngdata, bytes):
        # make sure we don't double-encode
        if not pngdata.startswith(PNG64):
            pngdata = encodebytes(pngdata)
        encoded['image/png'] = pngdata.decode('ascii')

    jpegdata = format_dict.get('image/jpeg')
    if isinstance(jpegdata, bytes):
        # make sure we don't double-encode
        if not jpegdata.startswith(JPEG64):
            jpegdata = encodebytes(jpegdata)
        encoded['image/jpeg'] = jpegdata.decode('ascii')

    pdfdata = format_dict.get('application/pdf')
    if isinstance(pdfdata, bytes):
        # make sure we don't double-encode
        if not pdfdata.startswith(PDF64):
            pdfdata = encodebytes(pdfdata)
        encoded['application/pdf'] = pdfdata.decode('ascii')

    return encoded


def json_clean(obj):
    """Clean an object to ensure it's safe to encode in JSON.

    Atomic, immutable objects are returned unmodified.  Sets and tuples are
    converted to lists, lists are copied and dicts are also copied.

    Note: dicts whose keys could cause collisions upon encoding (such as a dict
    with both the number 1 and the string '1' as keys) will cause a ValueError
    to be raised.

    Parameters
    ----------
    obj : any python object

    Returns
    -------
    out : object

      A version of the input which will not cause an encoding error when
      encoded as JSON.  Note that this function does not *encode* its inputs,
      it simply sanitizes it so that there will be no encoding errors later.

    """
    # types that are 'atomic' and ok in json as-is.
    atomic_ok = (unicode_type, type(None))

    # containers that we need to convert into lists
    container_to_list = (tuple, set, types.GeneratorType)

    # Since bools are a subtype of Integrals, which are a subtype of Reals,
    # we have to check them in that order.

    if isinstance(obj, bool):
        return obj

    if isinstance(obj, numbers.Integral):
        # cast int to int, in case subclasses override __str__ (e.g. boost enum, #4598)
        return int(obj)

    if isinstance(obj, numbers.Real):
        # cast out-of-range floats to their reprs
        if math.isnan(obj) or math.isinf(obj):
            return repr(obj)
        return float(obj)
    
    if isinstance(obj, atomic_ok):
        return obj

    if isinstance(obj, bytes):
        return obj.decode(DEFAULT_ENCODING, 'replace')

    if isinstance(obj, container_to_list) or (
        hasattr(obj, '__iter__') and hasattr(obj, next_attr_name)):
        obj = list(obj)

    if isinstance(obj, list):
        return [json_clean(x) for x in obj]

    if isinstance(obj, dict):
        # First, validate that the dict won't lose data in conversion due to
        # key collisions after stringification.  This can happen with keys like
        # True and 'true' or 1 and '1', which collide in JSON.
        nkeys = len(obj)
        nkeys_collapsed = len(set(map(unicode_type, obj)))
        if nkeys != nkeys_collapsed:
            raise ValueError('dict cannot be safely converted to JSON: '
                             'key collision would lead to dropped values')
        # If all OK, proceed by making the new dict that will be json-safe
        out = {}
        for k,v in iteritems(obj):
            out[unicode_type(k)] = json_clean(v)
        return out
    if isinstance(obj, datetime):
        return obj.strftime(ISO8601)
    
    # we don't understand it, it's probably an unserializable object
    raise ValueError("Can't clean for JSON: %r" % obj)
