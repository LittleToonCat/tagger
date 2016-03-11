from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal

class TagAvatarManager(DistributedObjectGlobal):

    def requestAccess(self):
        print 'requestAccess'
        self.sendUpdate('requestAccess', [])

    def accessResponse(self, success):
        print 'accessResponse %d' % success
        messenger.send('accessResponse', [success])