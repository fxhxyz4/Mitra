#!/bin/sh

set -e

rm -f /tmp/ready
ollama serve &
pid=$!

until ollama list >/dev/null 2>&1; do
  sleep 1
done

for model in $OLLAMA_PULL; do
  ollama pull "$model"
done

touch /tmp/ready
wait "$pid"
