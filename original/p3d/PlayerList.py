class PlayerList:
    """ Maintains a list of players in the game, and generates that
    list to HTML text when updates are needed. """

    def __init__(self, playerTable):
        self.players = []
        self.playerTable = playerTable
        self.updateTask = None

        self.header =  '''
        <tr>
        <td style="text-align: left; padding-left: 5pt; padding-right: 5pt">Player</td>
        <td style="text-align: right; padding-left: 5pt; padding-right: 5pt">Score</td>
        </tr>
        '''

    def addPlayer(self, player):
        self.players.append(player)
        self.markDirty()

    def removePlayer(self, player):
        self.players.remove(player)
        self.markDirty()

    def markDirty(self):
        if self.updateTask:
            # Already waiting to send an update.
            return
        self.updateTask = taskMgr.doMethodLater(5, self.sendUpdate, 'sendUpdate')
        

    def sendUpdate(self, task):
        """ Updates the HTML page, if any, with the latest player
        information. """
        self.updateTask = None
        self.players.sort(key = lambda p: -p.score)

        if self.playerTable:
            text = self.header
            for p in self.players[:12]:
                 text += p.htmlText % (p.score)
                 
            text = '<center><table width="296" style="border-collapse: collapse">%s</table></center>' % (text)

            #self.playerTable.innerHTML = text
            base.appRunner.evalScript("document.getElementById('playerTable').innerHTML = %s" % (repr(text)))
            
