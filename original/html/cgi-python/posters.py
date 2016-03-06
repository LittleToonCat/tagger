from mod_python import apache, util
import os
import sys
from PIL import Image
from cStringIO import StringIO
import cPickle
import traceback

def handler(req):
    log = StringIO()

    print >> log, req.unparsed_uri
    for key, value in req.headers_in.items():
        print >> log, '%s: %s' % (key, value)
    print >> log, ''

    try:
        return do_handler(req, log)

    except:
        traceback.print_exc(100, log)

        req.content_type = "text/plain"
        req.send_http_header()
        req.write(log.getvalue())
        return apache.OK

def do_handler(req, log):
    form = util.FieldStorage(req)

    playerId = form.get('playerId', None)
    try:
        playerId = int(playerId)
    except ValueError:
        return apache.HTTP_BAD_REQUEST
    except TypeError:
        return apache.HTTP_BAD_REQUEST
    nextUrl = str(form.get('nextUrl', None))
    if not nextUrl:
        return apache.HTTP_BAD_REQUEST
        
    poster = form.get('poster', None)

    print >> log, 'poster.file = %s type = %s' % (repr(poster.file), repr(poster.type))

    try:
        im = Image.open(poster.file)
        im.load()
    except IOError:
        redirectUrl = nextUrl + '?playerId=%s&invalid=1' % (playerId)
        util.redirect(req, redirectUrl)
        return apache.OK

    print >> log, 'im.size = %s' % (repr(im.size))

    # Make sure it's no larger than 256x256, and a power of 2.
    sx, sy = im.size
    if sx <= 0 or sy <= 0:
        redirectUrl = nextUrl + '?playerId=%s&invalid=1' % (playerId)
        util.redirect(req, redirectUrl)
        return apache.OK

    aspect = float(sx) / float(sy)
    sx = toPower2(sx)
    sy = toPower2(sy)

    im = im.resize((sx, sy), Image.BILINEAR)
    print >> log, 'im.size = %s' % (repr(im.size))

    print >> log, 'os.cwd = %s' % (repr(os.getcwd()))
    print >> log, 'sys.argv = %s' % (repr(sys.argv))
    print >> log, '__file__ = %s' % (repr(__file__))

    outputFile = StringIO()
    im.save(outputFile, 'JPEG', quality = 65)
    data = outputFile.getvalue()

    filename = os.path.split(__file__)[0]
    filename = os.path.split(filename)[0]
    uploads = os.path.join(filename, 'uploads', 'poster_%s.pkl' % (playerId))
    print >> log, 'uploads = %s' % (repr(uploads))

    posterData = (data, aspect)
    file = open(uploads, 'wb')
    cPickle.dump(posterData, file, cPickle.HIGHEST_PROTOCOL)
    file.close()

    posters = os.path.join(filename, 'posters', 'poster_%s.pkl' % (playerId))
    os.rename(uploads, posters)

    redirectUrl = nextUrl + '?playerId=%s&success=1' % (playerId)
    util.redirect(req, redirectUrl)
    
    return apache.OK

def toPower2(s):
    if s < 1:
        return 1
    
    power2 = 256
    while s < power2:
        power2 >>= 1
    return power2
        
