# Spec: example-data

## Purpose

Defines the example JSON input files bundled with the repository for testing batching behaviour, deduplication, and malformed-record handling against the mock server.

## Requirements

### Requirement: Large example files are available for testing batching behaviour
The repository SHALL include at least two additional example JSON input files beyond the minimal `examples/responses.json`:
- `examples/responses_large.json`: 100 valid records
- `examples/responses_batch_demo.json`: 300 records including at least one pre-seeded duplicate ID (matching the mock server), at least one malformed record, and enough total records to exercise at least 3 query batches and 3 upload batches with the default batch size of 100

#### Scenario: Large file processes without error against the mock server
- **WHEN** `make run INPUT=examples/responses_large.json` is executed against the running mock server
- **THEN** the process exits with code 0 and logs a summary showing 100 records read

#### Scenario: Batch demo file demonstrates batching and deduplication
- **WHEN** `make run INPUT=examples/responses_batch_demo.json` is executed against the running mock server
- **THEN** the summary log shows at least 1 existing record, at least 1 skipped record, and uploaded count < total read count

#### Scenario: Batch demo file includes a pre-seeded duplicate
- **WHEN** `examples/responses_batch_demo.json` is read
- **THEN** it contains a record with `responseId` matching the mock server's pre-seeded ID (`11111111-1111-1111-1111-111111111111`)

#### Scenario: Batch demo file includes a malformed record
- **WHEN** `examples/responses_batch_demo.json` is read by `read_responses`
- **THEN** at least one record is skipped due to missing or invalid required fields
