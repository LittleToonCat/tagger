from direct.distributed.DistributedObjectUD import DistributedObjectUD

class RootObjectUD(DistributedObjectUD):
    def __init__(self, air):
        DistributedObjectUD.__init__(self, air)