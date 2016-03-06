from direct.distributed.DistributedObject import DistributedObject
from pandac.PandaModules import *

class Maze(DistributedObject):
    def __init__(self, cr):
        DistributedObject.__init__(self, cr)

        self.xsize = 0
        self.ysize = 0
        self.numWalls = 0
        
    def announceGenerate(self):
        DistributedObject.announceGenerate(self)

    def disable(self):
        DistributedObject.disable(self)

    def setSize(self, xsize, ysize):
        self.xsize = xsize
        self.ysize = ysize
        
    def setNumWalls(self, numWalls):
        self.numWalls = numWalls
