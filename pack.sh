#! /bin/bash
#
# pack.sh [opts]
# 
# Options:
#
#  -s "host"
#  -p for production
#
#ENDCOMMENT

host=
production=
while getopts hs:p flag; do
  case $flag in
    h)  sed '/#ENDCOMMENT/,$d' <$0 >&2; exit 1;;
    s)  host="$OPTARG";;
    p)  production=1;;
    \?) exit 1;
  esac
done

if [ -z "$production" ]; then
  audio=
  script_origin="localhost"
  default_host="drose"
else
  audio="-rfmod"
  script_origin="tagger.ddrose.com"
  default_host="cmu"
fi

if [ -z "$host" ]; then
  host="$default_host"
fi

if [ "$host" = "drose" ]; then
  p3dstage=~/p3dstage
  packer="$DIRECT/built/bin/packp3d -s $p3dstage"
elif [ "$host" = "cmu" ]; then
  if [ -d /Developer ]; then
    packer=/Developer/Tools/Panda3D/packp3d
  else
    packp3d=~/packp3d_cmu.p3d
    packer="panda3d $packp3d"
  fi
else
  echo "Unknown host: $host"
  exit 1
fi

echo "Building for host $host, production: $production"

$packer -o ~/src/tagger/html/tagger.p3d -d ~/src/tagger/p3d -S ~/mycert.pem $audio -c script_origin="${script_origin}"
