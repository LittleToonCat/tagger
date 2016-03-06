from direct.distributed.DistributedObjectUD import DistributedObjectUD

class TagAvatarManagerUD(DistributedObjectUD):

    notify = directNotify.newCategory("TagAvatarManagerUD")

    def __init__(self, air):
        DistributedObjectUD.__init__(self, air)
        self.air = air

    def requestAvatar(self, name):
        clientId = self.air.getMsgSender()
        print 'Got requestAvatar from %d: %s' % (clientId, name)
        