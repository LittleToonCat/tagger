#!/usr/bin/env python

usageText = """
Usage:

  %(prog)s [opts]

Options:

  -s Run a server

  -a baseChannel
     Run an AI

  -u Run an UD

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
    opts, args = getopt.getopt(sys.argv[1:], 'uacr:tp:l:h')
except getopt.error, msg:
    usage(1, msg)

runAI = False
runUD = False
runClient = False
runRobot = False
robotName = 'robot'
logFilename = None
threadedNet = True

for opt, arg in opts:
    if opt == "-u":
        runUD = True
    elif opt == '-a':
        runAI = True
        serverId = 402000
        if arg:
            baseChannel = arg
        else:
            baseChannel = 101000000
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
        print 'illegal options: ' + flag
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

if not runAI and not runClient and not runRobot and not runUD:
    runClient = True
    #runAI = True

if not runClient:
    # Don't open a graphics window on the server.  (Open a window only
    # if we're running a normal client, not one of the server
    # processes.)
    loadPrcFileData('', 'window-type none\naudio-library-name null')

from direct.directbase.DirectStart import *

if runAI:
    from TagAIRepository import TagAIRepository
    base.air = TagAIRepository(baseChannel, serverId, threadedNet = threadedNet)

if runUD:
    from TagUDRepository import TagUDRepository
    base.air = TagUDRepository(threadedNet = threadedNet)

if runRobot:
    from TagClientRepository import TagClientRepository
    from RobotPlayer import RobotPlayer
    base.w = TagClientRepository(playerName = robotName, threadedNet = False)
    base.w.robot = RobotPlayer(base.w)

elif runClient:
    from TagClientRepository import TagClientRepository
    base.w = TagClientRepository()

run()

