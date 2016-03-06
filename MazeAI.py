from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.showbase.RandomNumGen import RandomNumGen
from pandac.PandaModules import *
import Globals
from CellAI import CellAI
import time
import random
import math

class MazeAI(DistributedObjectAI):

    notify = directNotify.newCategory("MazeAI")

    TurnChance = 75
    ForkChance = 20
    StopChance = 10

    def __init__(self, air, gameId):
        DistributedObjectAI.__init__(self, air)

        self.gameId = gameId
        self.xsize = 0
        self.ysize = 0
        self.numWalls = 0
        self.map = None
        self.root = None

        self.prevPlayers = {}

    def getSize(self):
        return self.xsize, self.ysize

    def getNumWalls(self):
        return self.numWalls

    def deleteMaze(self):
        if self.map:
            for row in self.map:
                for cell in row:
                    self.air.sendDeleteMsg(cell.doId)
                    self.air.zoneAllocator.free(cell.zoneId)

    def generateMaze(self, xsize, ysize, 
                     prevMaze = None, seed = None):
        if seed is None:
            seed = int(time.time())
        self.random = RandomNumGen(seed)

        # Delete the old maze, if any
        self.deleteMaze()

        self.xsize = xsize
        self.ysize = ysize
        self.map = []
        for sy in range(self.ysize):
            row = []
            for sx in range(self.xsize):
                zoneId = self.air.zoneAllocator.allocate()
                cell = self.air.createDistributedObject(
                    className = 'CellAI', zoneId = zoneId)
                cell.setGeometry(Globals.AllDirs, sx, sy)
                row.append(cell)
            self.map.append(row)

        # Start by choosing a random square and a random direction.
        self.numSquares = self.xsize * self.ysize - 1
        self.paths = []
        nextStep = self.__findEmptySquare()
        self.paths.append(nextStep)
        while self.numSquares > 0:
            self.__generateMazeSteps()

        # Count up the number of walls.
        walls = []
        for row in self.map:
            for cell in row:
                walls += cell.getWalls()
        self.numWalls = len(walls)
        
        random.shuffle(walls)

        if prevMaze:
            # Put our previous art paintings up on the walls,
            # including any poster data.
            for i in range(len(prevMaze.artPaintings)):
                dir, name, color, posterData, imgData = prevMaze.artPaintings[i]
                sx, sy, wallDir = walls[i]
                cell = self.map[sy][sx]
                while posterData[0] and cell.posterDir:
                    # We've already placed a poster in this cell.  Go
                    # on to the next one.
                    del walls[i]
                    sx, sy, wallDir = walls[i]
                    cell = self.map[sy][sx]
                
                if dir & Globals.AllDirs != 0:
                    # It's not a floor or ceiling, so use the wall we
                    # picked, instead of the wall it was on in the
                    # previous maze.
                    dir = wallDir
                else:
                    # It is a floor or ceiling, so keep it there.
                    pass

                cell.preloadPrevPainting(dir, posterData, imgData)

                # Record the player's color so we can identify him
                # when he comes back in and give him the points for
                # this paint immediately.
                self.prevPlayers.setdefault(color, []).append((cell, dir))

