from direct.distributed.DistributedObject import DistributedObject
from pandac.PandaModules import *
import Globals
import math

class TagPlayer(DistributedObject):
    def __init__(self, cr, name = None, color = None, gameId = None):
        DistributedObject.__init__(self, cr)

        # This is true if this avatar represents the "local avatar",
        # i.e. the player at the keyboard, as opposed to a remote
        # player.
        self.localPlayer = False

        # The doId of the game we've joined.
        self.gameId = gameId

        # The doId of the associated avatar.
        self.avId = 0

        # The list of avatars onto which this player has painted.
        self.paintedAvatars = []

        self.name = name
        self.brushRadius = 1
        self.brushes = {}
        self.setColor(color)
        self.posterData = ('', 0)
        self.score = 0
        self.wallCount = 0
        self.floorCount = 0
        self.pixelCount = 0
        self.avPixelCount = 0
        self.onMePixelCount = 0
        self.bonus = 1
        
    def announceGenerate(self):
        DistributedObject.announceGenerate(self)

        # Set up our HTML text for the player list.
        hexcolor = '%02x%02x%02x' % (
            int(self.color[0] * 255),
            int(self.color[1] * 255),
            int(self.color[2] * 255))
        self.htmlText = '''
        <tr style="border: 1px solid black; background: #%(hexcolor)s">
        <td style="padding-left: 5pt; padding-right: 5pt; text-align: left"><span class="tag">%(name)s</span></td>
        <td style="padding-left: 5pt; padding-right: 5pt; text-align: right">%%s</td>
        </tr>
        '''  % {
            'name' : self.name,
            'hexcolor' : hexcolor,
            }

        # Add ourselves to the player list.
        self.cr.playerList.addPlayer(self)
            
