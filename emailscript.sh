# exact path might need to change, probably not though
for file in ./emails/*; do
  curl -X POST \
    -F "file=@./emails/${file}.csv"
  # add url
  # DO NOT CHANGE /measurements/govee
  https://airguard.com/measurements/govee

  mkdir -p ./emails/read

  mv ./emails/file ./emails/read/file
done
