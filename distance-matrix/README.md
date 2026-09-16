# Distance matrices

## Large matrices, asynchronously (Python, Node)

For hundreds or thousands of origin-destination pairs, use the
[async endpoints](https://developers.woosmap.com/products/distance-api/features/matrix_async/): submit,
poll the status, fetch the result. Two CSV files in, one CSV out with a row per pair.

```sh
pip install -r python/requirements.txt
python python/async_matrix.py matrix.csv --origins origins.csv --destinations destinations.csv --mode driving
python python/async_matrix.py matrix.csv --matrix-id 74b4265e-c102-4178-b483-9111b2342443

node node/async-matrix.mjs matrix.csv --origins origins.csv --destinations destinations.csv
```

The job runs on Woosmap's side and its result stays available after the script exits: the submitted
`matrix_id` is printed, and `--matrix-id` resumes the polling without submitting, and paying for, a
second job. Input files hold one `lat,lng` per line, a header row is skipped. Output columns: `origin_index`,
`destination_index`, `status`, `distance_m`, `duration_s`.

The result endpoint answers `303` to a signed, gzipped file that both runtimes follow and decompress
transparently. Its body is not the synchronous `rows/elements` shape: it carries `matrix.travelTimes`
and `matrix.distances` as flat row-major arrays, plus `matrix.errorCodes` when some pairs failed. The
scripts unfold them into pairs for you.

## Small matrices, synchronously (Java)

`java/` is a minimal Java 11 client for `GET /distance/distancematrix/json`, fit for a handful of
destinations in a request-response flow. It reads the key from `WOOSMAP_PRIVATE_KEY`.

```sh
cd java
mvn clean compile exec:java -Dexec.mainClass="com.example.WoosmapDistanceApiClient"
```
