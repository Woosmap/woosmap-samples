# Woosmap Distance API Java client

A single-file Java 11 client for the synchronous Distance Matrix endpoint. Jackson parses the response.

```sh
export WOOSMAP_PRIVATE_KEY=...
mvn clean compile exec:java -Dexec.mainClass="com.example.WoosmapDistanceApiClient"
```

The example computes driving distance and duration from one origin in Paris to three destinations and
prints them. For matrices beyond a few hundred elements, use the asynchronous samples in the parent folder.
