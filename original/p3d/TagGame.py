from direct.distributed.DistributedObject import DistributedObject
from direct.distributed.ClockDelta import globalClockDelta
from direct.gui.DirectGui import *
from direct.interval.IntervalGlobal import *
from pandac.PandaModules import *
from Cell import makeArtCard
import Globals
import math

class TagGame(DistributedObject):
    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.timeout = None
        self.objZone = None
        self.timerTask = None
        self.timerText = None
        self.localPlayerJoined = False
        self.winnerText = None
        self.againButton = None
        self.music = None
        self.musicIval = None
        self.fadeModel = None

        self.gameActive = True

        # This is set true if we ever requested to join this game, and
        # it said no.
        self.rejectedMe = False

        # Filled in when the Maze gets created.
        self.mazeId = None
        self.maze = None

    def announceGenerate(self):
        DistributedObject.announceGenerate(self)

        self.cr.allGames.append(self)

        nextGameId = self.cr.nextGameId
        if not nextGameId:
            nextGameId = self.cr.timeManager.suggestedGameId
            
        if nextGameId == self.doId and not self.cr.game and not self.localPlayerJoined and self.gameActive and not self.rejectedMe:
            # If we're waiting for this particular game, request to
            # join it.
            self.d_requestJoin()

    def disable(self):
        self.cr.allGames.remove(self)

        DistributedObject.disable(self)

    def setNumPlayers(self, numPlayers):
        self.numPlayers = numPlayers
        
    def setMazeId(self, mazeId):
        if mazeId != self.mazeId:
            self.mazeId = mazeId
            self.cr.relatedObjectMgr.requestObjects([self.mazeId], self.__gotMaze)

    def __gotMaze(self, mazeList):
        self.maze = mazeList[0]
        if self.localPlayerJoined:
            messenger.send(self.cr.uniqueName('enterMaze'), [self.maze],
                           taskChain = 'default')

    def d_requestJoin(self):
        """ Called by a new client to join the game. """

        self.sendUpdate('requestJoin', [])

    def setJoin(self, success):
        """ Called by the server to tell a player he's joined the
        game. """

        if self.cr.game:
            print "Already involved in game %s, cannot join %s" % (self.cr.game.doId, self.doId)
        elif not success:
            print "Not allowed to join game %s" % (self.doId)
            self.rejectedMe = True
            self.cr.waitForGame()
        else:
            print "Joining game %s" % (self.doId)
            self.localPlayerJoined = True
            if self.timeout:
                self.startTimer()
            messenger.send(self.cr.uniqueName('joinGame'), [self],
                           taskChain = 'default')
        
    def setTimeout(self, timestamp):
        timeout = globalClockDelta.networkToLocalTime(timestamp)
        if self.timeout is None or abs(self.timeout - timeout) > 0.5:
            self.timeout = timeout

            if self.localPlayerJoined:
                self.startTimer()
        
    def setObjZone(self, objZone):
        self.objZone = objZone

    def cleanup(self):
        self.stopTimer()
        if self.timerText:
            self.timerText.removeNode()
            self.timerText = None
        if self.winnerText:
            self.winnerText.removeNode()
            self.winnerText = None
        if self.againButton:
            self.againButton.destroy()
            self.againButton = None
        if self.fadeModel:
            self.fadeModel.detachNode()
            self.fadeModel = None

        self.maze = None

    def setWinners(self, gameActive, winners, artPaintings, nextGameId):
        if not self.gameActive:
            # Never mind, we've already been here.
            return
        
        self.gameActive = gameActive
        self.winners = winners
        self.artPaintings = artPaintings
        self.nextGameId = nextGameId
        if self.gameActive:
            # The game is still active.
            return

        # The game is over.
        if not self.localPlayerJoined:
            return
        
        if self.cr.onscreenScoreLeft:
            self.cr.onscreenScoreLeft.setText('')
            self.cr.onscreenScoreRight.setText('')

        if not self.timerText:
            self.__setupTimerText()
        if self.timerTask:
            taskMgr.remove(self.timerTask)
            self.timerTask = None
        self.timerText.node().setText('Game Over!')

        self.cr.posterFSM.request('Clear')

        if self.fadeModel:
            self.fadeModel.detachNode()
        self.fadeModel = loader.loadModel('models/fade')
        self.fadeModel.reparentTo(render2d, -1)
        self.fadeModel.setScale(2)
        self.fadeModel.setColor(0.4, 0.2, 0.2, 1)
        self.fadeModel.setColorScale(1, 1, 1, 0)
        ival = self.fadeModel.colorScaleInterval(0.5, (1, 1, 1, 1))
        ival.start()
            
        if self.winnerText:
            self.winnerText.removeNode()
        self.winnerText = aspect2d.attachNewNode('winnerText')
        self.winnerText.setPos(0, 0, 0.3)
        self.winnerText.setScale(0.75)
        
        if self.winners:
            winningScore = winners[0][2]
            for i in range(len(self.winners)):
                name, color, score = self.winners[i]
                self.__makeWinnerText(name, color, score, i, (score == winningScore))
        artPaintingsNode = self.winnerText.attachNewNode('artPaintings')
        for i in range(len(self.artPaintings)):
            dir, name, color, poster, imgData = self.artPaintings[i]
            bonus = Globals.ArtPaintingBonus[i]
            wall = makeArtCard(dir, name, color, poster, imgData, bonus)
            wall.reparentTo(artPaintingsNode)
            wall.setScale(0.6)
            wall.setPos(0.9 * (i - 1), 0, -1)

        if self.againButton:
            self.againButton.destroy()

        playAgainEvent = self.cr.uniqueName('resetGame')
        self.againButton = DirectButton(
            text = 'Play again',
            scale = 0.1,
            pos = (0, 0, -0.8),
            relief = DGG.RAISED,
            borderWidth = (0.05, 0.05),
            pad = (0.8, 0.3),
            command = lambda e = playAgainEvent: messenger.send(e, taskChain = 'default'),
            )

        messenger.send(self.cr.uniqueName('gameOver'), taskChain = 'default')

    def __makeWinnerText(self, name, color, score, i, isWinner):
        root = self.winnerText.attachNewNode(str(i))

        scale = 0.12
        width = 20

        root.setPos(-width * 0.5 * scale, 0, 0.4 - 0.15 * i)
        root.setScale(scale)

        if isWinner:
            root.setZ(0.45 - 0.15 * i)

        tagFont = loader.loadFont('models/one8seven.ttf')
        tn = TextNode('name')
        tn.setFont(tagFont)
        tn.setText(name)
        tn.setTextColor(0, 0, 0, 1)
        tn.setAlign(tn.ABoxedLeft)
        tn.setWordwrap(width)
        tn.setCardAsMargin(0.5, 0.5, 0.05, -0.15)
        tn.setCardColor(color[0], color[1], color[2], 1)
        tn.setFrameAsMargin(0.5, 0.5, 0.05, -0.15)
        tn.setFrameColor(0, 0, 0, 1)
        name = root.attachNewNode(tn)

        if isWinner:
            tn.setTextColor(1, 1, 1, 1)
            tn.setShadow(0.05, 0.05)
        
        tn = TextNode('score')
        tn.setText(str(score))
        tn.setTextColor(0, 0, 0, 1)
        tn.setAlign(tn.ABoxedRight)
        tn.setWordwrap(width)
        score = name.attachNewNode(tn)

        if isWinner:
            tn.setTextColor(1, 1, 1, 1)
            tn.setShadow(0.05, 0.05)

        return root

    def __setupTimerText(self):
        if self.timerText:
            self.timerText.removeNode()
        self.timerText = base.a2dTopCenter.attachNewNode(TextNode('timer'))
        self.timerText.setScale(0.15)
        self.timerText.setPos(0, 0, -0.15)
        tn = self.timerText.node()
        tn.setAlign(TextNode.ACenter)
        tn.setShadow(0.05, 0.05)

        cardModel = loader.loadModel('models/nametag_card')
        cardTex = cardModel.findTexture('*')
        tn.setCardColor(0, 0, 0, 0.5)
        tn.setCardBorder(0.2, 0.2)
        tn.setCardAsMargin(0.2, 0.3, 0.05, -0.15)
        if cardTex:
            tn.setCardTexture(cardTex)

    def startTimer(self):
        if self.timerTask:
            taskMgr.remove(self.timerTask)
            self.timerTask = None
        self.__setupTimerText()
        
        delay = self.__getTimerDelay()
        self.timerTask = taskMgr.doMethodLater(delay, self.doTimer, 'timer')

        # We also start the music at the same time.
        self.startMusic()

    def startMusic(self):
        """ Starts the music playing when it has been successfully
        downloaded. """
        if not self.timerTask:
            # No timer, no music.
            return

        if not self.cr.gotMusic:
            # Come back when we've really got it.
            self.acceptOnce('gotMusic', self.startMusic)
            return

        # Load it and start it.
        self.music = loader.loadMusic(self.cr.musicTrackFilename.cStr())
        if self.music:
            gameLength = Globals.GameLengthSeconds + Globals.MusicHangSeconds
            startTime = 0
            if self.music.length() > gameLength:
                # If the music clip is too long, start it in the middle.
                startTime = self.music.length() - gameLength
            self.musicIval = SoundInterval(self.music, startTime = startTime)
            # If the music clip is too short, pad it with silence at the beginning.
            if self.music.length() < gameLength:
                self.musicIval = ParallelEndTogether(Wait(gameLength), self.musicIval)

            # Now start the clip so that it will end when the timer does.
            timeRemaining = self.timeout - globalClock.getFrameTime()
            timeRemaining += Globals.MusicHangSeconds
            if timeRemaining > 0:
                self.musicIval.start(startT = self.musicIval.getDuration() - timeRemaining)

    def stopTimer(self):
        if self.timerTask:
            taskMgr.remove(self.timerTask)
            self.timerTask = None
        if self.musicIval:
            self.musicIval.finish()
            self.musicIval = None

    def __getTimerDelay(self):
        """ Returns the number of seconds until the timer should be
        next adjusted. """
        
        timeRemaining = self.timeout - globalClock.getFrameTime()
        if timeRemaining < 0:
            return 0
        
        if timeRemaining < Globals.ShowClockSeconds:
            return timeRemaining - math.floor(timeRemaining)
        else:
            return timeRemaining - Globals.ShowClockSeconds

    def doTimer(self, task):
        time = int(self.timeout - globalClock.getFrameTime() + 0.5)
        time = max(time, 0)
        self.timerText.node().setText(str(time))

        delay = self.__getTimerDelay()
        if not delay:
            return task.done
        task.setDelay(delay)
        return task.again
    
