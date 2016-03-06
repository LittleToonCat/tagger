from direct.distributed.TimeManager import TimeManager
from pandac.PandaModules import *
import Globals

class TagManager(TimeManager):
    """ This class subclasses TimeManager, to provide some global
    controls specific to this game. """
    
    def __init__(self, cr):
        TimeManager.__init__(self, cr)
        self.suggestedGameId = 0

    def d_requestNewGame(self):
        """ Request that the AI spin up a new game for us to join. """
        self.sendUpdate('requestNewGame', [])
        
    def setSuggestedGameId(self, gameId):
        self.suggestedGameId = gameId
