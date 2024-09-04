# Woosmap Distance API Client

This is a simple Java client to interact with the Woosmap Distance API.

## Prerequisites

- Java 11 or later
- Maven

## Setup

1. Clone the repository.
2. Replace `YOUR_WOOSMAP_API_KEY` in `WoosmapDistanceApiClient.java` with your actual Woosmap Private API key.

## Build and Run

```sh
mvn clean install
mvn exec:java -Dexec.mainClass="com.example.WoosmapDistanceApiClient"
```

## Example

The client sends a request to the Woosmap Distance API to calculate the distance and duration between Paris and multiple
destinations. Example of output:

```shell
[INFO] --- exec:3.0.0:java (default-cli) @ woosmap-distance-api-client ---
Origin 1:
  Destination 1:
    Distance: 24090.0 meters (24.1 km)
    Duration: 1652.0 seconds (28 mins)
  Destination 2:
    Distance: 15880.0 meters (15.9 km)
    Duration: 1095.0 seconds (18 mins)
  Destination 3:
    Distance: 153263.0 meters (153 km)
    Duration: 7331.0 seconds (2 hours 2 mins)
[INFO] ------------------------------------------------------------------------
```

## Dependencies

- Jackson Databind for JSON parsing