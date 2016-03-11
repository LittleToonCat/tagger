from direct.distributed.DistributedObjectUD import DistributedObjectUD
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.MsgTypes import *

class TagAvatarManagerUD(DistributedObjectUD):

    notify = directNotify.newCategory("TagAvatarManagerUD")

    def __init__(self, air):
        DistributedObjectUD.__init__(self, air)
        self.air = air

    def requestAccess(self):
        clientId = self.air.getMsgSender()
        
        self.air.setClientState(clientId, 2)

        dg = PyDatagram()
        dg.addServerHeader(clientId, self.air.ourChannel, CLIENTAGENT_OPEN_CHANNEL)
        dg.addChannel(self.GetPuppetConnectionChannel(clientId))
        self.air.send(dg)

        self.sendUpdateToChannel(clientId, 'accessResponse', [True])