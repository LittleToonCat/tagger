from direct.distributed.TimeManagerAI import TimeManagerAI
from pandac.PandaModules import *
import Globals

class TagManagerAI(TimeManagerAI):
    """ This class subclasses TimeManagerAI, to provide some global
    controls specific to this game. """

    notify = directNotify.newCategory("TagManagerAI")
    
    def __init__(self, air):
        TimeManagerAI.__init__(self, air)

        self.suggestedGameId = 0

    def requestNewGame(self):
        """ This message is sent by the client, to request that the AI
        spin up a new game.  The request may or may not be honored,
        according to the number of available games we have. """

        avId = self.air.getAvatarIdFromSender()
        self.notify.info("New game requested by %s" % (avId))

        availableSpaces = []
        for game in self.air.games:
            if game.gameActive:
                spaces = max(Globals.MaxPlayersPerGame - len(game.playerIds) - len(game.waitingIds), 0)
                availableSpaces.append(spaces)
        if sum(availableSpaces) > 5:
            # If we've got room for at least five more players in our
            # existing games, don't respect this request.
            print "games available: %s = %s" % (availableSpaces, sum(availableSpaces))
            return

        gameId = self.air.allocateDoId()
        self.air.makeGame(doId = gameId)
        self.b_setSuggestedGameId(gameId)

    def chooseSuggestedGame(self, origGameId):
        """ Chooses the best game to suggest players to join next.
        This will be the game with the fewest number of players. """
        if self.suggestedGameId != origGameId:
            # No need to change it.
            return
        
        minNumPlayers = None
        gameId = 0
        for game in self.air.games:
            if not game.gameActive:
                continue
            numPlayers = len(game.playerIds) + len(game.waitingIds)
            if minNumPlayers is None or numPlayers < minNumPlayers:
                minNumPlayers = numPlayers
                gameId = game.doId

        self.b_setSuggestedGameId(gameId)

    def b_setSuggestedGameId(self, gameId):
        print "suggesting game %s" % (gameId)
        self.setSuggestedGameId(gameId)
        self.d_setSuggestedGameId(gameId)

    def d_setSuggestedGameId(self, gameId):
        self.sendUpdate('setSuggestedGameId', [gameId])

    def setSuggestedGameId(self, gameId):
        self.suggestedGameId = gameId

    def getSuggestedGameId(self):
        return self.suggestedGameId
    
    
