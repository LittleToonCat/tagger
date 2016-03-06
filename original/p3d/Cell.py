from direct.distributed.DistributedObject import DistributedObject
from direct.interval.IntervalGlobal import *
from PosterImage import PosterImage
from pandac.PandaModules import *
import Globals

MazeCells = {}

class Cell(DistributedObject):
    paintTs = TextureStage('paintTs')
    paintTs.setTexcoordName('paint')
    paintTs.setMode(TextureStage.MDecal)
    paintTs.setSort(100)
    paintTs.setPriority(100)

    class WallGeom:
        def __init__(self, geom):
            self.geom = geom
            self.fade = False
            self.fadeIval = None

        def disable(self):
            if self.fadeIval:
                self.fadeIval.finish()
                self.fadeIval = None
                
            if self.geom:
                self.geom.clearTransparency()
                self.geom.clearColorScale()

        def setFade(self, fade):
            """ Sets the fade flag for this wall.  When this is true, the
            wall is mostly transparent so we can see through it to the
            avatar. """

            if fade == self.fade:
                return
            self.fade = fade

            if False:
                if fade:
                    # Make it transparent.
                    self.geom.setTransparency(TransparencyAttrib.MAlpha)
                    #self.geom.setShaderOff(1)
                    self.geom.setColorScale(1, 1, 1, Globals.FadeAlpha)
                else:
                    # Make it opaque again.
                    self.geom.clearTransparency()
                    #self.geom.clearShader()
                    self.geom.clearColorScale()
            else:
                if self.fadeIval:
                    self.fadeIval.finish()
                if fade:
                    # Fade out to transparent.
                    self.geom.setTransparency(TransparencyAttrib.MAlpha)
                    #self.geom.setShaderOff(1)
                    self.fadeIval = Sequence(
                        LerpColorScaleInterval(self.geom, Globals.FadeTime,
                                               (1, 1, 1, Globals.FadeAlpha),
                                               startColorScale = (1, 1, 1, 1),
                                               blendType = 'easeOut'))
                else:
                    # Fade back to opaque.
                    self.fadeIval = Sequence(
                        LerpColorScaleInterval(self.geom, Globals.FadeTime,
                                               (1, 1, 1, 1),
                                               startColorScale = (1, 1, 1, Globals.FadeAlpha),
                                               blendType = 'easeOut'),
                        Func(self.geom.clearTransparency),
                        Func(self.geom.clearColorScale),
                        #Func(self.geom.clearShader),
                        )
                self.fadeIval.start()
    
    def __init__(self, cr):
        DistributedObject.__init__(self, cr)

        self.bits = Globals.AllDirs
        self.sx = None
        self.sy = None
        self.root = None
        self.wallGeoms = {}
        self.posterDir = 0
        self.posterData = ('', 0)
        self.textures = {}
        self.lastPaintPoint = None
        self.paintDirty = 0 # A bitmask of walls
        self.flushTask = None

    def announceGenerate(self):
        DistributedObject.announceGenerate(self)

    def disable(self):
        for wall in self.wallGeoms.values():
            wall.disable()
        if self.root:
            self.root.detachNode()
        if self.flushTask:
            taskMgr.remove(self.flushTask)
            self.flushTask = None

        try:
            del MazeCells[(self.sx, self.sy)]
        except KeyError:
            pass

        DistributedObject.disable(self)

    def delete(self):
        DistributedObject.delete(self)

    def setFade(self, dir, fade):
        """ Sets the fade flag for the indicated wall. """
        if dir in self.wallGeoms:
            self.wallGeoms[dir].setFade(fade)

    def getFade(self, dir):
        """ Returns the fade flag for the indicated wall. """
        if dir in self.wallGeoms:
            return self.wallGeoms[dir].fade
        return False

    def setGeometry(self, bits, sx, sy):
        if self.bits == bits and self.sx == sx and self.sy == sy:
            # We've already got this geometry.  (Assume the poster
            # hasn't changed.)
            return
            
        self.bits = bits
        self.sx = sx
        self.sy = sy

        self.makeGeomCell()

        MazeCells[(sx, sy)] = self

    def makeGeomCell(self):
        """ Generates the renderable and collidable geometry for a
        single cell. """
        
        root = NodePath('%s_%s' % (self.sx, self.sy))
        wallGeoms = {}

        if self.bits & Globals.South:
            self.__loadWall('models/wall', Globals.South, 180, wallGeoms, root)
                           
        if self.bits & Globals.North:
            self.__loadWall('models/wall', Globals.North, 0, wallGeoms, root)

        if self.bits & Globals.West:
            self.__loadWall('models/wall', Globals.West, 90, wallGeoms, root)

        if self.bits & Globals.East:
            self.__loadWall('models/wall', Globals.East, 270, wallGeoms, root)

        self.__loadWall('models/floor', Globals.Floor, 0, wallGeoms, root)
        self.__loadWall('models/ceiling', Globals.Ceiling, 0, wallGeoms, root)

        root.setScale(Globals.MazeScale, Globals.MazeScale, Globals.MazeZScale)
        root.setPos(self.sx * Globals.MazeScale, self.sy * Globals.MazeScale, 0)
        root.flattenLight()

        root.setPythonTag('cell', (self.sx, self.sy))
        root.setTag('paintType', 'cell')

        root.reparentTo(self.cr.mazeRoot)
        if self.root:
            self.root.removeNode()
        self.root = root
        self.wallGeoms = wallGeoms

        for dir, (tex, p, myp, lastp) in self.textures.items():
            if tex:
                # Re-apply the paint texture onto this wall.
                wall = self.wallGeoms[dir].geom
                wall.setTexture(Cell.paintTs, tex)
                if Globals.EnableShaders:
                    s = loader.loadShader('models/paint_normal.sha')
                    wall.setShader(s)

    def __loadWall(self, modelName, dir, rotate, wallGeoms, root):
        """ Loads a wall from the egg file. """
        wall = loader.loadModel(modelName)
        wall.setH(rotate)
        wall.setPos(0.5, 0.5, 0)
        wall.setPythonTag('step', (self.sx, self.sy, dir))
        wall.setName('wall_%s' % (dir))
        wall.reparentTo(root)

        if dir == self.posterDir:
            print "Applying poster to %s, %s" % (self.sx, self.sy)
            applyPoster(wall, self.posterData)

        wallGeoms[dir] = self.WallGeom(wall)

    def __applyPaintTexture(self, dir):
        """ Applies the paintable texture to the indicated wall
        geometry. """

        p = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
        p.fill(1)
        p.alphaFill(0)

        tex = Texture('paint_%s_%s_%s' % (self.sx, self.sy, dir))
        tex.load(p)
        tex.setWrapU(tex.WMClamp)
        tex.setWrapV(tex.WMClamp)

        self.textures[dir] = (tex, p, None, None)
        wall = self.wallGeoms[dir].geom
        wall.setTexture(Cell.paintTs, tex)

        if Globals.EnableShaders:
            s = loader.loadShader('models/paint_normal.sha')
            wall.setShader(s)
        base.wall = wall

    def clearPaint(self):
        """ Forgets the previous paint point. """
        self.lastPaintPoint = None

    def paint(self, colorBrush, whiteBrush, px, py, pz, dir):
        """ Paints a point on the wall within the cell given by px,
        py, pz, in the range 0 .. 1. """

        # The t coordinate is usually the same as z.
        t = pz
        if dir == Globals.East:
            s = 1.0 - py
        elif dir == Globals.West:
            s = py
        elif dir == Globals.North:
            s = px
        elif dir == Globals.South:
            s = 1.0 - px
        elif dir == Globals.Floor:
            s = px
            t = py
        elif dir == Globals.Ceiling:
            s = px
            t = 1.0 - py
        else:
            # Something else?
            assert(False)

        tex, p, myp, lastp = self.textures.get(dir, (None, None, None, None))
        if not tex:
            # No texture on this wall yet.
            self.__applyPaintTexture(dir)
            tex, p, myp, lastp = self.textures[dir]
        if not myp:
            myp = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 1)
            myp.fill(0)
            self.textures[dir] = (tex, p, myp, lastp)

        ix = (s * p.getXSize())
        iy = ((1.0 - t) * p.getYSize())

        lx, ly = ix, iy
        if self.lastPaintPoint:
            lx, ly, ldir = self.lastPaintPoint
            if ldir != dir:
                lx, ly = ix, iy

        # Draw in color directly on the wall
        p1 = PNMPainter(p)
        p1.setPen(colorBrush)
        p1.drawLine(lx, ly, ix, iy)

        # And draw in white in our personal record
        p2 = PNMPainter(myp)
        p2.setPen(whiteBrush)
        p2.drawLine(lx, ly, ix, iy)
        
        self.lastPaintPoint = (ix, iy, dir)
            
        tex.load(p)
        tex.setWrapU(tex.WMClamp)
        tex.setWrapV(tex.WMClamp)

        self.paintDirty |= dir
        if not self.flushTask:
            # Spawn a task to send this artwork to the server in a
            # little bit.
            self.flushTask = taskMgr.doMethodLater(0.5, self.flushPaint, 'flushPaint')
            
    def flushPaint(self, task):
        if not self.paintDirty:
            return task.done

        for dir in Globals.AllPaintList:
            if not self.paintDirty & dir:
                continue
            
            tex, p, myp, lastp = self.textures[dir]
            if myp:
                data = StringStream()
                myp.write(data, Globals.ImageFormat)
                self.sendUpdate('userPaint', [dir, data.getData()])
            self.textures[dir] = (tex, p, None, myp)
            if myp is None:
                # Don't clear the dirty bit until we have fully
                # flushed our local paint out of the system.
                self.paintDirty &= ~dir

        if self.paintDirty:
            # Check back later to see if more flushing is needed.
            return task.again

        self.flushTask = None
        return task.done
            
    def setPaintSouth(self, data):
        return self.__setPaint(Globals.South, data)

    def setPaintNorth(self, data):
        return self.__setPaint(Globals.North, data)

    def setPaintEast(self, data):
        return self.__setPaint(Globals.East, data)

    def setPaintWest(self, data):
        return self.__setPaint(Globals.West, data)

    def setPaintFloor(self, data):
        return self.__setPaint(Globals.Floor, data)

    def setPaintCeiling(self, data):
        return self.__setPaint(Globals.Ceiling, data)

    def __setPaint(self, dir, data):
        if not data:
            return
        
        tex, p, myp, lastp = self.textures.get(dir, (None, None, None, None))
        if not tex:
            # No texture on this wall yet.
            self.__applyPaintTexture(dir)
            tex, p, myp, lastp = self.textures[dir]

        p.read(StringStream(data), Globals.ImageFormat)
        #p.write('paint.png')

        # Also, apply any colors we've recently painted but haven't
        # flushed yet.
        if self.cr.player:
            if myp or lastp:
                colorp = PNMImage(Globals.PaintXSize, Globals.PaintYSize, 4)
                colorp.fill(*self.cr.player.color)

                if lastp:
                    colorp.copyChannel(lastp, 0, 0, 3)
                    p.blendSubImage(colorp, 0, 0)

                if myp:
                    colorp.copyChannel(myp, 0, 0, 3)
                    p.blendSubImage(colorp, 0, 0)

        tex.load(p)
        tex.setWrapU(tex.WMClamp)
        tex.setWrapV(tex.WMClamp)

    def setPoster(self, posterDir, posterData):
        if self.posterDir == posterDir and self.posterData == posterData:
            # Nothing new.
            return
        
        # Remove the previous poster, if any.
        if self.posterDir:
            wall = self.wallGeoms[self.posterDir].geom
            applyPoster(wall, ('', 0))
            
        self.posterDir = posterDir
        self.posterData = posterData

        # Now apply the new poster, if any.
        if self.posterDir:
            self.makeGeomCell()

