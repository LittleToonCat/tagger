import direct
from pandac.PandaModules import BitMask32

ServerPort = 4430
#ServerHost = 'temp.ddrose.com'
ServerHost = ''
ImageFormat = 't.rgb'

# The directory into which Apache will dump users' uploaded poster
# images.  We should scan this dir from time to time for new images.
#ScanPosterDirectory = '/tmp/posters'
ScanPosterDirectory = '../html/posters'

EnableShaders = False

FadeAlpha = 0.3
FadeTime = 0.5

PaintXSize = 64
PaintYSize = 64

# The max number of players per game.
MaxPlayersPerGame = 20

# The number of players at which a game is considered "ideal"
WantedPlayersPerGame = 12

# You must paint at least this many pixels on a given wall to count as
# having painted it at all.
MinWallPaint = 50

# Number of points per wall section painted
PointsPerWall = 100

# Number of seconds allowed to finish a game
GameLengthSeconds = 210
#GameLengthSeconds = 30

# Name of the music track.
MusicTrackURL = 'http://tagger.ddrose.com/UrbanLegends_UL12-IHS-Knox.ogg'

# Number of seconds of the music track to let hang over the final
# timer reaching 0.
MusicHangSeconds = 9

# Time in seconds remaining at which the clock becomes visible
ShowClockSeconds = 60

# Time in seconds for which the game remains after completion.
GameAfterlifeSeconds = 60

# Extra bonus multiplier for owning a certain number of walls
WallBonus = [
    (160, 5),
    (80, 4),
    (40, 3),
    (20, 2),
    (10, 1.5),
    (0, 1),
]

# Number of points per floor or ceiling section painted
PointsPerFloor = -100

# Number of points per each pixel painted on walls, floors, or ceilings.
PointsPerPixel = 1

# Number of points per each pixel painted on other avatars.
PointsPerAvatarPixel = 10
# Number of points per each pixel painted on other me by other players.
PointsPerMePixel = -1

# Factor to scale pixels by when reporting "paint"
PixelReportFactor = 0.1

# Number of winners to show on the final page.
NumWinnersShow = 5

# Extra bonus points for "art paitings".
ArtPaintingBonus = [ 20000, 10000, 5000 ]

# Keys which are used to control the avatar.
ControlKeys = ['arrow_left', 'arrow_right', 'arrow_up', 'arrow_down',
               'w', 'a', 's', 'd']

# Speed at which avatar controls work.
TurnPerSecond = 200
ForwardPerSecond = 25
BackwardPerSecond = 10

# Controlling the camera chasing.
MaxCameraDistance = 5
CameraPerSecond = 20

# Controlling camera-mouse mode.
CameraPerPixel = 0.1

WallBit = BitMask32.bit(0)
FloorBit = BitMask32.bit(1)
AvatarBit = BitMask32.bit(2)
SelfBit = BitMask32.bit(3)
WingsBit = BitMask32.bit(4)

CamMask = BitMask32.bit(0)
AvBufMask = BitMask32.bit(1)

South = 1
East = 2
North = 4
West = 8
Floor = 16
Ceiling = 32
AllDirs = South | East | North | West
AllDirsList = [ South, East, North, West ]
AllPaintList = [ South, East, North, West, Floor, Ceiling ]

MazeScale = 10
MazeZScale = 7

MazeSquaresPerPlayer = 5
MazeMinSize = 25
#MazeMinSize = 5
