from pandac.PandaModules import *
from direct.fsm.FSM import FSM
import random

class RobotPlayer(FSM):
    """ This class takes over the controls and starts moving the local
    character around and painting at random, for the purposes of
    simulating a crowded playfield. """

    WindowSize = (256, 256)

    def __init__(self, cr):
        FSM.__init__(self, 'robot')
        self.cr = cr

        # Allow a lot of time for other processes.
        base.setSleep(0.1)
        
        self.mouse = VirtualMouse('vmouse')
        self.mouse.setWindowSize(*self.WindowSize)
        
        np = base.dataRoot.attachNewNode(self.mouse)

        if base.mouseWatcher:
            base.mouseWatcher.reparentTo(np)
        else:
            base.mouseWatcher = np.attachNewNode(MouseWatcher('watcher'))
            base.mouseWatcherNode = base.mouseWatcher.node()
            bt = base.mouseWatcher.attachNewNode(ButtonThrower('buttons'))
            base.camera = NodePath('camera')
            base.cam = base.camera.attachNewNode(Camera('cam'))
            base.camNode = base.cam.node()

        self.task = None

        self.accept(self.cr.uniqueName('gameOver'), self.gameOver)
        self.request('Idle')

    def gameOver(self):
        messenger.send(self.cr.uniqueName('resetGame'))

    def changeRobotState(self, task):
        state = random.choice(['Paint', 'Forward', 'Left', 'Right'])
        self.request(state)

    def enterIdle(self):
        taskMgr.doMethodLater(2, self.changeRobotState,
                              'changeRobotState')

    def exitIdle(self):
        pass

    def enterPaint(self):
        self.mousePos = (128, 128)
        self.mouse.setMouseOn(True)
        self.mouse.pressButton(MouseButton.one())
        self.task = taskMgr.add(self.robotPaint, 'robotPaint')

        taskMgr.doMethodLater(random.uniform(2, 5), self.changeRobotState,
                              'changeRobotState')

    def exitPaint(self):
        taskMgr.remove(self.task)
        self.mouse.setMouseOn(False)
        self.mouse.releaseButton(MouseButton.one())

    def enterForward(self):
        self.mouse.pressButton(KeyboardButton.up())

        taskMgr.doMethodLater(random.uniform(0, 3), self.changeRobotState,
                              'changeRobotState')

    def exitForward(self):
        self.mouse.releaseButton(KeyboardButton.up())

    def enterLeft(self):
        self.mouse.pressButton(KeyboardButton.left())

        taskMgr.doMethodLater(random.uniform(0, 1), self.changeRobotState,
                              'changeRobotState')

    def exitLeft(self):
        self.mouse.releaseButton(KeyboardButton.left())

    def enterRight(self):
        self.mouse.pressButton(KeyboardButton.right())

        taskMgr.doMethodLater(random.uniform(0, 1), self.changeRobotState,
                              'changeRobotState')

    def exitRight(self):
        self.mouse.releaseButton(KeyboardButton.right())

    def robotPaint(self, task):
        x, y = self.mousePos
        self.mousePos = (x + random.randint(-5, 5),
                         y + random.randint(-5, 5))
        self.mouse.setMousePos(*self.mousePos)
        return task.cont
    
