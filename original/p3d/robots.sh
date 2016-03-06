#! /bin/bash
prefix="$1"
count="$2"

if [ -z "$count" ]; then
  echo "Count required."
  exit 1
fi

rm -f robot_$prefix[0-9]*.log

i=0
while [ $i -lt "$count" ]; do
  rm -f robot_$prefix$i.log
  echo "python main.py -r robot_$prefix$i -l robot_$prefix$i.log"
  python main.py -r robot_$prefix$i -l robot_$prefix$i.log 2>&1 >dev.null &
  sleep 10
  i=`expr $i + 1`
done