##             self.playerRow = self.cr.playerTable.insertRow(0)
##             self.playerNameCol = self.playerRow.insertCell(0)
##             self.playerScoreCol = self.playerRow.insertCell(1)
##             self.playerNameCol.innerHTML = self.name
##             self.playerScoreCol.innerHTML = str(self.score)

    def disable(self):
        # Remove ourselves from the player list.
        self.cr.playerList.removePlayer(self)

        for av in self.paintedAvatars:
            av.removePlayer(self)

        self.cr.posterFSM.request('Clear')

        DistributedObject.disable(self)

    def setupLocalPlayer(self, world):
        """ Sets up this particular player as this local client's
        player."""

        self.localPlayer = True

    def getName(self):
        return self.name

    def setName(self, name):
        self.name = name

    def getColor(self):
        return self.color

    def setColor(self, color):
        self.color = color
        self.pixelSpec = None

        if color:
            # Store the color as a PixelSpec too, which is used for
            # bookkeeping.
            self.pixelSpec = PNMImage.PixelSpec(int(color[0] * 255),
                                                int(color[1] * 255),
                                                int(color[2] * 255))

            self.colord = VBase4D(color[0], color[1], color[2], 1)
            self.brushes = {}

    def getGameId(self):
        return self.gameId

    def getAvId(self):
        return self.avId

    def setAvId(self, avId):
        self.avId = avId

    def d_setAvId(self, avId):
        self.sendUpdate('setAvId', [avId])

    def b_setAvId(self, avId):
        self.d_setAvId(avId)
        self.setAvId(avId)
            
    def getBrushes(self, alpha):
        """ Returns colorBrush, whiteBrush for the indicated alpha
        value. """
        ialpha = int(alpha * 100)
        alpha = ialpha / 100.0
        
        brushes = self.brushes.get(ialpha, None)
        if not brushes:
            r, g, b = self.color
            colorBrush = PNMBrush.makeSpot(VBase4D(r, g, b, alpha), self.brushRadius, False)
            whiteBrush = PNMBrush.makeSpot(VBase4D(1, 1, 1, alpha), self.brushRadius, False)
            brushes = (colorBrush, whiteBrush)
            self.brushes[ialpha] = brushes
        return brushes
        
        
    def getColor(self):
        return self.color

    def setScore(self, score):
        self.score = score
        
        if self.localPlayer and self.cr.game and self.cr.game.maze:
            # Update the onscreen score report.
            bonusText = ''
            bonusPointsText = ''
            if self.bonus > 1:
                # U+00d7 is the multiply symbol.
                bonusText = u'\u00d7 %.1f wall bonus' % (self.bonus)
                bonusPointsText = self.score - (self.wallCount * Globals.PointsPerWall + self.floorCount * Globals.PointsPerFloor + self.pixelCount * Globals.PointsPerPixel + self.avPixelCount * Globals.PointsPerAvatarPixel + self.onMePixelCount * Globals.PointsPerMePixel)

            if self.cr.onscreenScoreLeft:
                # Use setWtext because it might include unicode characters.
                self.cr.onscreenScoreLeft.setWtext(u'Walls: %s (of %s)\nFloors/Ceilings: %s\nPaint: %d\nOn other players: %d\nOther paint on me: %d\n%s\nScore:' % (
                    self.wallCount, self.cr.game.maze.numWalls,
                    self.floorCount,
                    self.pixelCount * Globals.PixelReportFactor,
                    self.avPixelCount * Globals.PixelReportFactor,
                    self.onMePixelCount * Globals.PixelReportFactor,
                    bonusText))
                self.cr.onscreenScoreRight.setText('%s\n%s\n%s\n%s\n%s\n%s\n%s' % (
                    self.wallCount * Globals.PointsPerWall,
                    self.floorCount * Globals.PointsPerFloor,
                    self.pixelCount * Globals.PointsPerPixel,
                    self.avPixelCount * Globals.PointsPerAvatarPixel,
                    self.onMePixelCount * Globals.PointsPerMePixel,
                    bonusPointsText, self.score))

            # Update the web-based score report.
            if self.cr.scoreTable:
                text = '''
                <table width="300px" style="border-collapse: collapse">
                <tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">Walls: %s (of %s)</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                <tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">Floors/Ceilings: %s</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                <tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">Paint: %d</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                <tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">On other players: %d</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                <tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">Other paint on me: %d</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                <tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">%s</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">Score:</td>
                <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">%s</td>
                </tr>
                </table>
                ''' % (self.wallCount, self.cr.game.maze.numWalls,
                       self.wallCount * Globals.PointsPerWall,
                       self.floorCount, self.floorCount * Globals.PointsPerFloor,
                       self.pixelCount * Globals.PixelReportFactor,
                       self.pixelCount * Globals.PointsPerPixel,
                       self.avPixelCount * Globals.PixelReportFactor,
                       self.avPixelCount * Globals.PointsPerAvatarPixel,
                       self.onMePixelCount * Globals.PixelReportFactor,
                       self.onMePixelCount * Globals.PointsPerMePixel,
                       bonusText, bonusPointsText,
                       self.score)
                self.cr.scoreTable.innerHTML = text

        # Update the web page with the player list as needed.
        self.cr.playerList.markDirty()
            
    def getScore(self):
        return self.score

    def setScoreDerivation(self, wallCount, floorCount, pixelCount,
                           avPixelCount, onMePixelCount, bonus):
        self.wallCount = wallCount
        self.floorCount = floorCount
        self.pixelCount = pixelCount
        self.avPixelCount = avPixelCount
        self.onMePixelCount = onMePixelCount
        self.bonus = bonus

        pixelCount = self.avPixelCount - self.onMePixelCount
        if pixelCount > 0:
            # More paint on other avatars than on me.  A brush radius
            # bonus.
            brushRadius = math.log(pixelCount) / 10.0 + 1.0
        elif pixelCount == 0:
            # Same amount of paint, probably none.
            brushRadius = 1
        else: # pixelCount < 0:
            # More paint on me than other avatars.  A brush radius
            # penalty.
            brushRadius = 1000.0 / (-pixelCount + 1000.0)

        if brushRadius != self.brushRadius:
            self.brushRadius = brushRadius
            self.brushes = {}

    def d_avatarPixelCount(self, av, count):
        """ Informs the AI of the count of this player's paint pixels
        on the indicated avatar. """

        self.sendUpdate('avatarPixelCount', [av.doId, count])
        

    def getPoster(self):
        return (self.posterData,)
        
    def setPoster(self, posterData):
        """ Set from the client, or from the AI repository. """
        print "setPoster(%s, %s)" % (len(posterData[0]), posterData[1])
        self.posterData = posterData

        # Save it on the CR for the next game.
        self.cr.posterData = posterData

        if self.posterData[0]:
            # Unless we already have a poster.
            self.cr.posterFSM.request('OnDisplay')
        else:
            self.cr.posterFSM.request('Hang', self.doId)

    def d_setPoster(self, posterData):
        self.sendUpdate('setPoster', [posterData])

    def b_setPoster(self, posterData):
        self.setPoster(posterData)
        self.d_setPoster(posterData)