##         # Temp hack for debugging.
##         painted = PNMImage()
##         painted.read('paint.rgb')
##         for sx, sy, dir in walls:
##             cell = self.map[sy][sx]
##             for dir in Globals.AllDirsList:
##                 if cell.bits & dir:
##                     cell.painted[dir] = PNMImage(painted)

        self.drawMap()
        self.determineVisibility()

    def getPosterData(self):
        return self.posterData
        
    def determineVisibility(self):
        """ Determines which cells can be seen from which other
        cells, based on straight-line visibility. """

        self.visCollWalls = self.makeCollisionWalls()
        self.visTrav = CollisionTraverser('visTrav')
        self.visQueue = CollisionHandlerQueue()
        self.visNode = CollisionNode('visNode')
        self.visNP = self.visCollWalls.attachNewNode(self.visNode)
        self.visNP.setCollideMask(0)
        self.visTrav.addCollider(self.visNP, self.visQueue)

        for sy in range(self.ysize):
            self.notify.info("%s determineVisibility: %d%%" % (
                self.gameId, 100.0 * sy / self.ysize))
            row = self.map[sy]
            for cell in row:
                self.__determineVisibilityForCell(cell, 1, Globals.AllDirs)

        # Now build the expanded visibility, including neighbor
        # visibility, for smooth transitions.
        for row in self.map:
            for cell in row:
                self.__expandVisibilityForCell(cell)
        self.notify.info("%s done" % (self.gameId))

    def __expandVisibilityForCell(self, cell):
        """ Build cell.expandedZoneIds, representing the union of
        visibleZoneIds for the cell and all of its eight neigbors. """

        cell.expandedZoneIds = set()
        for sy in range(max(cell.sy - 1, 0), min(cell.sy + 2, self.ysize)):
            for sx in range(max(cell.sx - 1, 0), min(cell.sx + 2, self.xsize)):
                c2 = self.map[sy][sx]
                cell.expandedZoneIds |= c2.visibleZoneIds
        assert cell.expandedZoneIds | cell.visibleZoneIds == cell.expandedZoneIds

    def __determineVisibilityForCell(self, cell, radius, dirBits):
        """ Determines the set of visible cells that can be seen from
        this cell, for the given radius. """
        cell.visibleZoneIds.add(cell.zoneId)
        
        numVisible = 0
        nextDirs = 0
        for i in range(-radius, radius):
            if dirBits & Globals.North:
                # North wall
                sx = cell.sx - i
                sy = cell.sy + radius
                if self.__checkCellVisibility(cell, sx, sy):
                    nextDirs |= Globals.North

            if dirBits & Globals.East:
                # East wall
                sx = cell.sx + radius
                sy = cell.sy + i
                if self.__checkCellVisibility(cell, sx, sy):
                    nextDirs |= Globals.East

            if dirBits & Globals.South:
                # South wall
                sx = cell.sx + i
                sy = cell.sy - radius
                if self.__checkCellVisibility(cell, sx, sy):
                    nextDirs |= Globals.South

            if dirBits & Globals.West:
                # West wall
                sx = cell.sx - radius
                sy = cell.sy - i
                if self.__checkCellVisibility(cell, sx, sy):
                    nextDirs |= Globals.West

        if nextDirs:
            # Recursively check the higher radius
            self.__determineVisibilityForCell(cell, radius + 1, nextDirs)

    def __checkCellVisibility(self, source, sx, sy):
        """ Looks up the target cell, and returns true if the target
        can be seen from source, false otherwise. """
        if sx < 0 or sx >= self.xsize or sy < 0 or sy >= self.ysize:
            # Not even a real cell.
            return False
        target = self.map[sy][sx]
        if not self.__doVisibilityTest(source, target):
            return False

        # target is visible.
        source.visibleZoneIds.add(target.zoneId)
        return True
            
    def __doVisibilityTest(self, source, target):
        """ Returns true if target can be seen from source, false
        otherwise. """

        # We naively check 16 lines: each of the four corners of
        # target from the four corners of source.  If any of them has
        # a line of sight--that is, any one of them does *not*
        # generate a collision event--we're in.

        # We use a point just inside each corner, so we don't have to
        # deal with ambiguities at the precise corner.

        self.visQueue.clearEntries()
        self.visNode.clearSolids()

        segs = {}
        for ax, ay in [(source.sx + 0.1, source.sy + 0.1),
                       (source.sx + 0.9, source.sy + 0.1),
                       (source.sx + 0.9, source.sy + 0.9),
                       (source.sx + 0.1, source.sy + 0.9)]:
            for bx, by in [(target.sx + 0.1, target.sy + 0.1),
                           (target.sx + 0.9, target.sy + 0.1),
                           (target.sx + 0.9, target.sy + 0.9),
                           (target.sx + 0.1, target.sy + 0.9)]:
                seg = CollisionSegment(ax, ay, 0.5, bx, by, 0.5)
                self.visNode.addSolid(seg)
                segs[seg] = True

        self.visTrav.traverse(self.visCollWalls)

        # Now see which segments detected a collision.
        for entry in self.visQueue.getEntries():
            seg = entry.getFrom()
            if seg in segs:
                del segs[seg]

        # If any are left, we've got a line of sight.
        if segs:
            return True

        # If none are left, we're blocked.
        return False

    def __generateMazeSteps(self):
        """ Moves all of the active paths forward one step. """

        if not self.paths:
            # Ran out of open paths.  Go find a likely square to pick
            # up from again.
            nextStep = self.__findEmptySquare()
            self.paths.append(nextStep)

        paths = self.paths
        self.paths = []
        for sx, sy, dir in paths:
            self.__generateMazeOneStep(sx, sy, dir)

    def __generateMazeOneStep(self, sx, sy, dir):
        """ Moves this path forward one step. """

        if self.random.randint(0, 99) < self.StopChance:
            # Abandon this path.
            return

        numNextSteps = 1
        while numNextSteps < 4 and self.random.randint(0, 99) < self.ForkChance:
            # Consider a fork.
            numNextSteps += 1

        nextDirs = Globals.AllDirsList[:]
        nextDirs.remove(dir)
        self.random.shuffle(nextDirs)

        if self.random.randint(0, 99) < self.TurnChance:
            # Consider a turn.  Put the current direction at the end.
            nextDirs.append(dir)
        else:
            # Don't consider a turn.  Put the current direction at the
            # front.
            nextDirs = [dir] + nextDirs

        for dir in nextDirs:
            nextStep = self.__makeStep(sx, sy, dir)
            if nextStep:
                # That step was valid, save the current path for next
                # pass.
                self.numSquares -= 1
                self.paths.append(nextStep)
                numNextSteps -= 1
                if numNextSteps == 0:
                    return
                
            # Try the next direction.

        # Couldn't go anywhere else.  We're done.
        return
                
    def __makeStep(self, sx, sy, dir):
        """ Attempts to move this path forward in the indicated
        direction.  Returns the new sx, sy, dir if successful, or None
        on failure. """
        if dir == Globals.South:
            if sy == 0:
                return None
            if self.map[sy][sx].bits & Globals.South == 0:
                return None
            if self.map[sy - 1][sx].bits != Globals.AllDirs:
                return None
            self.map[sy][sx].bits &= ~Globals.South
            self.map[sy - 1][sx].bits &= ~Globals.North
            return (sx, sy - 1, dir)

        elif dir == Globals.West:
            if sx == 0:
                return None
            if self.map[sy][sx].bits & Globals.West == 0:
                return None
            if self.map[sy][sx - 1].bits != Globals.AllDirs:
                return None
            self.map[sy][sx].bits &= ~Globals.West
            self.map[sy][sx - 1].bits &= ~Globals.East
            return (sx - 1, sy, dir)

        elif dir == Globals.North:
            if sy == self.ysize - 1:
                return None
            if self.map[sy][sx].bits & Globals.North == 0:
                return None
            if self.map[sy + 1][sx].bits != Globals.AllDirs:
                return None
            self.map[sy][sx].bits &= ~Globals.North
            self.map[sy + 1][sx].bits &= ~Globals.South
            return (sx, sy + 1, dir)

        elif dir == Globals.East:
            if sx == self.xsize - 1:
                return None
            if self.map[sy][sx].bits & Globals.East == 0:
                return None
            if self.map[sy][sx + 1].bits != Globals.AllDirs:
                return None
            self.map[sy][sx].bits &= ~Globals.East
            self.map[sy][sx + 1].bits &= ~Globals.West
            return (sx + 1, sy, dir)

        assert False

    def __findEmptySquare(self):
        """ Finds an empty square next door to a non-empty square, and
        starts a new path. """

        if self.numSquares == self.xsize * self.ysize - 1:
            # All squares are still empty.
            sx = self.random.randint(0, self.xsize - 1)
            sy = self.random.randint(0, self.ysize - 1)
            dir = self.random.choice(Globals.AllDirsList)
            return (sx, sy, dir)

        # First, get the map squares in random order.
        ylist = list(range(self.ysize))
        xlist = list(range(self.xsize))
        self.random.shuffle(ylist)
        self.random.shuffle(xlist)

        for sy in ylist:
            for sx in xlist:
                if self.map[sy][sx].bits != Globals.AllDirs:
                    continue
                if sy > 0 and self.map[sy - 1][sx].bits != Globals.AllDirs:
                    return (sx, sy - 1, Globals.North)
                elif sy < self.ysize - 1 and self.map[sy + 1][sx].bits != Globals.AllDirs:
                    return (sx, sy + 1, Globals.South)
                elif sx > 0 and self.map[sy][sx - 1].bits != Globals.AllDirs:
                    return (sx - 1, sy, Globals.East)
                elif sx < self.xsize - 1 and self.map[sy][sx + 1].bits != Globals.AllDirs:
                    return (sx + 1, sy, Globals.West)

        self.drawMap()
        assert False

    def makeCollisionWalls(self):
        """ Creates and returns a scene graph that contains a
        collision wall for each West and South wall in the maze, for
        the purposes of determining visibility. """
        root = self.__makeCollisionQuadtree(0, 0, self.xsize, self.ysize)
        root.flattenLight()
        return root

    def __makeCollisionQuadtree(self, ax, ay, bx, by):
        # We recursively create a quadtree hierarchy, in an attempt to
        # ensure the collisions remain scalable with very large maps.
        xsize = bx - ax
        ysize = by - ay
        if xsize > 1 or ysize > 1:
            # Recurse.
            root = NodePath('%s_%s__%s_%s' % (ax, ay, bx, by))
            xsize = max((xsize + 1) / 2, 1)
            ysize = max((ysize + 1) / 2, 1)
            py = ay
            while py < by:
                px = ax
                while px < bx:
                    np = self.__makeCollisionQuadtree(px, py, min(px + xsize, bx), min(py + ysize, by))
                    np.reparentTo(root)
                    px += xsize
                py += ysize
            return root

        # One cell.  Handle it.
        node = CollisionNode('%s_%s' % (ax, ay))
        cell = self.map[ay][ax]
        if cell.bits & Globals.West:
            node.addSolid(CollisionPolygon(Point3(0, 0, 0), Point3(0, 1, 0),
                                           Point3(0, 1, 1), Point3(0, 0, 1)))
        if cell.bits & Globals.South:
            node.addSolid(CollisionPolygon(Point3(1, 0, 0), Point3(0, 0, 0),
                                           Point3(0, 0, 1), Point3(1, 0, 1)))
        np = NodePath(node)
        np.setPos(cell.sx, cell.sy, 0)
        return np

    def drawMap(self):
        line = '+'
        for xi in range(self.xsize):
            line += '---+'
        print line

        for yi in range(self.ysize - 1, -1, -1):
            row = self.map[yi]
            line = '|'
            for cell in row:
                if cell.bits & Globals.East:
                    line += '   |' 
                else:
                    line += '    ' 
            print line
            line = '+'
            for cell in row:
                if cell.bits & Globals.South:
                    line += '---+'
                else:
                    line += '   +'
            print line
        
    def makeGeom(self):
        """ Generates a set of renderable geometry. """

        if self.root:
            self.root.removeNode()

        self.root = NodePath('root')
        for sy in range(self.ysize):
            geomRow = []
            for sx in range(self.xsize):
                nodeGeom = self.map[sy][sx].makeGeomCell(sx, sy)
                nodeGeom.reparentTo(self.root)
                geomRow.append(nodeGeom)
        return self.root
        

    def chooseArtPaintings(self, game):
        """ Give score bonuses to the players with the 3 "best" art
        paintings. """

        # Now score each wall painting.
        anyPosters = False
        artPaintings = []
        for row in self.map:
            for cell in row:
                for dir, score in cell.artScore.items():
                    # Normally, the player with the most paint gets
                    # the bonus for the art painting.
                    player = cell.wonPlayers.get(dir, None)

                    # But if there's a poster on this wall, the player
                    # who owns the poster gets that bonus instead.
                    if dir == cell.posterDir:
                        anyPosters = True
                        pp = self.cr.doId2do.get(cell.posterPlayerId)
                        if pp:
                            player = pp
                        
                    p = cell.painted.get(dir, None)
                    if p and player and not player.isDeleted():
                        artPaintings.append((-score, cell, dir, player, p))

        # Sort the list so that the highest scores appear at the top.
        artPaintings.sort()

        self.artPaintings = []

        # We must have at least one poster in the list.
        needPoster = True

        # Unless there are no posters with paint on them, in which
        # case never mind.
        if not anyPosters:
            needPoster = False
        
        for i in range(len(artPaintings)):
            score, cell, dir, player, p = artPaintings[i]

            if dir == cell.posterDir:
                needPoster = False

            if len(self.artPaintings) == len(Globals.ArtPaintingBonus) - 1 and needPoster:
                # If we've reached the end of the list and we haven't
                # yet met our poster need, don't consider any
                # art paintings that aren't made on posters.
                continue

            bonus = Globals.ArtPaintingBonus[len(self.artPaintings)]
            player.artBonus += bonus
            player.score += bonus
            
            data = StringStream()
            p.write(data, Globals.ImageFormat)
            imgData = data.getData()

            posterData = ('', 0)
            if dir == cell.posterDir:
                posterData = cell.posterData
            
            self.artPaintings.append((dir, player.name, player.color, posterData, imgData))
            if len(self.artPaintings) >= len(Globals.ArtPaintingBonus):
                break

    def chooseRandomPosterCell(self, player):
        """ Selects a cell without a poster already applied, and
        applies this player's poster to it. """

        cells = []
        for row in self.map:
            cells += row[:]

        while True:
            if not cells:
                print "No cell available for user's poster."
                return
            
            cell = random.choice(cells)
            cells.remove(cell)
            if cell.posterDir:
                # Already taken.
                continue
            if cell.bits & Globals.AllDirs == 0:
                # No walls to hold a poster.
                continue
            break

        dirs = Globals.AllDirsList[:]
        while True:
            dir = random.choice(dirs)
            if cell.bits & dir:
                break
            dirs.remove(dir)

        cell.posterDir = dir
        cell.posterPlayerId = player.doId
        player.posterCell = cell

        print "posterData = %s, %s" % (len(player.posterData[0]), player.posterData[1])
        cell.updatePosterData(player.posterData)

        
    
