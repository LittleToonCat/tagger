from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.distributed.ClockDelta import globalClockDelta
from pandac.PandaModules import *
from MazeAI import MazeAI
import Globals
import random
import math

class TagGameAI(DistributedObjectAI):

    notify = directNotify.newCategory("TagGameAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.gameActive = True
        self.winners = []
        self.artPaintings = []
        self.nextGameId = 0
        self.timeout = globalClock.getFrameTime() + Globals.GameLengthSeconds
        self.expireTask = taskMgr.doMethodLater(Globals.GameLengthSeconds, self.expireGame, 'expireGame')
        self.deleteGameTask = None

        # Get a unique zoneId to put game objects (like the players)
        # in.
        self.objZone = self.air.zoneAllocator.allocate()

        self.maxNumPlayers = 0

        # Player ID's in the game.
        self.playerIds = []

        # Player ID's about to join the game.
        self.waitingIds = []

        # Mapping of player url -> server url for player posters.
        self.playerPosterMap = {}

        self.accept('newPlayer', self.newPlayer)
        self.accept('deletePlayer', self.deletePlayer)

    def generateMaze(self, playerIds, prevMaze = None):
        """ Generate a maze for this game. """

        self.maze = MazeAI(self.air, self.doId)
        self.air.createDistributedObject(
            distObj = self.maze, zoneId = self.objZone)

        # How many players are we basing this maze on?
        numPlayers = len(playerIds)
        mazeSize = max(numPlayers * Globals.MazeSquaresPerPlayer, Globals.MazeMinSize)
        xsize = math.sqrt(mazeSize)

        # Expand or contract the width of the maze by up to 33%, so
        # it's not always square.
        if random.choice([True, False]):
            xsize += xsize * random.uniform(0, 0.33)
        else:
            xsize -= xsize * random.uniform(0, 0.33)
            
        xsize = int(math.floor(xsize + 0.5))
        ysize = int(math.floor(mazeSize / xsize + 0.5))

        self.mazeId = self.maze.doId

        self.maze.generateMaze(xsize, ysize, prevMaze = prevMaze)

    def setupPlayerPoster(self, player, url, posterData):
        """ Copies the player's posterData to the posterData list to
        store in the maze, so we can distribute local poster images to
        the players in the game.  Returns the modified URL. """

        try:
            i = int(URLSpec(url).getPath()[1:])
        except ValueError:
            return None

        try:
            data = player.posterData[i]
        except IndexError:
            return None

        if data in posterData:
            i = posterData.index(data)
        else:
            i = len(posterData)
            posterData.append(data)
        newUrl = 'maze://%s/%s' % (self.maze.doId, i)
        self.playerPosterMap[url] = newUrl

        return newUrl
        

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)

    def delete(self):
        self.air.zoneAllocator.free(self.objZone)
        self.objZone = None

        for playerId in self.playerIds[:]:
            player = self.air.doId2do.get(playerId, None)
            if player:
                player.game = None
        self.air.timeManager.chooseSuggestedGame(self.doId)

        DistributedObjectAI.delete(self)

    def getNumPlayers(self):
        return len(self.playerIds)

    def getMazeId(self):
        return self.mazeId

    def newPlayer(self, player):
        """ A new player has just joined the world: is he in this
        game? """
        if player.gameId == self.doId and player.doId in self.waitingIds:
            player.game = self
            self.waitingIds.remove(player.doId)
            self.playerIds.append(player.doId)
            self.maxNumPlayers = max(self.maxNumPlayers, len(self.playerIds))
            self.sendUpdate('setNumPlayers', [len(self.playerIds)])

            self.notify.info("player %s joined game %s, %s in game" % (player.name, self.doId, len(self.playerIds)))

            # Award any paint points for carried-forward art paintings.
            prevCells = self.maze.prevPlayers.get(player.color, [])
            if prevCells:
                del self.maze.prevPlayers[player.color]
                for cell, dir in prevCells:
                    cell.markPrevUser(player, dir)

            # Assign a cell for the poster.
            self.maze.chooseRandomPosterCell(player)
        

    def deletePlayer(self, player):
        """ A player has just left the world. """
        if player.doId in self.playerIds:
            self.playerIds.remove(player.doId)
            player.game = None
            self.sendUpdate('setNumPlayers', [len(self.playerIds)])

            self.notify.info("player %s left game %s, %s in game" % (player.name, self.doId, len(self.playerIds)))

            if player.posterCell:
                player.posterCell.updatePosterData(('', 0))
                player.posterCell.posterPlayerId = None
                player.posterCell = None

            if not self.playerIds:
                # When the last player leaves a game, shut it down.
                self.__deleteGame()

    def getTimeout(self):
        return globalClockDelta.localToNetworkTime(self.timeout)

    def getObjZone(self):
        return self.objZone

    def expireGame(self, task):
        """ The game has expired.  End it now. """
        self.expireTask = None
        self.endGame()

    def endGame(self):
        if self.expireTask:
            taskMgr.remove(self.expireTask)
            self.expireTask = None

        if not self.gameActive:
            return
        
        self.gameActive = False

        self.maze.chooseArtPaintings(self)

        playerList = []
        for playerId in self.playerIds:
            player = self.air.doId2do[playerId]
            playerList.append(player)

        # First, randomize the list, so ties come out in random order.
        random.shuffle(playerList)

        # Then sort it in decreasing order by score.
        playerList.sort(key = lambda p: -p.score)
        self.winners = playerList[:5]

        self.nextGameId = 0
        if self.playerIds:
            self.notify.info("%s winner is %s, %s" % (self.doId, self.winners[0].name, self.winners[0].score))

            # Immediately start up a new game.  Assume the players in this
            # game will be joining the next game.
            self.nextGameId = self.air.allocateDoId()
            taskMgr.add(self.air.makeGame, 'makeGame',
                        extraArgs = [self.nextGameId, self.playerIds, self.maze])
            
        else:
            self.notify.info("%s ended with no players" % (self.doId))

        self.sendUpdate('setWinners', [self.gameActive, self.winners, self.maze.artPaintings, self.nextGameId])
        self.air.timeManager.chooseSuggestedGame(self.doId)

        # And, after a period of time, remove this game object.
        self.deleteGameTask = taskMgr.doMethodLater(
            Globals.GameAfterlifeSeconds, self.__deleteGame,
            'deleteGame')

    def __deleteGame(self, task = None):
        if self.expireTask:
            taskMgr.remove(self.expireTask)
            self.expireTask = None
        if self.deleteGameTask:
            taskMgr.remove(self.deleteGameTask)
            self.deleteGameTask = None

        if self.isDeleted():
            return
            
        self.maze.deleteMaze()
        self.air.sendDeleteMsg(self.maze.doId)
        self.air.sendDeleteMsg(self.doId)
        self.air.games.remove(self)
        self.ignoreAll()

    def getWinners(self):
        return (self.gameActive, self.winners, self.artPaintings, self.nextGameId)

    def requestJoin(self):
        """ Called by a new client to join the game. """

        playerId = self.air.getAvatarIdFromSender()

        if not self.gameActive or len(self.playerIds) + len(self.waitingIds) >= Globals.MaxPlayersPerGame:
            # Not allowing more joiners right now.
            self.sendUpdateToAvatarId(playerId, 'setJoin', [False])
            self.air.timeManager.chooseSuggestedGame(self.doId)
            return

        self.waitingIds.append(playerId)
        self.sendUpdateToAvatarId(playerId, 'setJoin', [True])

        if len(self.playerIds) + len(self.waitingIds) >= Globals.WantedPlayersPerGame:
            # This should no longer be the suggested game.
            self.air.timeManager.chooseSuggestedGame(self.doId)
            
    def setPoster(self, posterData):
        """ Sent from the client to tell the AI its current poster
        data.  Normally this is sent only when starting a new game,
        since the poster data is normally sent through the web
        interface initially. """

        playerId = self.air.getAvatarIdFromSender()
        if playerId in self.playerIds:
            player = self.air.doId2do[playerId]
            player.setPoster(posterData)
