# GOP Data Center Voter Lookup

Automated voter lookup script for the GOP Data Center website using Playwright browser automation.

## Features

- Secure credential storage with encryption
- Automated login and search
- Bulk voter searches
- Export results to JSON or CSV
- Runs headless by default (no browser window)
- Debug mode for troubleshooting with visible browser
- Search filters (address, city, zip, phone, voter ID)
- Optional detailed voter information extraction from individual voter pages
- Direct links to voter detail pages for manual browsing
- Google Sheets integration for bulk processing and automated data updates

## Installation

### Using uv (Recommended)

1. Install [uv](https://github.com/astral-sh/uv) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repository
```bash
git clone <repository-url>
cd gop-data-center
```

That's it! The script will automatically install dependencies and browsers when you run it.


## Usage

The script operates in two modes:

1. **Command Line Mode**: Search specific voters by providing names as arguments
2. **Google Sheets Mode**: Bulk process voters from a Google Sheet using `--sheets`

### Command Line Mode

#### With uv (Recommended)
Search for a single voter:
```bash
./gop_voter_lookup.py "John Doe"
```

Or use uv run directly:
```bash
uv run gop_voter_lookup.py "John Doe"
```

Search for multiple voters:
```bash
./gop_voter_lookup.py "John Doe" "Jane Smith" "Robert Johnson"
```

### First Run
On first run, the script will prompt for your GOP Data Center credentials:
```
GOP Data Center credentials not found.
Please enter your credentials (they will be encrypted and saved locally)
Username: your_username
Password: [hidden input]
```

Credentials are encrypted and stored locally in `.credentials` (excluded from git).

### Command Line Options

All examples below work with both `./gop_voter_lookup.py` (uv) or `python gop_voter_lookup.py`:

```bash
# Basic search (runs in headless mode by default)
./gop_voter_lookup.py "John Doe"

# Debug mode: shows browser and keeps it open for troubleshooting
./gop_voter_lookup.py "John Doe" --debug

# Export results to JSON
./gop_voter_lookup.py "John Doe" --export json --output results.json

# Export results to CSV
./gop_voter_lookup.py "John Doe" --export csv --output results.csv

# Search with filters
./gop_voter_lookup.py "John Doe" --city Houston --zip 77001

# Extract detailed voter information (slower but more comprehensive)
./gop_voter_lookup.py "John Doe" --extract-details

# Combine detailed extraction with other options
./gop_voter_lookup.py "John Doe" --extract-details --export json --output detailed_results.json

# Delete stored credentials
./gop_voter_lookup.py --delete-credentials
```

### Available Options

#### Search Filters
- `--address`: Filter by address
- `--city`: Filter by city
- `--zip`: Filter by zip code
- `--phone`: Filter by phone number
- `--voter-id`: Filter by voter ID

#### Additional Options
- `--extract-details`: Extract comprehensive voter information from individual detail pages (slower)
- `--debug`: Show browser window and detailed debugging information
- `--export`: Export results to JSON or CSV format
- `--output`: Specify output filename for exports

#### Google Sheets Integration
- `--sheets`: Enable Google Sheets integration mode
- `--spreadsheet-id`: Google Sheets spreadsheet ID (required with --sheets)
- `--sheet-name`: Sheet name within spreadsheet (default: "Sheet1")
- `--name-column`: Column containing voter names (default: "A")
- `--start-row`: Row to start reading names from (default: 2)
- `--results-start-column`: Column to start adding voter data (required with --sheets)
- `--row-limit`: Limit number of voter lookups (skips empty rows)

## Security

- Credentials are encrypted using Fernet symmetric encryption
- Encryption key is stored separately from credentials
- Both files have restricted permissions (600)
- Never commit `.credentials` or `.key` files

## Output Format

### Console Output
```
Searching for: John Doe
Found 1 result(s)

=== Results for John Doe ===

Result 1:
  name: DOE, JOHN M.
  address: 123 Main St
  city: Houston
  state: TX
  zip_code: 77001
  phone: (713)555-1234
  date_of_birth: 05/15/1965
  calculated_party: 2 - Soft Republican
  📄 View Full Details: https://www.gopdatacenter.com/rnc/RecordLookup/RecordMaintenance.aspx?id=12345
```

The "📄 View Full Details" link provides direct access to the voter's complete profile page on the GOP Data Center, allowing you to manually browse additional information or verify the automated extraction results.


## Google Sheets Integration

The script can integrate with Google Sheets to automatically read voter names from a spreadsheet and update it with voter data. This is perfect for bulk processing of voter lists.

### Setup

1. **Enable Google Sheets API**: The script will walk you through the setup if no credentials are detected.

2. **Prepare your spreadsheet**:
   - Create a Google Sheet with voter names in column A (starting from row 2)
   - Add headers in row 1 for the data you want to populate
   - Note the spreadsheet ID from the URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
   - **For Service Account**: Share the sheet with the service account email (Editor permissions)

### Google Sheets Mode Usage

**Note**: When using `--sheets`, you don't need to provide voter names as command line arguments - they are read from your spreadsheet.

```bash
# Basic Google Sheets integration (reads names from column A, adds data starting from column C)
./gop_voter_lookup.py --sheets --spreadsheet-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" \
  --results-start-column "C"

# Specify custom sheet name and name column
./gop_voter_lookup.py --sheets --spreadsheet-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" \
  --sheet-name "Voters" --name-column "B" --start-row 3 --results-start-column "D"

# Safe approach - start data after existing columns
./gop_voter_lookup.py --sheets --spreadsheet-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" \
  --results-start-column "F"  # Assumes columns A-E contain existing data

# Process only first 50 valid names (skips empty rows)
./gop_voter_lookup.py --sheets --spreadsheet-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" \
  --results-start-column "C" --row-limit 50

# Test with just 1 lookups for debugging
./gop_voter_lookup.py --sheets --spreadsheet-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" \
  --results-start-column "C" --row-limit 1 --debug
```

### How Column Assignment Works

The script automatically assigns voter data to sequential columns starting from your specified `--results-start-column`:

**Basic data fields (default):**
1. Phone
2. Address  
3. City
4. State
5. ZIP Code
6. Date of Birth
7. Party Affiliation
8. View Voter URL

**With `--extract-details`, additional fields are added:**
9. First Name
10. Middle Name
11. Last Name
12. Email
13. Home Phone
14. Work Phone
15. Cell Phone
16. Voter ID
17. Party Affiliation
18. Precinct
19. Registration Date
20. Gender
21. Employer
22. Occupation

### Column Assignment Example

If you specify `--results-start-column "D"`, the data will be assigned like this:

| A | B | C | D (Phone) | E (Address) | F (City) | G (State) | H (ZIP) | I (DOB) | J (Party) | K (URL) |
|---|---|---|-----------|-------------|----------|-----------|---------|---------|-----------|---------|
| John Doe | [existing] | [existing] | (555)123-4567 | 123 Main St | Austin | TX | 78701 | 01/15/1980 | Republican | https://... |

This approach ensures your existing data in columns A-C remains safe.

### Row Processing Features

- **Empty row skipping**: Automatically skips any rows with empty or blank names
- **Already processed detection**: Skips rows that already have data in the start column
- **Row limit**: Use `--row-limit N` to process only the first N valid (non-empty) entries
- **Accurate row mapping**: Data is written to the correct rows even when empty rows are skipped
- **Automatic headers**: Creates column headers in row 1 when `--start-row` is 2 or higher
- **Resume capability**: Can safely re-run on partially processed spreadsheets

**Example with empty rows and already processed data:**
```
Row 1: [Headers]
Row 2: John Doe      [Phone data exists] ← Skipped (already processed)
Row 3:               ← Skipped (empty)
Row 4: Jane Smith    ← Processed (1st new)
Row 5:               ← Skipped (empty) 
Row 6: Bob Johnson   [Phone data exists] ← Skipped (already processed)
Row 7: Alice Cooper  ← Processed (2nd new)
```

**Output:**
```
🎉 Processing complete:
   ✅ Updated: 2
   ⏭️  Skipped (already processed): 2
   📊 Total processed: 4/7
```

This makes it safe to re-run the script on partially processed spreadsheets.

### JSON Export
```json
{
  "John Doe": [
    {
      "name": "DOE, JOHN M.",
      "address": "123 Main St",
      "city": "Houston",
      "state": "TX",
      "zip_code": "77001",
      "phone": "(713)555-1234",
      "date_of_birth": "05/15/1965",
      "calculated_party": "2 - Soft Republican",
      "voter_id": null,
      "precinct": null,
      "status": null
    }
  ]
}
```

## Troubleshooting

### Authentication Issues
- Verify your credentials are correct
- Delete stored credentials and re-enter: `./gop_voter_lookup.py --delete-credentials`

### Browser Issues
- Browsers are installed automatically on first run
- If you encounter browser errors, try deleting the `.venv` folder and running again

### Search Issues
- The script uses "Closest Match" search by default
- Try being more specific with search terms
- Use filters to narrow results
- Use `--debug` mode to see exactly what's happening:
  ```bash
  ./gop_voter_lookup.py "John Doe" --debug
  ```
  This will:
  - Show the browser window
  - Print navigation steps
  - Display search parameters
  - Keep the browser open after searching (press Enter to close)

## License

This script is for authorized use only. Ensure you have permission to access the GOP Data Center and follow the terms of usage.