def applyPoster(wall, posterData):
    """ Apply a poster to the wall."""
    # First, remove the old poster, if any.
    frameModel = wall.find('poster')
    if frameModel:
        frameModel.removeNode()

    # Now decode and apply the new poster.
    data, aspect = posterData
    if not data:
        return

    data = StringStream(data)
    p = PNMImage()
    if not p.read(data):
        return
    
    tex = Texture('poster')
    if not tex.load(p):
        return

    posterModel = loader.loadModel('models/poster')
    frameModel = loader.loadModel('models/frame')
    frameModel.flattenLight()
    g1 = wall.find('**/+GeomNode')
    g2 = posterModel.find('**/+GeomNode')
    g1.setEffect(DecalEffect.make())
    g2.reparentTo(g1)
    g2.setShaderOff()
    frameModel.setName('poster')
    frameModel.reparentTo(wall)
    wallAspect = float(Globals.MazeZScale) / float(Globals.MazeScale)
    if aspect > 1:
        g2.setScale(wallAspect, 1, 1.0 / aspect)
        g2.setTexScale(Cell.paintTs, wallAspect, 1.0 / aspect)
        frameModel.setScale(wallAspect, 1, 1.0 / aspect)
        frameModel.setTexScale(Cell.paintTs, wallAspect, 1.0 / aspect)
    else:
        g2.setScale(aspect * wallAspect, 1, 1)
        g2.setTexScale(Cell.paintTs, aspect * wallAspect, 1)
        frameModel.setScale(aspect * wallAspect, 1, 1)
        frameModel.setTexScale(Cell.paintTs, aspect * wallAspect, 1)
    g2.setTexOffset(Cell.paintTs, 0.5, 0.45)
    frameModel.setTexOffset(Cell.paintTs, 0.5, 0.45)
    g2.setPos(0, 0, 0.45)
    frameModel.setPos(0, 0, 0.45)
    g2.setTexture(tex)
    

