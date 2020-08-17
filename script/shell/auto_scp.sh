#!/bin/bash
this_dir=`pwd`
# echo "$this_dir ,this is pwd"
# echo "$0 ,this is \$0"
dirname $0|grep "^/" >/dev/null
if [ $? -eq 0 ];then
       this_dir=`dirname $0`
else
dirname $0|grep "^\." >/dev/null
retval=$?
if [ $retval -eq 0 ];then
       this_dir=`dirname $0|sed "s#^.#$this_dir#"`
else
       this_dir=`dirname $0|sed "s#^#$this_dir/#"`
fi
fi

status=0

if [  -f  $1  ] && [  -f  $2 ]; then
   status=0
else	
   echo "script args err, except filename \$hosts  and  \$filename_conf."
   status=1
   exit $status

fi



host=$1
file_conf=$2

cat $host | while read line
do
   cat $file_conf | while read file
   do
     src_file=`echo  $file | awk '{print $1}'`
     dest_file=`echo  $file | awk '{print $2}'`
     host_ip=`echo $line | awk '{print $1}'`
     username=`echo $line | awk '{print $2}'`
     password=`echo $line | awk '{print $3}'`
     echo "$host_ip"
     $this_dir/scp_log.sh  $host_ip $username $password $src_file $dest_file
     if [ "$?" != 0 ]; then
	 echo "scp script err!"
	 status=1
     else
	 status=0
     fi
   done
done


exit $status

