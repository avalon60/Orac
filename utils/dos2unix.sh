for dir in bin src apps project_lib features resources samples js
do
   echo "Processing directory: $dir"
   for type in md py sh js gitignore
   do
     find $dir -name "*.$type" -exec dos2unix "{}" ";"
   done
done
