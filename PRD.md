## 1. Crawler Workflow

### Crawler Workflow Implementation Steps
**Initialization Phase**
1. Start the crawler process by initializing the database connection (PostgreSQL/MySQL) and PDF file storage configuration. Prepare a crawl status table to track the progress of each scraped entity.

**Phase 1: Subject Data Retrieval**
2. Send an HTTP GET request to the `/Subjek` endpoint to retrieve the list of available subjects.
3. Extract data from the response, collecting the following attributes for each subject:
- `Nama`: Full name of the subject
- `tema ID`: Unique identifier for the theme/subject
- `URL pencarian`: Base URL for performing searches related to the subject
4. Temporarily store all extracted subject data for further processing, and update the crawl status for each subject to "subjek_extracted".

**Phase 2: Regulation List Search and Extraction**
5. For each extracted subject, construct the full search URL by appending the `tema` parameter to the `/Search?tema=` endpoint, using the `tema ID` as the parameter value.
6. Send an HTTP GET request to the constructed search URL.
7. Extract all regulation data from the search page; identify and handle the pagination mechanism to retrieve all search result pages (ensure no regulations are missed, even if they span multiple pages).
8. Store all extracted regulation data along with the necessary detail IDs for accessing detail pages, and update the crawl status to "peraturan_list_extracted".

**Phase 3: Detail and PDF Document Retrieval**
9. For each discovered regulation, construct the detail page URL by populating the appropriate parameters for the `/Details//` endpoint (complete the path according to the correct endpoint structure to access specific regulation details).
10. Send an HTTP GET request to the regulation detail URL. 11. Extract all regulation metadata from the detail page and retrieve the available PDF download link.
12. Download the PDF file using the extracted link, save the file to the configured storage system, and record the file storage path in the database.

**Storage and Final Status Tracking Phase**
13. Persist all collected data (subject data, regulation data, regulation metadata, and PDF storage path) into a PostgreSQL or MySQL database according to the predefined schema.
14. Update the crawl status for each successfully processed regulation to "completed" and record the completion timestamp for auditing purposes.
15. Implement error handling for each stage: if an HTTP request, data extraction, or PDF download fails, update the crawl status to "failed" and log the error message for debugging.
16. Implement rate limiting for HTTP requests to avoid overloading the target server, and include a retry mechanism for transient failures (maximum of 3 attempts with a delay between them).
17. Once all subjects and regulations have been processed, terminate the crawler process by generating a summary report that includes the total number of successfully processed entities, the number of failures, and the total number of successfully downloaded PDF files.
