from direct.distributed.ServerRepository import ServerRepository
import Globals

class TagServerRepository(ServerRepository):
    def __init__(self, threadedNet = True):
        tcpPort = base.config.GetInt('server-port', Globals.ServerPort)
        hostname = base.config.GetString('server-host', Globals.ServerHost)
        dcFileNames = ['direct.dc', 'tagger.dc']
        
        ServerRepository.__init__(self, tcpPort, serverAddress = hostname,
                                  dcFileNames = dcFileNames,
                                  threadedNet = threadedNet)

        # Need at least 32 bits to send big picture packets.
        self.setTcpHeaderSize(4)

        # Allow some time for other processes.
        base.setSleep(0.01)
        
