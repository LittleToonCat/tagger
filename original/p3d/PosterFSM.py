from direct.fsm.FSM import FSM

class PosterFSM(FSM):
    def __init__(self, appRunner):
        FSM.__init__(self, 'PosterFSM')
        
        if not appRunner:
            self.slice = None
            self.posterDiv = None
        else:
            document = appRunner.dom.document
            self.slice = document.getElementById('slice_6_b')
            self.posterDiv = document.getElementById('posterDiv')

    def enterClear(self):
        """ No poster in offer. """
        print "No poster offer"
        if self.slice and self.posterDiv:
            self.slice.src = "slice_6_b.jpg"
            self.posterDiv.innerHTML = ''

    def enterHang(self, playerId):
        """ Hang a poster. """

        print "Offer a poster"
        if self.slice and self.posterDiv:
            self.slice.src = "slice_6_b_hang_poster.jpg"
            self.posterDiv.innerHTML = '<iframe src="poster.html?playerId=%s" width="640" height="139" frameborder="0" scrolling="no"></iframe>' % (playerId)

    def enterOnDisplay(self):
        """ Poster is on display. """
        print "Poster is on display"
        
        if self.slice and self.posterDiv:
            self.slice.src = "slice_6_b_on_display.jpg"
            self.posterDiv.innerHTML = '<input value="Change Poster" type="button" onClick="ChangePoster()">'
            
