from direct.distributed.AstronInternalRepository import AstronInternalRepository
from pandac.PandaModules import *
from TagManagerAI import TagManagerAI
from TagGameAI import TagGameAI
from TagPlayerAI import TagPlayerAI
import Globals
import sys
import os
import cPickle
from cStringIO import StringIO

class TagAIRepository(AstronInternalRepository):
    def __init__(self, baseChannel, serverId, threadedNet = True):
        dcFileNames = ['direct.dc', 'tagger.dc']

        self.GameGlobalsId = 1000

        AstronInternalRepository.__init__(self, baseChannel, serverId, dcFileNames = dcFileNames,
                                  dcSuffix = 'AI', connectMethod = self.CM_NET,
                                  threadedNet = threadedNet)

        # Allow some time for other processes.
        base.setSleep(0.01)

        taskMgr.setupTaskChain('updateCells', numThreads = 1,
                               threadPriority = TPLow, frameSync = True)

        taskMgr.doMethodLater(5, self.__checkPosters, 'checkPosters')

        self.games = []

        self.managerId = self.allocateChannel()

        self.zoneAllocator = UniqueIdAllocator(3, 1000000)

        tcpPort = base.config.GetInt('ai-server-port', 7190)
        hostname = base.config.GetString('ai-server-host', '127.0.0.1')
        self.acceptOnce('airConnected', self.connectSuccess)
        self.connect(hostname, tcpPort)


    def connectSuccess(self):
        """ Successfully connected to the Message Director.
            Now to generate the TagManagerAI """
        print 'Connected successfully!'

        self.timeManager = TagManagerAI(self)
        self.timeManager.generateWithRequiredAndId(self.managerId, self.GameGlobalsId, 1)
        self.timeManager.setAI(self.ourChannel)
        self.districtId = self.timeManager.doId
        #self.makeGame()

    def lostConnection(self):
        # This should be overridden by a derived class to handle an
        # unexpectedly lost connection to the gameserver.
        self.notify.warning("Lost connection to gameserver.")
        sys.exit()

    def makeGame(self, playerIds = [], prevMaze = None):
        # Create a TagGame and place it in zone 2 for players to find
        # it and join it.

        game = TagGameAI(self)
        game.generateWithRequired(2)
        game.generateMaze(playerIds, prevMaze = prevMaze)

        self.games.append(game)

        return game.doId

        # Listen for players in all of our games' objZone.
        #zoneIds = map(lambda g: g.objZone, self.games)
        #self.setInterestZones(zoneIds)

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

    def getAvatarIdFromSender(self):
        return self.getMsgSender() & 0xFFFFFFFFL