def makeArtCard(dir, name, color, posterData, imgData, bonus):
    """ Returns a card showing the art painting. """

    p = PNMImage()
    p.read(StringStream(imgData), Globals.ImageFormat)

    tex = Texture('art_card')
    tex.load(p)
    tex.setWrapU(tex.WMClamp)
    tex.setWrapV(tex.WMClamp)

    if dir == Globals.Ceiling:
        wall = loader.loadModel('models/ceiling')
        wall.setP(-90)
        wall.setZ(0.5)
    elif dir == Globals.Floor:
        wall = loader.loadModel('models/floor')
        wall.setP(90)
        wall.setZ(0.5)
    else:
        wall = loader.loadModel('models/wall')
        wallAspect = float(Globals.MazeZScale) / float(Globals.MazeScale)
        wall.setScale(1, 1, wallAspect)
    wall.setTexture(Cell.paintTs, tex)

    data, aspect = posterData
    if data:
        applyPoster(wall, posterData)
    wall.flattenLight()

    # Create a label right below the wall.
    tn = TextNode('name')
    tn.setText('\1tag\1%s\2\n+ %s' % (name, bonus))
    tn.setTextColor(0, 0, 0, 1)
    tn.setAlign(tn.ACenter)
    tn.setCardAsMargin(0.2, 0.2, 0.05, -0.15)
    tn.setCardColor(color[0], color[1], color[2], 1)
    tn.setFrameColor(0, 0, 0, 1)

    hscale = 0.12
    vscale = 0.12

    # Widen the card to match the wall geometry.
    card = tn.getCardActual()
    if card[1] > 0.5/hscale:
        hscale = 0.5 / card[1]
    card = VBase4(-0.5/hscale, 0.5/hscale, card[2], card[3])
    tn.setCardActual(*card)
    tn.setFrameActual(*card)

    name = wall.attachNewNode(tn)
    name.setScale(hscale, hscale, vscale)
    name.setPos(0, 0, -0.15)

    return wall



