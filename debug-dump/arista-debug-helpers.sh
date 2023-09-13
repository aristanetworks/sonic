runcmd() {
   echo ":: BEGIN CMD: $@"
   "$@"
   echo ":: END CMD: $@"
}

dumpfile() {
   local filename="$1"
   echo ":: BEGIN FILE: $filename"
   cat "$filename"
   if [ "$(tail -c 1 "$filename")" != "\n" ]; then
      echo
   fi
   echo ":: END FILE: $filename"
}
