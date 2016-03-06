from direct.distributed.DistributedSmoothNode import DistributedSmoothNode
from pandac.PandaModules import *
from direct.actor.Actor import Actor
import Globals

class TagAvatar(DistributedSmoothNode):
    paintTs = None

    def __init__(self, cr, playerId = None):
        DistributedSmoothNode.__init__(self,cr)
        # you have to initialize NodePath.__init__() here because it is
        # not called in DistributedSmoothNode.__init__()
        NodePath.__init__(self, 'avatar')

        self.playerId = playerId

        self.setTag('paintType', 'avatar')

        # This point is in the middle of the avatar, for determining
        # paint normals and such.
        self.center = self.attachNewNode('center')
        self.center.setZ(0.5)

        self.lastPaintPoint = None
        self.paintDirty = False
        self.flushTask = None
        self.p = None
        self.tex = None

        # A dictionary of player -> count, showing the number of
        # pixels that each player has painted onto this avatar.
        self.players = {}

        self.actor = None
        self.nametag = None
        self.moving = False

        # This is true if this avatar represents the "local avatar",
        # the player at the keyboard, as opposed to a remote player.
        self.localAvatar = False

        # Create an "into" collision sphere so it becomes tangible.
        cs = CollisionSphere(0, 0, 0.5, 0.5)
        cnode = CollisionNode('cnode')
        cnode.addSolid(cs)
        self.cnp = self.attachNewNode(cnode)
        self.cnp.setCollideMask(Globals.AvatarBit)

    def getPlayerId(self):
        return self.playerId

    def setPlayerId(self, playerId):
        self.playerId = playerId

    def setMoving(self, moving):
        """ Updates the moving flag, which changes the animation
        accordingly. """
        
        if moving != self.moving:
            if moving:
                self.actor.loop("run")
            else:
                self.actor.pose("walk", 5)
            self.moving = moving

    def loadModel(self):
        if self.actor:
            self.actor.cleanup()
            
        self.actor = Actor('models/ralph',
                           {'walk' : 'models/ralph-walk',
                            'run' : 'models/ralph-run'})
        self.actor.reparentTo(self)
        self.actor.setScale(0.2)

        # Ralph is modeled facing backward.  Fix that.
        self.actor.setH(180)

        self.__applyPaintTexture()

        # Let's set up a floating nametag too.
        if self.nametag:
            self.nametag.removeNode()
        cardModel = loader.loadModel('models/nametag_card')
        cardTex = cardModel.findTexture('*')
        
        tn = TextNode('nametag')
        tagFont = loader.loadFont('models/one8seven.ttf', okMissing = True)
        if tagFont:
            tn.setFont(tagFont)
        tn.setText(self.player.name)
        tn.setCardColor(self.player.color[0], self.player.color[1], self.player.color[2], 0.6)
        tn.setCardBorder(0.2, 0.2)
        tn.setCardAsMargin(0.4, 0.5, 0.05, -0.15)
        if cardTex:
            tn.setCardTexture(cardTex)
        tn.setTextColor(0, 0, 0, 1)
        tn.setCardDecal(True)
        tn.setAlign(tn.ACenter)
        
        self.nametag = self.attachNewNode(tn)
        self.nametag.setBillboardAxis()
        self.nametag.setLightOff()
        self.nametag.setScale(0.3)
        self.nametag.setPos(0, 0, 1.5)
        

    def __applyPaintTexture(self):
        """ Applies the paintable texture to the avatar. """

        if not self.tex:
            if not TagAvatar.paintTs:
                TagAvatar.paintTs = TextureStage('paintTs')
                TagAvatar.paintTs.setMode(TextureStage.MDecal)
                TagAvatar.paintTs.setSort(10)
                TagAvatar.paintTs.setPriority(10)

            tex = Texture('paint_av_%s' % (self.doId))
            p = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
            p.fill(1)
            p.alphaFill(0)
            myp = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 1)
            myp.fill(0)
            tex.load(p)
            tex.setWrapU(tex.WMClamp)
            tex.setWrapV(tex.WMClamp)

            self.tex = tex
            self.p = p
            self.myp = myp

        if self.actor:
            self.actor.setTexture(TagAvatar.paintTs, self.tex)


    def setupLocalAvatar(self, world):
        """ Sets up this particular avatar as this local client's
        avatar.  This means enabling it as a "from" object in the
        collision traversal.  We only enable the one "from" object on
        each client; each client will take care of its own
        collisions. """

        self.localAvatar = True
        
        self.cnp.setCollideMask(Globals.SelfBit)
        self.cnp.node().setFromCollideMask(Globals.AvatarBit | Globals.WallBit | Globals.WingsBit)

        pusher = CollisionHandlerPusher()
        pusher.setInPattern("%in")
        pusher.addCollider(self.cnp, self)
        world.avTrav.addCollider(self.cnp, pusher)

    def generate(self):
        """ This method is called when the object is generated: when it
        manifests for the first time on a particular client, or when it
        is pulled out of the cache after a previous manifestation.  At
        the time of this call, the object has been created, but its
        required fields have not yet been filled in. """

        # Always call up to parent class
        DistributedSmoothNode.generate(self)

        self.setPythonTag('avId', self.doId)
        
    def announceGenerate(self):
        """ This method is called after generate(), after all of the
        required fields have been filled in.  At the time of this call,
        the distributed object is ready for use. """

        DistributedSmoothNode.announceGenerate(self)

        # We can activate smoothing on this avatar as soon as it's
        # generated.
        self.activateSmoothing(True, False)

        # We also need to start the smooth task, which computes the
        # new smoothed position every frame.  Let's keep this task
        # running as long as the avatar is generated.
        self.startSmooth()

        # Get a pointer to the associated TagPlayer object.  Since
        # there's no guarantee of order between the time TagPlayer and
        # TagAvatar are generated, we might have to wait for it.  The
        # RelatedObjectManager can do that for us.
        self.cr.relatedObjectMgr.requestObjects(
            [self.playerId], allCallback = self.manifestAvatar)

    def manifestAvatar(self, playerList):
        if self.isDisabled():
            # Never mind.
            return
            
        # Store the pointer to the associated TagPlayer.
        self.player = playerList[0]

        # Now that the object has been fully manifested, we can parent
        # it into the scene.
        self.loadModel()
        self.reparentTo(self.cr.avRoot)

    def disable(self):
        """ This method is called when the object is removed from the
        scene, for instance because it left the zone.  It is balanced
        against generate(): for each generate(), there will be a
        corresponding disable().  Everything that was done in
        generate() or announceGenerate() should be undone in disable().

        After a disable(), the object might be cached in memory in case
        it will eventually reappear.  The DistributedObject should be
        prepared to receive another generate() for an object that has
        already received disable().

        Note that the above is only strictly true for *cacheable*
        objects.  Most objects are, by default, non-cacheable; you
        have to call obj.setCacheable(True) (usually in the
        constructor) to make it cacheable.  Until you do this, your
        non-cacheable object will always receive a delete() whenever
        it receives a disable(), and it will never be stored in a
        cache.
        """

        # Stop the smooth task.
        self.stopSmooth()

        # Take it out of the scene graph.
        self.detachNode()

        if self.flushTask:
            taskMgr.remove(self.flushTask)
            self.flushTask = None

        DistributedSmoothNode.disable(self)

    def delete(self):
        """ This method is called after disable() when the object is to
        be completely removed, for instance because the other user
        logged off.  We will not expect to see this object again; it
        will not be cached.  This is stronger than disable(), and the
        object may remove any structures it needs to in order to allow
        it to be completely deleted from memory.  This balances against
        __init__(): every DistributedObject that is created will
        eventually get delete() called for it exactly once. """

        # Clean out self.model, so we don't have a circular reference.
        self.model = None

        DistributedSmoothNode.delete(self)

    def smoothPosition(self):
        """
        This function updates the position of the node to its computed
        smoothed position.  This may be overridden by a derived class
        to specialize the behavior.
        """
        DistributedSmoothNode.smoothPosition(self)

        vel = self.smoother.getSmoothForwardVelocity()
        self.setMoving(vel != 0)


    def clearPaint(self):
        """ Forgets the previous paint point. """
        self.lastPaintPoint = None

    def paint(self, colorBrush, whiteBrush, s, t):
        """ Paints a point on the avatar at texture coordinates (s,
        t). """

        p = self.p
        myp = self.myp
        tex = self.tex

        ix = (s * p.getXSize())
        iy = ((1.0 - t) * p.getYSize())

        lx, ly = ix, iy
        if self.lastPaintPoint:
            lx, ly, ldir = self.lastPaintPoint
            if ldir != dir:
                lx, ly = ix, iy

        # Draw in color directly on the avatar
        p1 = PNMPainter(p)
        p1.setPen(colorBrush)
        p1.drawLine(lx, ly, ix, iy)

        if not self.localAvatar:
            # And draw in white in our personal record
            p2 = PNMPainter(myp)
            p2.setPen(whiteBrush)
            p2.drawLine(lx, ly, ix, iy)
        
        self.lastPaintPoint = (ix, iy, dir)
            
        tex.load(p)
        tex.setWrapU(tex.WMClamp)
        tex.setWrapV(tex.WMClamp)

        self.paintDirty = True
        if not self.flushTask:
            # Spawn a task to send this artwork to the remote client in a
            # little bit.
            self.flushTask = taskMgr.doMethodLater(0.5, self.flushPaint, 'flushPaint')
            
    def flushPaint(self, task):
        if not self.paintDirty:
            return task.done

        tex = self.tex
        p = self.p
        myp = self.myp

        data = StringStream()

        if self.localAvatar:
            # If we're painting on our own avatar, we just broadcast
            # the update immediately.
            p.write(data, Globals.ImageFormat)
            self.sendUpdate('setPaint', [data.getData()])
            self.givePaintCredit(self.player)
        else:
            # If we're painting on some remote avatar, we have to ask
            # him to do the conflict resolution.
            myp.write(data, Globals.ImageFormat)
            self.sendUpdate('userPaint', [data.getData()])
            myp.fill(0)
            
        self.paintDirty = False
        self.flushTask = None
        return task.done

    def getPaint(self):
        if not self.p:
            return ''
        
        data = StringStream()
        self.p.write(data, Globals.ImageFormat)
        return data.getData()

    def setPaint(self, data):
        """ The authoritative client is telling the world about the paint
        results. """
        
        if not data:
            return

        if not self.tex:
            self.__applyPaintTexture()

        p = self.p
        tex = self.tex

        p.read(StringStream(data), Globals.ImageFormat)
        tex.load(p)
        tex.setWrapU(tex.WMClamp)
        tex.setWrapV(tex.WMClamp)

    def givePaintCredit(self, player):
        # Now do the bookkeeping: count up the players who have
        # painted onto this avatar.
        assert self.localAvatar
        
        pcopy = PNMImage(self.p)
        pcopy.removeAlpha()
        hist = pcopy.Histogram()
        pcopy.makeHistogram(hist)

        if player not in self.players:
            self.players[player] = 0
            player.paintedAvatars.append(self)

        for p2 in self.players.keys():
            if p2.localPlayer:
                # We don't count paint on ourselves.
                continue
            
            count = hist.getCount(p2.pixelSpec)
            self.players[p2] = count
            p2.d_avatarPixelCount(self, count)


    def userPaint(self, data):
        """ Sent by a remote client to indicate he/she has painted
        some onto the avatar. """

        player = self.cr.doId2do.get(self.cr.getAvatarIdFromSender())
        color = (0, 0, 0)
        if player:
            color = player.color
        
        myp = PNMImage()
        myp.read(StringStream(data), Globals.ImageFormat)

        colorp = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
        colorp.fill(*color)
        colorp.copyChannel(myp, 0, 0, 3)

        p = self.p
        if not p:
            p = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
            p.fill(1)
            self.p = p

        p.blendSubImage(colorp, 0, 0)
        data = StringStream()
        p.write(data, Globals.ImageFormat)

        self.sendUpdate('setPaint', [data.getData()])

        if self.localAvatar:
            tex = self.tex
            tex.load(p)
            tex.setWrapU(tex.WMClamp)
            tex.setWrapV(tex.WMClamp)

            self.givePaintCredit(player)
    
    def removePlayer(self, player):
        """ This player is going away; remove it from our
        dictionary. """
        
        del self.players[player]

    def setZoneInformation(self, zoneId, visZones):
        """ The AI is telling us what zone we want to be in. """
        self.cr.setInterestZones([1, 2, zoneId] + visZones)
        self.cr.setObjectZone(self, zoneId)
    
        
