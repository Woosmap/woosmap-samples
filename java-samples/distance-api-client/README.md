# Woosmap Distance API Client

This is a simple Java client to interact with the Woosmap Distance API.

## Prerequisites

- Java 11 or later
- Maven

## Setup

1. Clone the repository.
2. Replace `YOUR_WOOSMAP_API_KEY` in `WoosmapDistanceApiClient.java` with your actual Woosmap API key.

## Build and Run

```sh
mvn clean install
mvn exec:java -Dexec.mainClass="com.example.WoosmapDistanceApiClient"
```

## Example

The client sends a request to the Woosmap Distance API to calculate the distance and duration between Paris and London.

## Dependencies

- Jackson Databind for JSON parsing