package com.example;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

public class WoosmapDistanceApiClient {

    private static final String API_KEY = "YOUR_WOOSMAP_API_KEY";
    private static final String BASE_URL = "https://api.woosmap.com/distance/distancematrix/json";

    public static void main(String[] args) {
        try {
            String origins = "48.836,2.237"; // Example: Paris coordinates
            String destinations = "48.709,2.403|48.768,2.338|49.987,2.223"; // Example multiple destinations
            String mode = "driving"; // Optional: mode of transport
            String language = "en"; // Optional: language
            String units = "metric"; // Optional: units
            String elements = "duration_distance"; // Optional: elements
            String method = "time"; // Optional: method

            String url = String.format("%s?origins=%s&destinations=%s&private_key=%s&mode=%s&language=%s&units=%s&elements=%s&method=%s",
                    BASE_URL,
                    URLEncoder.encode(origins, StandardCharsets.UTF_8),
                    URLEncoder.encode(destinations, StandardCharsets.UTF_8),
                    URLEncoder.encode(API_KEY, StandardCharsets.UTF_8),
                    URLEncoder.encode(mode, StandardCharsets.UTF_8),
                    URLEncoder.encode(language, StandardCharsets.UTF_8),
                    URLEncoder.encode(units, StandardCharsets.UTF_8),
                    URLEncoder.encode(elements, StandardCharsets.UTF_8),
                    URLEncoder.encode(method, StandardCharsets.UTF_8));

            HttpClient client = HttpClient.newHttpClient();
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(new URI(url))
                    .GET()
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                parseAndPrintResponse(response.body());
            } else {
                System.out.println("Error: " + response.statusCode());
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static void parseAndPrintResponse(String responseBody) {
        try {
            ObjectMapper objectMapper = new ObjectMapper();
            JsonNode rootNode = objectMapper.readTree(responseBody);
            String status = rootNode.path("status").asText();

            if (!"OK".equals(status)) {
                System.out.println("Error: " + responseBody);
                return;
            }

            JsonNode rows = rootNode.path("rows");

            for (int i = 0; i < rows.size(); i++) {
                JsonNode row = rows.get(i);
                JsonNode elements = row.path("elements");
                System.out.println("Origin " + (i + 1) + ":");
                for (int j = 0; j < elements.size(); j++) {
                    JsonNode element = elements.get(j);
                    String elementStatus = element.path("status").asText();
                    if ("OK".equals(elementStatus)) {
                        double distance = element.path("distance").path("value").asDouble();
                        String distanceText = element.path("distance").path("text").asText();
                        double duration = element.path("duration").path("value").asDouble();
                        String durationText = element.path("duration").path("text").asText();
                        System.out.println("  Destination " + (j + 1) + ":");
                        System.out.println("    Distance: " + distance + " meters (" + distanceText + ")");
                        System.out.println("    Duration: " + duration + " seconds (" + durationText + ")");
                    } else {
                        System.out.println("  Destination " + (j + 1) + " Error: " + elementStatus);
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}