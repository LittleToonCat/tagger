from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.directnotify.DirectNotifyGlobal import directNotify
from pandac.PandaModules import *
from TagAvatarAI import TagAvatarAI
import Globals

class TagPlayerAI(DistributedObjectAI):

    notify = directNotify.newCategory("TagPlayerAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.name = None
        self.color = None
        self.score = None
        self.artBonus = 0
        self.game = None
        self.gameId = 0
        self.avId = 0
        self.scoreDirty = False

        # The player's poster, if set.  This can be set either from
        # the AI side, or from the client side through the normal
        # DistributedObject channels (it is set directly to the server
        # via a separate POST operation, since JavaScript can't read a
        # file locally).
        self.posterData = ('', 0)

        # The cell onto which this player's poster is/will be applied.
        self.posterCell = None

        self.updateScoreTask = None

        # Which cell the player's avatar appears to be standing in.
        self.cellLocation = None

        # A dictionary of other player avatars we've painted on.
        self.paintedAvatars = {}

        # Cells that we've painted.
        self.paintedCells = []

        self.accept('deleteAvatar', self.deleteAvatar)

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        messenger.send('newPlayer', [self])

        self.updateScoreTask = taskMgr.doMethodLater(0.5, self.__updateScore, 'updateScore')

    def delete(self):
        taskMgr.remove(self.updateScoreTask)
        self.updateScoreTask = None
        
        for cell in self.paintedCells:
            cell.removePlayer(self)

        messenger.send('deletePlayer', [self])
        DistributedObjectAI.delete(self)

    def deleteAvatar(self, av):
        """ This message is sent whenever any TagAvatarAI is deleted. """
        if av in self.paintedAvatars:
            del self.paintedAvatars[av]
            self.scoreDirty = True

    def setName(self, name):
        self.name = name

    def setColor(self, color):
        self.color = color

        # Store the color as a PixelSpec too, which is used for
        # bookkeeping.
        self.pixelSpec = PNMImage.PixelSpec(int(color[0] * 255),
                                            int(color[1] * 255),
                                            int(color[2] * 255))

    def setGameId(self, gameId):
        self.gameId = gameId

    def setAvId(self, avId):
        self.avId = avId

    def setScore(self, score):
        self.score = score

    def __updateScore(self, task):
        """ Computes the new score after pixel counts have
        changed. """

        if not self.game or not self.game.gameActive:
            return task.again

        if not self.scoreDirty:
            return task.again

        self.scoreDirty = False

        wallCount = 0
        floorCount = 0
        pixelCount = 0
        for cell in self.paintedCells:
            with cell.playersLock:
                for dir in Globals.AllPaintList:
                    pixelCount += cell.players.get(self, {}).get(dir, 0)
                    if cell.wonPlayers.get(dir, None) == self:
                        if dir & Globals.AllDirs:
                            wallCount += 1
                        else:
                            floorCount += 1

        avPixelCount = sum(self.paintedAvatars.values())

        # Get the avatar associated with this player.
        onMePixelCount = 0
        myAv = self.air.doId2do.get(self.avId)
        if myAv:
            onMePixelCount = sum(myAv.paintedOnMe.values())

        for wc, bonus in Globals.WallBonus:
            if wallCount >= wc:
                break

        self.score = int((Globals.PointsPerWall * wallCount + Globals.PointsPerFloor * floorCount + Globals.PointsPerPixel * pixelCount + Globals.PointsPerAvatarPixel * avPixelCount + Globals.PointsPerMePixel * onMePixelCount) * bonus)
        self.sendUpdate('setScoreDerivation', [wallCount, floorCount, pixelCount, avPixelCount, onMePixelCount, bonus])
        self.sendUpdate('setScore', [self.score])

        return task.again


    def avatarPixelCount(self, avId, count):
        """ Sent (by any client) when the painted-pixel count of this
        player onto the indicated avatar changes. """

        av = self.air.doId2do.get(avId)
        if av and isinstance(av, TagAvatarAI):
            oldCount = self.paintedAvatars.get(av, 0)
            self.paintedAvatars[av] = count
            if self.doId != av.playerId:
                av.paintedOnMe[self] = count
                p2 = self.air.doId2do.get(av.playerId)
                if p2:
                    p2.scoreDirtry = True

            self.scoreDirty = True

    def getPoster(self):
        return (self.posterData,)
        
    def setPoster(self, posterData):
        """ Set from the client, or from the AI repository. """
        print "setPoster(%s, %s)" % (len(posterData[0]), posterData[1])
        self.posterData = posterData

        if self.posterCell:
            self.posterCell.updatePosterData(posterData)

    def d_setPoster(self, posterData):
        self.sendUpdate('setPoster', [posterData])

    def b_setPoster(self, posterData):
        self.setPoster(posterData)
        self.d_setPoster(posterData)
