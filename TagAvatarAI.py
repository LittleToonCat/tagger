from direct.distributed.DistributedSmoothNodeAI import DistributedSmoothNodeAI
from pandac.PandaModules import *
from direct.actor.Actor import Actor
import Globals

class TagAvatarAI(DistributedSmoothNodeAI):
    def __init__(self, air):
        DistributedSmoothNodeAI.__init__(self, air)

        # A dictionary of player -> count, showing the players, other
        # than the avatar's own player, who have paint on this avatar.
        self.paintedOnMe = {}

        self.paint = ''

        self.playerId = 0

        # Which cell the avatar appears to be standing in.
        self.cellLocation = None

        self.accept('deletePlayer', self.deletePlayer)

    def setPlayerId(self, playerId):
        self.playerId = playerId

    def d_setPlayerId(self, playerId):
        self.sendUpdate('setPlayerId', [playerId])

    def b_setPlayerId(self, playerId):
        self.d_setPlayerId(playerId)
        self.setPlayerId(playerId)

    def getPlayerId(self):
        return self.playerId

    def getPaint(self):
        return self.paint

    def delete(self):
        messenger.send('deleteAvatar', [self])
        
        DistributedSmoothNodeAI.delete(self)

    def deletePlayer(self, player):
        """ This message is sent whenever any TagPlayerAI is deleted. """
        if player in self.paintedOnMe:
            del self.paintedOnMe[player]
        if self.playerId == player.doId:
            self.requestDelete()

    def announceGenerate(self):
        DistributedSmoothNodeAI.announceGenerate(self)

    def setX(self, *args):
        DistributedSmoothNodeAI.setX(self, *args)
        self.tellZone()

    def setPos(self, *args):
        DistributedSmoothNodeAI.setPos(self, *args)
        self.tellZone()

    def setPosHpr(self, *args):
        DistributedSmoothNodeAI.setPosHpr(self, *args)
        self.tellZone()

    def tellZone(self):
        """ Tell the avatar what zone he should be in, and what zones
        he can see.  We allow the client itself to actually make the
        zone request, since that's the way the DistributedObject
        system is set up.  Need to reevaluate this. """

        player = self.air.doId2do.get(self.playerId, None)
        if not player or not player.game:
            return

        sx = int(self.getX() / Globals.MazeScale)
        sy = int(self.getY() / Globals.MazeScale)

        maze = player.game.maze
        sx = min(max(sx, 0), maze.xsize - 1)
        sy = min(max(sy, 0), maze.ysize - 1)

        cell = maze.map[sy][sx]
        if cell != self.cellLocation:
            self.cellLocation = cell
            player = self.air.doId2do.get(self.playerId, None)
            if player:
                player.cellLocation = cell
            self.sendUpdate('setZoneInformation', [cell.zoneId, list(cell.expandedZoneIds)])
        
