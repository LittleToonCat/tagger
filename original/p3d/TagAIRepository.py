from direct.distributed.ClientRepository import ClientRepository
from pandac.PandaModules import *
from TagGameAI import TagGameAI
from TagPlayerAI import TagPlayerAI
import Globals
import sys
import os
import cPickle
from cStringIO import StringIO

class TagAIRepository(ClientRepository):
    def __init__(self, threadedNet = True):
        dcFileNames = ['direct.dc', 'tagger.dc']

        ClientRepository.__init__(self, dcFileNames = dcFileNames,
                                  dcSuffix = 'AI', connectMethod = self.CM_NET,
                                  threadedNet = threadedNet)

        # Need at least 32 bits to receive big picture packets.
        self.setTcpHeaderSize(4)

        # Allow some time for other processes.
        base.setSleep(0.01)

        taskMgr.setupTaskChain('updateCells', numThreads = 1,
                               threadPriority = TPLow, frameSync = True)

        taskMgr.doMethodLater(5, self.__checkPosters, 'checkPosters')

        self.games = []

        tcpPort = base.config.GetInt('server-port', Globals.ServerPort)
        hostname = base.config.GetString('server-host', Globals.ServerHost)
        if not hostname:
            hostname = 'localhost'
        url = URLSpec('g://%s:%s' % (hostname, tcpPort))
        self.connect([url],
                     successCallback = self.connectSuccess,
                     failureCallback = self.connectFailure)

    def connectFailure(self, statusCode, statusString):
        raise StandardError, statusString

    def connectSuccess(self):
        """ Successfully connected.  But we still can't really do
        anything until we've got the doID range. """
        self.accept('createReady', self.gotCreateReady)

    def lostConnection(self):
        # This should be overridden by a derived class to handle an
        # unexpectedly lost connection to the gameserver.
        self.notify.warning("Lost connection to gameserver.")
        sys.exit()

    def gotCreateReady(self):
        """ Now we're ready to go! """
        if not self.haveCreateAuthority():
            # Not ready yet.
            return

        self.ignore('createReady')

        # Put the TagManager in zone 1 where the clients can find it.
        self.timeManager = self.createDistributedObject(
            className = 'TagManagerAI', zoneId = 1)

        self.zoneAllocator = UniqueIdAllocator(3, 1000000)

        #self.makeGame(self.allocateDoId())

    def makeGame(self, doId, playerIds = [], prevMaze = None):
        # Create a TagGame and place it in zone 2 for players to find
        # it and join it.

        game = TagGameAI(self)
        game.doId = doId
        game.generateMaze(playerIds, prevMaze = prevMaze)
        self.createDistributedObject(
            distObj = game, zoneId = 2, doId = doId, reserveDoId = False)

        self.games.append(game)

        # Listen for players in all of our games' objZone.
        zoneIds = map(lambda g: g.objZone, self.games)
        self.setInterestZones(zoneIds)

    def __checkPosters(self, task):
        """ This task runs every few seconds to see if someone has
        uploaded a new poster recently. """

        dir = Globals.ScanPosterDirectory
        try:
            files = os.listdir(dir)
        except OSError:
            files = None
        if not files:
            return task.again

        for filename in files:
            pathname = os.path.join(dir, filename)
            if not filename.startswith('poster_'):
                os.unlink(pathname)
                continue
            basename, ext = os.path.splitext(filename)
            if ext != '.pkl':
                os.unlink(pathname)
                continue

            playerId = basename.split('_', 2)[1]
            try:
                playerId = int(playerId)
            except ValueError:
                playerId = None
            if not playerId:
                os.unlink(pathname)
                continue

            posterData = cPickle.load(open(pathname, 'rb'))
            os.unlink(pathname)

            player = self.doId2do.get(playerId)
            if not isinstance(player, TagPlayerAI) or not player.air:
                continue

            player.b_setPoster(posterData)

        return task.again
    
