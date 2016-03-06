#! /usr/bin/env python

usageText = """
Usage:

  %(prog)s [opts]

Options:

  -s Run a server
  -a Run an AI
  -c Run a client
  -r name
     Run a robot client

  -t Don't run threaded network

  -p [server:][port]
     game server and/or port number to contact

  -l output.log
     optional log filename

If no options are specified, the default is to run a client."""

import sys
import getopt
import os
import Globals
import direct
from pandac.PandaModules import *

def usage(code, msg = ''):
    print >> sys.stderr, usageText % {'prog' : os.path.split(sys.argv[0])[1]}
    print >> sys.stderr, msg
    sys.exit(code)

try:
    opts, args = getopt.getopt(sys.argv[1:], 'sacr:tp:l:h')
except getopt.error, msg:
    usage(1, msg)

runServer = False
runAI = False
runClient = False
runRobot = False
robotName = 'robot'
logFilename = None
threadedNet = True

for opt, arg in opts:
    if opt == '-s':
        runServer = True
    elif opt == '-a':
        runAI = True
    elif opt == '-c':
        runClient = True
    elif opt == '-r':
        runRobot = True
        robotName = arg
    elif opt == '-t':
        threadedNet = False
    elif opt == '-p':
        if ':' in arg:
            Globals.ServerHost, arg = arg.split(':', 1)
        if arg:
            Globals.ServerPort = int(arg)
    elif opt == '-l':
        logFilename = Filename.fromOsSpecific(arg)
        
    elif opt == '-h':
        usage(0)
    else:
        print 'illegal option: ' + flag
        sys.exit(1)

if logFilename:
    # Set up Panda's notify output to write to the indicated file.
    mstream = MultiplexStream()
    mstream.addFile(logFilename)
    mstream.addStandardOutput()
    Notify.ptr().setOstreamPtr(mstream, False)

    # Also make Python output go to the same place.
    sw = StreamWriter(mstream, False)
    sys.stdout = sw
    sys.stderr = sw

    # Since we're writing to a log file, turn on timestamping.
    loadPrcFileData('', 'notify-timestamp 1')

if not runServer and not runAI and not runClient and not runRobot:
    runClient = True
    #runAI = True
    #runServer = True

if not runClient:
    # Don't open a graphics window on the server.  (Open a window only
    # if we're running a normal client, not one of the server
    # processes.)
    loadPrcFileData('', 'window-type none\naudio-library-name null')

from direct.directbase.DirectStart import *
if runServer:
    from TagServerRepository import TagServerRepository
    base.server = TagServerRepository(threadedNet = threadedNet)

if runAI:
    from TagAIRepository import TagAIRepository
    base.air = TagAIRepository(threadedNet = threadedNet)

if runRobot:
    from TagClientRepository import TagClientRepository
    from RobotPlayer import RobotPlayer
    base.w = TagClientRepository(playerName = robotName, threadedNet = False)
    base.w.robot = RobotPlayer(base.w)

elif runClient:
    from TagClientRepository import TagClientRepository
    base.w = TagClientRepository()

run()

