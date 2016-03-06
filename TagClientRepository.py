from direct.distributed.ClientRepository import ClientRepository
from direct.gui.DirectGui import *
from direct.showbase.DirectObject import DirectObject
from direct.interval.IntervalGlobal import *
from pandac.PandaModules import *
from TagPlayer import TagPlayer
from TagAvatar import TagAvatar
from PlayerList import PlayerList
from PosterFSM import PosterFSM
import Globals
import Cell
import sys
import random
import math
import os

class TagClientRepository(ClientRepository):

    # Degrees per second of rotation
    rotateSpeed = 90

    # Units per second of motion
    moveSpeed = 8

    taskChain = 'net'

    def __init__(self, playerName = None, threadedNet = True):
        dcFileNames = ['direct.dc', 'tagger.dc']
        
        ClientRepository.__init__(self, dcFileNames = dcFileNames,
                                  connectMethod = self.CM_NET,
                                  threadedNet = threadedNet)

        base.transitions.FadeModelName = 'models/fade'
        
        # Need at least 32 bits to receive big picture packets.
        self.setTcpHeaderSize(4)

        # Allow some time for other processes.  This also allows time
        # each frame for the network thread to run.
        base.setSleep(0.01)

        # If we're using OpenGL, we can enable shaders.  (DirectX
        # shader support is still kind of spotty, even for simple
        # shaders like these.)
        if base.pipe and base.pipe.getInterfaceName() == 'OpenGL':
            Globals.EnableShaders = True

        self.gotMusic = False
        self.__getMusic()
        
        # For the browse button.
        self.posterDefaultDir = Filename.getHomeDirectory().toOsSpecific()

        # Load a fun font to be the default text font.
        labelFont = loader.loadFont('models/amsterdam.ttf', okMissing = True)
        if labelFont:
            # Make a fuzzy halo behind the font so it looks kind of
            # airbrushy
            labelFont.setOutline(VBase4(0, 0, 0, 1), 2.0, 0.9)
            TextNode.setDefaultFont(labelFont)

        base.disableMouse()
        if base.mouseWatcher:
            mb = ModifierButtons()
            mb.addButton(KeyboardButton.control())
            base.mouseWatcher.node().setModifierButtons(mb)
            base.buttonThrowers[0].node().setModifierButtons(mb)
        taskMgr.setupTaskChain('loadPoster', numThreads = 4,
                               threadPriority = TPLow)
        #taskMgr.setupTaskChain('net', numThreads = 1, threadPriority = TPLow, frameSync = True)

        # Set up a text property called "tag" that renders using the
        # tag font, in white, with a shadow.  This is used for
        # rendering the art-painting awards at the end of the round.
        tpMgr = TextPropertiesManager.getGlobalPtr()
        tp = TextProperties()
        tagFont = loader.loadFont('models/one8seven.ttf', okMissing = True)
        if tagFont:
            tp.setFont(tagFont)
        tp.setTextColor(1, 1, 1, 1)
        tp.setShadow(0.05, 0.05)
        tp.setTextScale(1.5)
        tpMgr.setProperties('tag', tp)

        # If we're running from the web, get the gameInfo block from
        # the HTML tokens.
        self.gameInfo = None
        if base.appRunner:
            gameInfoName = base.appRunner.getToken('gameInfo')
            if gameInfoName:
                self.gameInfo = base.appRunner.evalScript(gameInfoName, needsResponse = True)

            # Expose the changePoster() method.
            base.appRunner.main.changePoster = self.changePoster

        print "self.gameInfo = %s" % (self.gameInfo)

        # Also be prepared to update the web form with the table of
        # players and the local player's score.
        self.playerTable = None
        self.scoreTable = None
        if base.appRunner and base.appRunner.dom:
            self.playerTable = base.appRunner.dom.document.getElementById('playerTable')
            self.scoreTable = base.appRunner.dom.document.getElementById('scoreTable')
        print "self.playerTable = %s, scoreTable = %s" % (self.playerTable, self.scoreTable)

        self.playerList = PlayerList(self.playerTable)
        self.onscreenScoreLeft = None

        # When we join a game, we'll prefer to join *this* game.
        self.nextGameId = 0
        self.chooseGameTask = None
        self.allGames = []

        # No game, no avatar (yet).
        self.robot = None
        self.game = None
        self.player = None
        self.av = None
        self.avCell = None
        self.paintThing = None

        self.keyMap = {}
        for key in Globals.ControlKeys:
            self.keyMap[key] = False

        self.dlnp = render.attachNewNode(DirectionalLight('dlnp'))
        self.dlnp.node().setColor((0.8, 0.8, 0.8, 1))
        render.setLight(self.dlnp)
        self.alnp = render.attachNewNode(AmbientLight('alnp'))
        self.alnp.node().setColor((0.2, 0.2, 0.2, 1))
        render.setLight(self.alnp)

        if base.camera:
            self.dlnp.reparentTo(base.camera)

        # Set up the poster FSM to switch the poster modes.
        self.posterFSM = PosterFSM(base.appRunner)

        # A node to hold all avatars.
        self.avRoot = render.attachNewNode('avRoot')

        # The root of the maze.
        self.mazeRoot = render.attachNewNode('maze')
        if Globals.EnableShaders:
            #self.mazeRoot.setShaderAuto()
            s = loader.loadShader('models/nopaint_normal.sha')
            self.mazeRoot.setShader(s)
            self.mazeRoot.setShaderInput('alight0', self.alnp)
            self.mazeRoot.setShaderInput('dlight0', self.dlnp)

        # Initial poster data.
        self.posterData = ('', 0)
        cvar = ConfigVariableFilename('tag-poster', '')
        filename = cvar.getValue()
        if filename:
            self.readTagPoster(filename)

        # Choose a bright paint color.
        h = random.random()
        s = random.random() * 0.3 + 0.7
        v = random.random() * 0.3 + 0.7
        self.playerColor = self.hsv2rgb(h, s, v)

        # Get the player's name.
        name = playerName
        if not name:
            name = getattr(self.gameInfo, 'name', None)
        if not name:
            name = base.config.GetString('player-name', '')
            
        if name:
            # Use the provided name.
            self.playerName = name
            self.startConnect()

        else:
            # Prompt the user.

            # Start with the wall model in the background.
            wall = loader.loadModel('models/wall')
            wall.reparentTo(base.camera)
            wall.setPos(0, 5, -2.5)
            wall.setScale(10)
            if Globals.EnableShaders:
                wall.setShaderAuto()
            self.nameWall = wall

            c = self.playerColor
            self.nameLabel = DirectLabel(
                text = 'Enter your street name:',
                text_align = TextNode.ALeft,
                text_fg = (c[0], c[1], c[2], 1),
                text_shadow = (0, 0, 0, 1),
                pos = (-0.9, 0, 0.45),
                relief = None,
                scale = 0.2)
            tagFont = loader.loadFont('models/one8seven.ttf')

            cardModel = loader.loadModel('models/nametag_card')
            cardTex = cardModel.findTexture('*')
            self.nameEntry = DirectEntry(
                pos = (-0.9, 0, 0.1),
                focus = True,
                relief = DGG.TEXTUREBORDER,
                frameColor = (c[0], c[1], c[2], 0.6),
                frameTexture = cardTex,
                borderWidth = (0.2, 0.2),
                pad = (0.0, -0.2),
                borderUvWidth = (0.1, 0.1),
                text_font = tagFont,
                width = 12, scale = 0.15,
                command = self.enteredName)

            self.nameButton = DirectButton(
                text = 'Enter game',
                frameColor = (c[0], c[1], c[2], 1),
                scale = 0.15,
                pos = (0, 0, -0.5),
                relief = DGG.RAISED,
                borderWidth = (0.05, 0.05),
                pad = (0.8, 0.3),
                command = self.enteredName)

    def enteredName(self, name = None):
        """ The user has entered his/her nickname.  Launch the
        game. """
        self.playerName = self.nameEntry.get()
        if not self.playerName:
            # Disallow entering with no name.
            self.nameLabel['text'] = 'You must enter a name!'
            return
        
        self.nameLabel.destroy()
        self.nameEntry.destroy()
        self.nameButton.destroy()
        self.nameWall.removeNode()
        
        self.startConnect()

    def lostConnection(self):
        # This should be overridden by a derived class to handle an
        # unexpectedly lost connection to the gameserver.
        self.notify.warning("Lost connection to gameserver.")
        if self.robot:
            self.exit()

        cbMgr = CullBinManager.getGlobalPtr()
        cbMgr.addBin('gui-popup', cbMgr.BTUnsorted, 60)

        self.failureText = OnscreenText(
            'Lost connection to gameserver.\nPress ESC to quit.',
            scale = 0.15, fg = (1, 0, 0, 1), shadow = (0, 0, 0, 1),
            pos = (0, 0.2))
        self.failureText.setBin('gui-popup', 0)
        base.transitions.fadeScreen(alpha = 1)
        render.hide()

        self.ignore('escape')
        self.accept('escape', self.exit)
        self.accept('control-escape', self.exit)

    def exit(self):
        if self.gotMusic:
            self.musicTrackFilename.unlink()
            
        sys.exit()

    def startConnect(self):
        self.url = None
        if self.gameInfo and getattr(self.gameInfo, 'server_url', None):
            self.url = URLSpec(self.gameInfo.server_url)
        if not self.url:
            tcpPort = base.config.GetInt('server-port', Globals.ServerPort)
            hostname = base.config.GetString('server-host', Globals.ServerHost)
            if not hostname:
                hostname = 'localhost'
            self.url = URLSpec('g://%s:%s' % (hostname, tcpPort))
        
        self.waitingText = OnscreenText(
            'Connecting to %s.\nPress ESC to cancel.' % (self.url),
            scale = 0.1, fg = (1, 1, 1, 1), shadow = (0, 0, 0, 1))

        self.connect([self.url],
                     successCallback = self.connectSuccess,
                     failureCallback = self.connectFailure)

    def escape(self):
        """ The user pressed escape.  Exit the client. """
        self.exit()
        
    def connectFailure(self, statusCode, statusString):
        self.waitingText.destroy()
        self.failureText = OnscreenText(
            'Failed to connect to %s:\n%s.\nPress ESC to quit.' % (self.url, statusString),
            scale = 0.15, fg = (1, 0, 0, 1), shadow = (0, 0, 0, 1),
            pos = (0, 0.2))

    def makeWaitingText(self):
        if self.waitingText:
            self.waitingText.destroy()
        self.waitingText = OnscreenText(
            'Waiting for server.',
            scale = 0.1, fg = (1, 1, 1, 1), shadow = (0, 0, 0, 1))

    def connectSuccess(self):
        """ Successfully connected.  But we still can't really do
        anything until we've got the doID range. """
        self.makeWaitingText()

        # Make sure we have interest in the TimeManager zone, so we
        # always see it even if we switch to another zone.
        self.setInterestZones([1])

        # We must wait for the TimeManager to be fully created and
        # synced before we can enter zone 2 and wait for the game
        # object.
        self.acceptOnce(self.uniqueName('gotTimeSync'), self.syncReady)

    def syncReady(self):
        """ Now we've got the TimeManager manifested, and we're in
        sync with the server time.  Now we can enter the world.  Check
        to see if we've received our doIdBase yet. """

        if self.haveCreateAuthority():
            self.gotCreateReady()
        else:
            # Not yet, keep waiting a bit longer.
            self.accept(self.uniqueName('createReady'), self.gotCreateReady)

    def gotCreateReady(self):
        """ Ready to enter the world.  Expand our interest to include
        zone 2, and wait for a TagGame to show up. """

        if not self.haveCreateAuthority():
            # Not ready yet.
            return

        self.ignore(self.uniqueName('createReady'))

        self.waitForGame()

    def joinGame(self, game):
        """ Now we're involved in a game. """
        self.ignore(self.uniqueName('joinGame'))
        self.accept(self.uniqueName('enterMaze'), self.enterMaze)

        if self.chooseGameTask:
            taskMgr.remove(self.chooseGameTask)
            self.chooseGameTask = None

        self.game = game
        self.setInterestZones([1, 2, self.game.objZone])

        # Manifest a player.  The player always has our "base" doId.
        self.player = TagPlayer(self, name = self.playerName,
                                color = self.playerColor,
                                gameId = self.game.doId)
        self.createDistributedObject(distObj = self.player, zoneId = self.game.objZone, doId = self.doIdBase, reserveDoId = True)
        self.player.setupLocalPlayer(self)

        # Set the saved poster data, and also transmit it to the AI.
        self.player.setPoster(self.posterData)
        self.game.sendUpdate('setPoster', [self.posterData])

        self.accept(self.uniqueName('resetGame'), self.resetGame)

    def resetGame(self):
        """ Exit the game and wait for a new one. """
        taskMgr.remove('moveAvatar')
        self.ignoreAll()
        self.stopPaint()

        self.nextGameId = 0
        
        if self.game:
            self.nextGameId = self.game.nextGameId
            self.game.cleanup()
            self.game = None
        if self.av:
            self.sendDeleteMsg(self.av.doId)
            self.av = None
        if self.player:
            self.sendDeleteMsg(self.player.doId)
            self.player = None

        self.waitForGame()

    def waitForGame(self):
        """ Wait for a game to be generated for us to join. """

        self.makeWaitingText()
        
        self.accept(self.uniqueName('joinGame'), self.joinGame)
        self.setInterestZones([1, 2])

        if self.chooseGameTask:
            taskMgr.remove(self.chooseGameTask)
            self.chooseGameTask = None

        if self.nextGameId:
            game = self.doId2do.get(self.nextGameId)
            if game:
                # We already have the game we're waiting for.
                game.d_requestJoin()

            # If we're waiting for a particular game, give it time to
            # show up.
            self.chooseGameTask = taskMgr.doMethodLater(15, self.__chooseGame, 'chooseGame')

        else:
            # Otherwise, take whatever we get.
            self.chooseGameTask = taskMgr.doMethodLater(1, self.__chooseGame, 'chooseGame')

    def __chooseGame(self, task):
        """ Selects one of the available games to join at random. """

        self.chooseGameTask = None

        # Choose a game to join at random.
        availableGames = []
        for game in self.allGames:
            if game.gameActive and not game.rejectedMe:
                availableGames.append(game)

        if not availableGames:
            # Hmm, no games to choose.  Ask for a new one.
            self.timeManager.d_requestNewGame()
            self.waitForGame()
            return

        game = random.choice(availableGames)
        game.d_requestJoin()

    def enterMaze(self, maze):
        # We've got a maze.
        self.setInterestZones([1, 2])

        if self.waitingText:
            self.waitingText.destroy()
            self.waitingText = None

        # If we're not running in a web and don't have a web-based
        # score table, then create an onscreen score table.
        if not self.scoreTable:
            tnp = base.a2dTopRight.attachNewNode('onscreenScore')
            self.onscreenScoreLeft = TextNode('onscreenScoreLeft')
            self.onscreenScoreLeft.setShadow(0.05, 0.05)
            self.onscreenScoreRight = TextNode('onscreenScoreRight')
            self.onscreenScoreRight.setShadow(0.05, 0.05)
            self.onscreenScoreRight.setAlign(TextNode.ARight)
            l = tnp.attachNewNode(self.onscreenScoreLeft)
            l.setX(-12)
            r = tnp.attachNewNode(self.onscreenScoreRight)
            tnp.setScale(0.07)
            tnp.setPos(-0.1, 0, -0.1)

        self.player.setScore(0)
        
        # A CollisionTraverser to detect when the avatar hits walls.
        self.avTrav = CollisionTraverser('avTrav')
        self.avTrav.setRespectPrevTransform(True)

        # A separate CollisionTraverser to ensure the camera still has
        # a line-of-sight to the avatar.
        self.camTrav = CollisionTraverser('camTrav')
        self.camSeg = CollisionSegment((0, 0, 0), (0, 1, 0))
        camSegNode = CollisionNode('camSeg')
        camSegNode.addSolid(self.camSeg)
        self.camSegNP = base.camera.attachNewNode(camSegNode)
        self.camSegNP.setCollideMask(BitMask32(0))
        camSegNode.setFromCollideMask(Globals.WallBit)
        self.camSegHandler = CollisionHandlerEvent()
        self.camSegHandler.setInPattern('blockVis')
        self.camSegHandler.setOutPattern('unblockVis')
        self.camTrav.addCollider(self.camSegNP, self.camSegHandler)
        self.accept('blockVis', self.blockVis)
        self.accept('unblockVis', self.unblockVis)

        # And yet another CollisionTraverser to detect where the spray
        # paint is being applied.
        self.paintTrav = CollisionTraverser('paintTrav')
        self.paintRay = CollisionSegment((0, 0, 0), (0, 1, 0))
        paintRayNode = CollisionNode('paintRay')
        paintRayNode.addSolid(self.paintRay)
        self.paintRayNP = base.cam.attachNewNode(paintRayNode)
        self.paintRayNP.setCollideMask(BitMask32(0))
        paintRayNode.setFromCollideMask(Globals.WallBit | Globals.FloorBit | Globals.AvatarBit | Globals.SelfBit)
        self.paintRayQueue = CollisionHandlerQueue()
        self.paintTrav.addCollider(self.paintRayNP, self.paintRayQueue)
        #self.paintTrav.showCollisions(render)

        # A buffer for rendering the false-color avatar offscreen.
        self.avbuf = None
        if base.win:
            self.avbufTex = Texture('avbuf')
            self.avbuf = base.win.makeTextureBuffer('avbuf', 256, 256, self.avbufTex, True)
            cam = Camera('avbuf')
            cam.setLens(base.camNode.getLens())
            self.avbufCam = base.cam.attachNewNode(cam)
            dr = self.avbuf.makeDisplayRegion()
            dr.setCamera(self.avbufCam)
            self.avbuf.setActive(False)
            self.avbuf.setClearColor((1, 0, 0, 1))
            cam.setCameraMask(Globals.AvBufMask)
            base.camNode.setCameraMask(Globals.CamMask)

            # avbuf renders everything it sees with the gradient texture.
            tex = loader.loadTexture('models/gradient.png')
            np = NodePath('np')
            np.setTexture(tex, 100)
            np.setColor((1, 1, 1, 1), 100)
            np.setColorScaleOff(100)
            np.setTransparency(TransparencyAttrib.MNone, 100)
            np.setLightOff(100)
            cam.setInitialState(np.getState())
            render.hide(Globals.AvBufMask)

        # Manifest an avatar for ourselves.
        if self.av:
            self.sendDeleteMsg(self.av.doId)
            self.av = None
        self.av = TagAvatar(self, playerId = self.player.doId)
        x = random.uniform(0, maze.xsize * Globals.MazeScale)
        y = random.uniform(0, maze.ysize * Globals.MazeScale)
        h = random.uniform(0, 360)
        self.av.setPosHpr(x, y, 0, h, 0, 0)
        self.createDistributedObject(distObj = self.av, zoneId = 2)
        self.av.setupLocalAvatar(self)

        self.player.b_setAvId(self.av.doId)

        # The camera arm follows behind the avatar.
        self.cameraArmHinge = self.av.attachNewNode('cameraArmHinge')
        self.cameraArm = self.cameraArmHinge.attachNewNode('cameraArm')
        self.cameraArm.setPos(0, -10, 2)
        base.camera.setPosHpr(self.cameraArm, 0, 0, 0, 0, 0, 0)

        # Sound effect while painting.
        self.spraySfx = loader.loadSfx('models/spray_middle.ogg')
        if self.spraySfx:
            self.spraySfx.setLoop(True)

        # Listen for movement control keys.
        for key in Globals.ControlKeys:
            self.accept(key, self.setKey, [key, True])
            self.accept('control-' + key, self.setKey, [key, True])
            self.accept(key + '-up', self.setKey, [key, False])

        # Holding mouse button 3, or control-mouse 1 (for macs),
        # activates camera-mouse mode.
        self.accept('mouse3', self.enableCameraMouse, [True])
        self.accept('control-mouse1', self.enableCameraMouse, [True])
        self.accept('mouse3-up', self.enableCameraMouse, [False])
        self.accept('mouse1-up', self.enableCameraMouse, [False])
        self.cameraMouseStart = None

        # Holding mouse button 1 paints.
        self.accept('mouse1', self.startPaint)

        # Now add the task that manages the avatar and camera
        # positions each frame.
        taskMgr.remove('moveAvatar')
        taskMgr.add(self.moveAvatar, 'moveAvatar')

        # Let the DistributedSmoothNode take care of broadcasting the
        # position updates several times a second.
        self.av.startPosHprBroadcast()

    def enableCameraMouse(self, enable):
        self.stopPaint()
        self.cameraMouseStart = None
        if enable and base.mouseWatcherNode.hasMouse():
            # Record the starting position of the mouse pointer.
            mpos = base.mouseWatcherNode.getMouse()
            self.cameraMouseStart = (mpos.getX(), mpos.getY())
            self.cameraMouseOrigHpr = self.cameraArmHinge.getHpr()

            # While in camera mouse mode, the camera is directly
            # parented to the camera arm.
            base.camera.wrtReparentTo(self.cameraArm)
            base.camera.setScale(1)

        else:
            # When no longer in camera mouse mode, the camera is
            # attached to render, and lags a little behind the camera
            # arm.
            base.camera.wrtReparentTo(render)
            base.camera.setScale(1)

    def blockVis(self, entry):
        """ A wall is between the camera and the avatar.  Make it
        transparent. """
