#!/bin/bash
# Prevent session crash when a user submits only an image with no text.
# Claude requires at least some text alongside an image; an empty prompt
# causes the session to bomb. We inject a neutral default so the model
# receives a valid text+image message.

input=$(cat)

prompt=$(echo "$input" | jq -r '.prompt // ""')

# Non-empty prompt — nothing to do.
if [[ -n "$prompt" ]]; then
  exit 0
fi

image_count=$(echo "$input" | jq '.images | length // 0')

if [[ "$image_count" -gt 0 ]]; then
  echo '{"decision":"continue","prompt":"Please analyze this image."}'
fi

exit 0
