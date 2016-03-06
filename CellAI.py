from direct.distributed.DistributedObjectAI import DistributedObjectAI
from pandac.PandaModules import *
from direct.stdpy import threading
import Globals

class CellAI(DistributedObjectAI):

    white = PNMImage(Globals.PaintXSize, Globals.PaintYSize)
    white.fill(1, 1, 1)
    
    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)

        self.bits = Globals.AllDirs
        self.needsUpdateBits = 0
        self.updateCellTask = None
        self.sx = 0
        self.sy = 0
        self.geom = None

        # The player that owns the poster in this cell, if any.
        self.posterPlayerId = None
        self.posterDir = 0
        self.posterData = ('', 0)

        self.updateLock = threading.Lock()
        self.paintedLock = threading.Lock()
        self.playersLock = threading.Lock()

        # A set of zoneIds, representing the zones that may be seen
        # from this cell.
        self.visibleZoneIds = set()

        # The same set, representing the union of visibleZoneIds from
        # all of our eight neighbors as well.
        self.expandedZoneIds = set()

        # A nested dictionary of player -> { dir -> count }, showing
        # the number of pixels each player has on the wall.
        self.players = {}

        # A dictionary of dir -> player, the player who has "won" each
        # wall.
        self.wonPlayers = {}

        # Walls that have been painted, and their generated images.
        self.painted = {}
        self.userPaintData = {}

        # The "score" of the painted wall.
        self.artScore = {}

    def countWalls(self):
        """ Returns the number of walls (not counting floor or
        ceiling) in the cell. """
        numWalls = 0
        for dir in Globals.AllDirsList:
            if self.bits & dir:
                numWalls += 1
        return numWalls

    def getWalls(self):
        """ Returns a list of tuples (sx, sy, dir) for each wall in
        the cell. """
        walls = []
        for dir in Globals.AllDirsList:
            if self.bits & dir:
                walls.append((self.sx, self.sy, dir))
        return walls
    
    def removePlayer(self, player):
        """ This player is going away; remove it from our
        dictionary. """

        with self.playersLock:
            del self.players[player]
            for dir, p2 in self.wonPlayers.items():
                if p2 is player:
                    self.wonPlayers[dir] = None

    def setGeometry(self, bits, sx, sy):
        self.bits = bits
        self.sx = sx
        self.sy = sy

    def getGeometry(self):
        return [self.bits, self.sx, self.sy]

    def getPaintSouth(self):
        return self.__getPaint(Globals.South)

    def getPaintNorth(self):
        return self.__getPaint(Globals.North)

    def getPaintEast(self):
        return self.__getPaint(Globals.East)

    def getPaintWest(self):
        return self.__getPaint(Globals.West)

    def getPaintFloor(self):
        return self.__getPaint(Globals.Floor)

    def getPaintCeiling(self):
        return self.__getPaint(Globals.Ceiling)

    def getPoster(self):
        return [self.posterDir, self.posterData]

    def __getPaint(self, dir):
        with self.paintedLock:
            p = self.painted.get(dir, None)
            if not p:
                return ''

        data = StringStream()
        p.write(data, Globals.ImageFormat)
        return data.getData()

    def userPaint(self, dir, data):
        """ Sent by the client to indicate he/she has painted some
        onto the wall. """

        player = self.air.doId2do.get(self.air.getAvatarIdFromSender())
        if not player:
            return

        with self.updateLock:
            # One way or another, we're going to have to retransmit this
            # cell's data later.
            self.needsUpdateBits |= dir
            if not self.updateCellTask:
                self.updateCellTask = taskMgr.doMethodLater(0.5, self.__updateCell, 'updateCell', taskChain = 'updateCells')

            # Check to ensure the player can reach this location.
            if not player.cellLocation or player.cellLocation.zoneId not in self.visibleZoneIds:
                return

            self.userPaintData.setdefault(dir, []).append((player, data))


    def markPrevUser(self, player, dir):
        """ Marks that the indicated player was the owner of the paint
        on this wall in the previous game (this must have been an art
        painting carried forward).  This gives the player credit for
        the paint on the wall at game start. """

        with self.updateLock:
            self.needsUpdateBits |= dir
            if not self.updateCellTask:
                self.updateCellTask = taskMgr.doMethodLater(0.5, self.__updateCell, 'updateCell', taskChain = 'updateCells')

            self.userPaintData.setdefault(dir, []).append((player, ''))
            if self.posterDir and not self.posterPlayerId:
                self.posterPlayerId = player.doId

    def __updateCell(self, task):
        """ This task is called in a sub-thread to actually update the
        paint on the wall. """

        with self.updateLock:
            self.updateCellTask = None
            needsUpdateBits = self.needsUpdateBits
            self.needsUpdateBits = 0
            userPaintData = self.userPaintData
            self.userPaintData = {}

        if not needsUpdateBits:
            # We've already updated it.
            return

        for dir in Globals.AllPaintList:
            if not (dir & needsUpdateBits):
                continue

            paintData = userPaintData.get(dir, [])
            
            # Get the images other users have painted so far.
            with self.paintedLock:
                p = self.painted.get(dir, None)
                if not p:
                    p = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
                    p.fill(1)
                    self.painted[dir] = p

            i = 0
            lastPlayer = None
            while i < len(paintData):
                player, data = paintData[i]

                with self.playersLock:
                    if player not in self.players:
                        self.players[player] = {}
                        player.paintedCells.append(self)

                if not data:
                    i += 1
                    continue

                if player is not lastPlayer:
                    # Create an image with the solid color for the user.
                    colorp = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
                    colorp.fill(*player.color)

                myp = PNMImage()
                myp.read(StringStream(data), Globals.ImageFormat)

                # Now apply the alpha channel from what the user has recently
                # drawn.  This makes our previously solid color become a
                # mostly-transparent image, except where the user has drawn
                # stuff.
                colorp.copyChannel(myp, 0, 0, 3)

                # Apply the new drawing on top of the existing paint.
                p.blendSubImage(colorp, 0, 0)

                # Get the next drawing in the list.
                i += 1

            # And now retransmit the drawing to all the clients.
            data = StringStream()
            p.write(data, Globals.ImageFormat)
            imgData = data.getData()
            self.artScore[dir] = len(imgData)

            if dir == Globals.South:
                self.sendUpdate('setPaintSouth', [imgData])
            elif dir == Globals.North:
                self.sendUpdate('setPaintNorth', [imgData])
            elif dir == Globals.East:
                self.sendUpdate('setPaintEast', [imgData])
            elif dir == Globals.West:
                self.sendUpdate('setPaintWest', [imgData])
            elif dir == Globals.Floor:
                self.sendUpdate('setPaintFloor', [imgData])
            elif dir == Globals.Ceiling:
                self.sendUpdate('setPaintCeiling', [imgData])

            # Also do some bookkeeping now: find the player with the
            # most paint on the wall, and give him/her the points for
            # it.

            pcopy = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 3)

            # Strip out any pixels whose alpha value is less than 0.5.
            pcopy.threshold(p, 3, 0.5, self.white, p)
            hist = pcopy.Histogram()
            pcopy.makeHistogram(hist)

            # How many pixels has each player contributed to the wall, and
            # which player has won the wall?
            with self.playersLock:
                wonPlayer = None
                wonCount = Globals.MinWallPaint
                for p2, ddict in self.players.items():
                    count = hist.getCount(p2.pixelSpec)
                    ddict[dir] = count
                    if count >= wonCount:
                        wonPlayer = p2
                        wonCount = count

                self.wonPlayers[dir] = wonPlayer

                # We have to update the score for all players, since we might
                # have overpainted some pixels for anyone.
                for p2 in self.players.keys():
                    p2.scoreDirty = True

    def preloadPrevPainting(self, dir, posterData, imgData):
        """ Preloads a winning art painting from the previous round
        onto this wall. """

        p = PNMImage()
        p.read(StringStream(imgData), Globals.ImageFormat)
        with self.paintedLock:
            self.painted[dir] = p

        if posterData[0]:
            self.posterDir = dir
            self.posterData = posterData


    def updatePosterData(self, posterData):
        assert self.posterDir
        self.posterData = posterData

        self.sendUpdate('setPoster', [self.posterDir, self.posterData])

