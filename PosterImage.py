from pandac.PandaModules import *
from direct.showbase.DirectObject import DirectObject
from direct.stdpy import threading

class PosterImage(DirectObject):

    LoadedPosters = {}

    def __init__(self, url):
        DirectObject.__init__(self)
        
        self.url = URLSpec(url)
        self.image = None

        # Create a condition variable so we can block on load.
        self.cvar = threading.Condition()
        self.done = False

        # Create an initial 1x1 white texture.
        self.tex = Texture(Filename(self.url.getPath()).getBasename())
        p = PNMImage(1, 1)
        p.fill(0.5, 0.5, 1)
        self.tex.load(p)

        if self.url.getScheme() == 'maze':
            # Here's a special case: instead of querying an HTTP
            # server, we get the local poster data from the maze
            # object.
            self.loadPlayerPoster()

        elif self.url.getScheme() == '':
            # Another special case: this is a local file.  This should
            # only happen from the local player.
            self.loadLocalPoster()
            
        else:
            # Otherwise, we get the poster data from the internet.
            self.loadingTask = taskMgr.add(self.load, 'loadPoster', taskChain = 'loadPoster')

    def loadLocalPoster(self):
        try:
            file = open(self.url.cStr(), 'rb')
        except IOError:
            print "Couldn't open file %s" % (self.url)
            self.__markDone()
            return

        data = file.read()
        self.loadImageData(data)

    def loadPlayerPoster(self):
        try:
            doId = int(self.url.getServer())
            i = int(self.url.getPath()[1:])
        except ValueError:
            print "Invalid maze URL: %s" % (self.url)
            self.__markDone()
            return

        base.w.relatedObjectMgr.requestObjects([doId], allCallback = self.__gotMaze, timeout = 5)

    def __gotMaze(self, mazeList):
        maze = mazeList[0]
        if not maze:
            print "No such maze: %s" % (doId)
            self.__markDone()
            return

        i = int(self.url.getPath()[1:])

        try:
            data = maze.posterData[i]
        except IndexError:
            print "Maze %s has no poster %s" % (doId, i)
            self.__markDone()
            return

        self.loadImageData(data)
        

    def block(self):
        """ Block the current thread until the texture is loaded. """
        self.cvar.acquire()
        while not self.done:
            self.cvar.wait()
        self.cvar.release()

    def __markDone(self):
        """ Called in the sub-thread to make sure that the texture is
        loaded. """
        self.cvar.acquire()
        self.done = True

        self.cvar.notifyAll()
        self.cvar.release()

    def load(self, task):
        """ Downloads the poster image and creates a Texture object. """
        try:
            http = HTTPClient.getGlobalPtr()
        except NameError:
            print "No HTTPClient available."
            self.__markDone()
            return
        
        doc = http.getDocument(self.url)
        rf = Ramfile()
        doc.downloadToRam(rf)
        if not doc.isValid():
            print "Failed to load %s: %s %s" % (self.url, doc.getStatusCode(), doc.getStatusString())
            self.__markDone()
            return

        # We've downloaded the URL, so now the image data is available
        # in RAM.  Load it into a PNMImage.
        self.loadImageData(rf.getData())

    def loadImageData(self, data):
        """ Once the image data has been retrieved, load it into a
        texture. """

        data = StringStream(data)
        p = PNMImage()

        # First, read the header to get the image size
        if not p.readHeader(data):
            print "Failed to read image header from %s" % (self.url)
            self.__markDone()
            return

        # Ensure the image is a power of 2
        self.tex.considerRescale(p)

        # Also ensure that it isn't larger than 256x256
        xsize = min(p.getReadXSize(), 256)
        ysize = min(p.getReadYSize(), 256)
        p.setReadSize(xsize, ysize)

        # Now, read the actual image data, scaling it to the requested
        # size as we read it.
        data.seekg(0)
        if not p.read(data):
            print "Failed to read image data from %s" % (self.url)
            self.__markDone()
            return

        self.image = p

        # Finally, load the PNMImage into the Texture.
        self.tex.load(p)
        self.tex.setMinfilter(Texture.FTLinearMipmapLinear)
        self.tex.setMagfilter(Texture.FTLinear)
        print "Loaded %s" % (self.url)
        self.__markDone()
                
