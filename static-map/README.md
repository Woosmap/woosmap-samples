# Static map for an e-mail or a PDF

Order confirmations, appointment reminders and delivery notes want a small map of the store. Rendering it
server-side with the [Static Map API](https://developers.woosmap.com/products/map-static-api/get-started/)
and attaching the image keeps your API key out of the message.

```sh
pip install -r python/requirements.txt
python python/static_map.py --lat 51.919948 --lng 4.486843 --zoom 15 \
  --marker 51.919948,4.486843 --retina --output store.webp
python python/static_map.py --lat 48.85 --lng 2.35 --zoom 12 --width 800 --height 300 \
  --marker "48.86,2.34,https://example.com/pin@2x.png" --marker 48.84,2.37
```

The API returns WebP. Most webmail and mobile clients render it; classic Outlook does not, convert with
Pillow or ImageMagick if that audience matters.

The script also prints the equivalent URL with a `key=YOUR_PUBLIC_KEY` placeholder, for pages where an
`<img src>` with a referer-restricted public key is the better fit.
