# Nearest stores from an IP address

Pre-fill "your store" on a landing page or route a support ticket to the right shop, before the visitor
has typed anything. The [Geolocation stores endpoint](https://developers.woosmap.com/products/geolocation-api/stores/)
locates the IP and runs a Stores Search around it in one call.

```sh
pip install -r python/requirements.txt
python python/nearest_stores_by_ip.py 145.94.1.1 --limit 3 --radius 50000
python python/nearest_stores_by_ip.py 2001:db8::1 --query 'type:"grocery"' --json
```

Prints the resolved city and accuracy, then one line per store with its distance in metres. Stores are
only returned when the IP resolves to within 20 km accuracy, so a datacentre or mobile-carrier IP often
yields a location without stores. Treat the result as a suggestion the visitor can correct.
