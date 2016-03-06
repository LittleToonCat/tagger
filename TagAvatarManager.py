from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal

class TagAvatarManager(DistributedObjectGlobal):

    def requestAvatar(self, name):
        print 'requestAvatar: %s' % name
        self.sendUpdate('requestAvatar', [name])