##         normal = entry.getSurfaceNormal(base.camera)
##         if normal[1] > 0:
##             # This wall is facing the wrong way; it doesn't count.
##             return

        sx, sy, dir = entry.getIntoNodePath().getNetPythonTag('step')
        cell = Cell.MazeCells.get((sx, sy), None)
        if cell:
            cell.setFade(dir, True)
        
    def unblockVis(self, entry):
        """ The wall is no longer between the camera and the avatar.
        Make it opaque again. """
        sx, sy, dir = entry.getIntoNodePath().getNetPythonTag('step')
        cell = Cell.MazeCells.get((sx, sy), None)
        if cell:
            cell.setFade(dir, False)

    def startPaint(self):
        taskMgr.add(self.doPaint, 'doPaint')
        if self.spraySfx:
            self.spraySfx.play()

    def stopPaint(self):
        taskMgr.remove('doPaint')
        if self.spraySfx:
            self.spraySfx.stop()

        if self.paintThing:
            self.paintThing.clearPaint()
            self.paintThing = None

    def doPaint(self, task):
        # The user is holding down the mouse button.  Apply spray
        # paint to whatever surface is under the mouse.
        if not base.mouseWatcherNode.hasMouse():
            # Mouse not in the window.
            return task.cont

        mpos = base.mouseWatcherNode.getMouse()
        self.paintRay.setFromLens(base.camNode, mpos.getX(), mpos.getY())
        self.paintTrav.traverse(render)

        self.paintRayQueue.sortEntries()

        # Find the first entry with a normal pointing torwards the
        # camera.
        for entry in self.paintRayQueue.getEntries():
            normal = entry.getSurfaceNormal(base.cam)
            if normal[1] > 0:
                # Facing the wrong way.
                continue

            paintType = entry.getIntoNodePath().getNetTag('paintType')
            if not paintType:
                # Not paintable.
                continue

            if paintType == 'cell':
                if self.__paintCell(entry):
                    return task.cont
            elif paintType == 'avatar':
                if self.__paintAvatar(entry):
                    return task.cont

        return task.cont
        
    def __paintCell(self, entry):
        """ Paints onto the cell wall, ceiling, or floor.  Returns
        true on success, false on failure. """

        # Check the wall's normal first; it must be pointed vaguely
        # towards the avatar to count.
        point = entry.getSurfacePoint(self.av.center)
        normal = entry.getSurfaceNormal(self.av.center)
        d = normal.dot(point)
        if d > 0:
            # The wall is facing the wrong way; it doesn't count.
            return False

        # The length of the point (treated as a vector), as seen from
        # the avatar, represents the distance to this point on the
        # wall.  We attenuate the paint color based on this distance.
        distance = point.length()
        alpha = min(5.0 / (distance + 0.0001), 1.0)
        alpha = alpha * alpha

        # Now get the point in world coordinates, to determine the
        # paint location.
        point = entry.getSurfacePoint(render)
        point = Point3(point[0] / Globals.MazeScale,
                       point[1] / Globals.MazeScale,
                       point[2] / Globals.MazeZScale)
        sx, sy, dir = entry.getIntoNodePath().getNetPythonTag('step')
        dx = point[0] - sx
        dy = point[1] - sy
        cell = Cell.MazeCells.get((sx, sy), None)
        if cell and not cell.getFade(dir):
            if cell is not self.paintThing:
                cell.clearPaint()
            colorBrush, whiteBrush = self.player.getBrushes(alpha)
            cell.paint(colorBrush, whiteBrush, dx, dy, point[2], dir)
            self.paintThing = cell
            return True

        return False
        
    def __paintAvatar(self, entry):
        """ Paints onto an avatar.  Returns true on success, false on
        failure (because there are no avatar pixels under the mouse,
        for instance). """
        
        # First, we have to render the avatar in its false-color
        # image, to determine which part of its texture is under the
        # mouse.
        if not self.avbuf:
            return False

        avId = entry.getIntoNodePath().getNetPythonTag('avId')
        av = self.doId2do.get(avId)
        if not av:
            return False

        mpos = base.mouseWatcherNode.getMouse()

        av.showThrough(Globals.AvBufMask)
        self.avbuf.setActive(True)
        base.graphicsEngine.renderFrame()
        av.show(Globals.AvBufMask)
        self.avbuf.setActive(False)

        # Now we have the rendered image in self.avbufTex.
        if not self.avbufTex.hasRamImage():
            print "Weird, no image in avbufTex."
            return False
        p = PNMImage()
        self.avbufTex.store(p)
        ix = int((1 + mpos.getX()) * p.getXSize() * 0.5)
        iy = int((1 - mpos.getY()) * p.getYSize() * 0.5)
        x = 1
        if ix >= 0 and ix < p.getXSize() and iy >= 0 and iy < p.getYSize():
            s = p.getBlue(ix, iy)
            t = p.getGreen(ix, iy)
            x = p.getRed(ix, iy)
        if x > 0.5:
            # Off the avatar.
            return False

        # At point (s, t) on the avatar's map.

        # Get the distance to the avatar, for attenuation.
        distance = self.av.getDistance(av)
        alpha = min(5.0 / (distance + 0.0001), 1.0)
        alpha = alpha * alpha
        
        if av is not self.paintThing:
            av.clearPaint()
        colorBrush, whiteBrush = self.player.getBrushes(alpha)
        av.paint(colorBrush, whiteBrush, s, t)
        self.paintThing = av
        return True
        
        

    def changeAvZone(self, zoneId):
        """ Move the avatar into the indicated zone. """

        # Move our avatar into the indicated zone
        self.setObjectZone(self.av, zoneId)

    def setKey(self, key, value):
        self.keyMap[key] = value

    def __determineCell(self, node):
        """ Returns the cell that the indicated node is positioned
        within, or None if it is not within any cell. """
        
        sx = int(node.getX() / Globals.MazeScale)
        sy = int(node.getY() / Globals.MazeScale)
        cell = Cell.MazeCells.get((sx, sy), None)
        return cell

    def moveAvatar(self, task):
        """ Moves the avatar according to the WASD or arrow keys. """

        # The amount of time elapsed since last frame.
        dt = globalClock.getDt()

        # Record the current position in case he goes off the grid.
        origPos = self.av.getPos()

        # The current position determines the active cell.
        self.avCell = self.__determineCell(self.av)

        moving = False
        if self.keyMap['arrow_left'] or self.keyMap['a']:
            self.av.setH(self.av.getH() + dt * Globals.TurnPerSecond)
            moving = True
        if self.keyMap['arrow_right'] or self.keyMap['d']:
            self.av.setH(self.av.getH() - dt * Globals.TurnPerSecond)
            moving = True
        if self.keyMap['arrow_down'] or self.keyMap['s']:
            self.av.setFluidY(self.av, -dt * Globals.BackwardPerSecond)
            moving = True
        if self.keyMap['arrow_up'] or self.keyMap['w']:
            self.av.setFluidY(self.av, dt * Globals.ForwardPerSecond)
            moving = True

        # Play the run animation if we're moving.
        if moving:
            self.av.setMoving(True)

            # No painting allowed while running.
            self.stopPaint()

            if not self.cameraMouseStart:
                # Also, ensure the camera arm is back where it
                # belongs, in case it was moved during camera-mouse
                # mode.
                self.cameraArmHinge.setHpr(0, 0, 0)
            
        else:
            self.av.setMoving(False)

        # Now check for collisions.
        if self.avCell:
            # Temporarily instance the current cell to avRoot, so we
            # can traverse the cell and the avatars at once.  A little
            # bit hacky.
            tmp = self.avCell.root.instanceTo(self.avRoot)
            self.avTrav.traverse(self.avRoot)
            tmp.removeNode()

        # Check if he's still in the grid.
        newCell = self.__determineCell(self.av)
        if not newCell:
            # No good: reset position.
            self.av.setPos(origPos)
            newCell = self.avCell

        if self.cameraMouseStart and base.mouseWatcherNode.hasMouse():
            # In camera-mouse mode, the camera arm can be swung around
            # to look at the avatar from different points of view.
            mpos = base.mouseWatcherNode.getMouse()
            dx = (mpos.getX() - self.cameraMouseStart[0]) * base.win.getXSize()
            dy = (mpos.getY() - self.cameraMouseStart[1]) * base.win.getYSize()
            self.cameraArmHinge.setHpr(-dx * Globals.CameraPerPixel + self.cameraMouseOrigHpr[0],
                                       dy * Globals.CameraPerPixel + self.cameraMouseOrigHpr[1], 0)

        # The camera chases the cameraArm.
        vec = base.camera.getPos(self.cameraArm)
        dist = vec.length()
        if dist > 0:
            vec /= dist
            # Move closer to the target point.
            dist = max(dist - dt * Globals.CameraPerSecond, 0)
            dist = min(dist, Globals.MaxCameraDistance)
            base.camera.setPos(self.cameraArm, vec * dist)

            # Ensure the camera is looking at our avatar, without tilting
            # downward.
            base.camera.headsUp(self.av)

        # Perform the line-of-sight check.
        to = base.camera.getRelativePoint(self.av, (0, 0, 1))
        self.camSeg.setPointB(to)
        self.camTrav.traverse(render)

        return task.cont

    def hsv2rgb(self, h, s, v):
        """ Given hue, saturation, value, return (r, g, b). """

        h *= 6  # convert [0..1] to [0..6]
        i = math.floor(h)
        f = h - i
        if not (int(i) & 1):
            f = 1 - f  # if i is even
        m = v * (1 - s)
        n = v * (1 - s * f)
        if i == 6 or i == 0:
            return (v, n, m)
        elif i == 1:
            return (n, v, m)
        elif i == 2:
            return (m, v, n)
        elif i == 3:
            return (m, n, v)
        elif i == 4:
            return (n, m, v)
        elif i == 5:
            return (v, m, n)

        assert False
    
    def __getMusic(self):
        """ This starts the download task to get the music track from
        the server in the background. """

        assert not self.gotMusic
        self.musicTrackFilename = Filename.temporary('', '', '.ogg')
        print "Music filename = %s" % (self.musicTrackFilename)
        http = HTTPClient.getGlobalPtr()
        ch = http.makeChannel(False)
        ch.beginGetDocument(Globals.MusicTrackURL)
        ch.downloadToFile(self.musicTrackFilename)

        taskMgr.add(self.__getMusicTask, 'getMusicTask',
                    extraArgs = [ch], appendTask = True)

    def __getMusicTask(self, ch, task):
        assert not self.gotMusic
        if ch.run():
            # Come back later.
            return task.cont

        # We're done!
        if not ch.isValid():
            print "Unable to download %s: %s" % (
                Globals.MusicTrackURL, ch.getStatusString())
            self.musicTrackFilename.unlink()
            return task.done

        print "Successfully downloaded %s to %s." % (Globals.MusicTrackURL, self.musicTrackFilename)
        self.gotMusic = True
        messenger.send('gotMusic')
        return task.done
    
    def changePoster(self):
        """ Called by the web code when the "change poster" button is
        clicked. """
        if self.player:
            self.posterFSM.request('Hang', self.player.doId)
            
    def readTagPoster(self, filename):
        """ Fill the initial poster data with the data in the
        indicated file.  This is generally used only in development,
        or when a user wants to preload a poster via a config
        file. """
        tex = loader.loadTexture(filename)
        if not tex or tex.getOrigFileYSize() == 0:
            print "Could not read tag-poster %s" % (filename)
            return
        aspect = float(tex.getOrigFileXSize()) / float(tex.getOrigFileYSize())

        p = PNMImage()
        tex.store(p)

        xs = min(p.getXSize(), 256)
        ys = min(p.getYSize(), 256)
        p1 = PNMImage(xs, ys)
        p1.quickFilterFrom(p)
        strm = StringStream()
        ConfigVariableInt('jpeg-quality').setValue(65)
        p1.write(strm, 'jpg')
        data = strm.getData()

        self.posterData = (data, aspect)
        
